import logging
from datetime import datetime
from telegram.ext import Application


from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove,  KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ConversationHandler

from config import TELEGRAM_BOT_TOKEN, DEFAULT_LOW_BATTERY_THRESHOLD, CHARGER_TYPES
from database import (
    init_db, connect_db, get_user, register_user, update_user_battery_status,
    update_user_location, add_charge_history, get_charge_history, add_favorite_station,
    get_favorite_stations, get_car_model_info, add_car_model_info
)
from charge_api import get_nearby_charging_stations
from utils import (
    calculate_distance, calculate_charge_time, format_charge_history,
    get_monthly_report, get_battery_health_tips, get_off_peak_reminder,
    get_service_reminder, get_tyre_pressure_reminder
)

# Enable logging
logging.basicConfig(
    format=
' %(asctime)s - %(name)s - %(levelname)s - %(message)s'
, level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states for registration
CAR_MODEL, BATTERY_CAPACITY, FULL_CHARGE_RANGE = range(3)

# Conversation states for battery update
CURRENT_BATTERY_PERCENT = range(1)

# Conversation states for charge logging
CHARGE_START_PERCENT, CHARGE_END_PERCENT, CHARGE_STATION_NAME, CHARGE_COST, CHARGE_TYPE = range(5)

# Conversation states for charge time calculation
CHARGE_TIME_START_PERCENT, CHARGE_TIME_TARGET_PERCENT = range(2)

async def start(update: Update, context) -> int:
    """Sends a welcome message and prompts to register."""
    user = update.effective_user
    await update.message.reply_html(
        f"⚡ EV Helper Bot မှ ကြိုဆိုပါတယ်, {user.mention_html()}!\n"
        "သင့်ကားအချက်အလက်တွေ သိမ်းဆည်းဖို့ /register နှိပ်ပါ။"
    )
    return ConversationHandler.END

async def register_start(update: Update, context) -> int:
    """Starts the registration conversation."""
    await update.message.reply_text(
        "🚗 ကား Model ရိုက်ထည့်ပါ (ဥပမာ: Tesla Model 3)"
    )
    return CAR_MODEL

async def register_car_model(update: Update, context) -> int:
    """Stores car model and asks for battery capacity."""
    context.user_data["car_model"] = update.message.text
    await update.message.reply_text(
        "🔋 Battery Capacity (kWh) ရိုက်ထည့်ပါ (ဥပမာ: 60)"
    )
    return BATTERY_CAPACITY

async def register_battery_capacity(update: Update, context) -> int:
    """Stores battery capacity and asks for full charge range."""
    try:
        capacity = float(update.message.text)
        if capacity <= 0:
            raise ValueError
        context.user_data["battery_capacity_kwh"] = capacity
        await update.message.reply_text(
            "🛣️ Full Charge Range (km) ရိုက်ထည့်ပါ (ဥပမာ: 450)"
        )
        return FULL_CHARGE_RANGE
    except ValueError:
        await update.message.reply_text(
            "မှားယွင်းသော Battery Capacity ဖြစ်ပါသည်။ ဂဏန်းဖြင့်သာ ရိုက်ထည့်ပါ။"
        )
        return BATTERY_CAPACITY

async def register_full_charge_range(update: Update, context) -> int:
    """Stores full charge range and completes registration."""
    try:
        full_range = float(update.message.text)
        if full_range <= 0:
            raise ValueError
        user_id = update.effective_user.id
        car_model = context.user_data["car_model"]
        battery_capacity_kwh = context.user_data["battery_capacity_kwh"]

        register_user(user_id, car_model, battery_capacity_kwh, full_range)
        # Also add/update car model info in car_models table if not exists
        add_car_model_info(car_model, battery_capacity_kwh=battery_capacity_kwh)

        await update.message.reply_text(
            "✅ မှတ်ပုံတင်ပြီးပါပြီ! သင့်ကားအချက်အလက်များကို သိမ်းဆည်းထားပါသည်။"
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text(
            "မှားယွင်းသော Full Charge Range ဖြစ်ပါသည်။ ဂဏန်းဖြင့်သာ ရိုက်ထည့်ပါ။"
        )
        return FULL_CHARGE_RANGE

async def cancel(update: Update, context) -> int:
    """Cancels and ends the conversation."""
    await update.message.reply_text(
        "လုပ်ဆောင်ချက်ကို ဖျက်သိမ်းလိုက်ပါပြီ။", reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def battery_status_start(update: Update, context) -> int:
    """Starts the battery status update conversation."""
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("ကျေးဇူးပြု၍ /register ဖြင့် အရင်မှတ်ပုံတင်ပါ။")
        return ConversationHandler.END

    await update.message.reply_text(
        "🔋 လက်ရှိ Battery ရာခိုင်နှုန်း (ဥပမာ: 75) ရိုက်ထည့်ပါ။"
    )
    return CURRENT_BATTERY_PERCENT

async def battery_status_update(update: Update, context) -> int:
    """Updates battery percentage and checks for low battery alert."""
    try:
        battery_percent = int(update.message.text)
        if not (0 <= battery_percent <= 100):
            raise ValueError

        user_id = update.effective_user.id
        update_user_battery_status(user_id, battery_percent)

        await update.message.reply_text(
            f"✅ Battery ရာခိုင်နှုန်း {battery_percent}% အဖြစ် မှတ်တမ်းတင်ပြီးပါပြီ။"
        )

        user = get_user(user_id)
        if user and battery_percent <= user[5]: # user[5] is low_battery_threshold
            await update.message.reply_text(
                f"⚠️ **သတိပေးချက်:** သင့် Battery က {battery_percent}% သာ ကျန်ရှိတော့ပါပြီ။ အားသွင်းရန် လိုအပ်ပါသည်။"
            )
        
        if battery_percent == 100:
            await update.message.reply_text(
                "💯 Battery အားအပြည့်သွင်းပြီးပါပြီ။ /chargecomplete ဖြင့် မှတ်တမ်းတင်နိုင်ပါသည်။"
            )

        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text(
            "မှားယွင်းသော ရာခိုင်နှုန်း ဖြစ်ပါသည်။ 0 မှ 100 အတွင်း ဂဏန်းဖြင့်သာ ရိုက်ထည့်ပါ။"
        )
        return CURRENT_BATTERY_PERCENT

async def find_station(update: Update, context) -> None:
    """Requests user's location to find nearby charging stations."""
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("ကျေးဇူးပြု၍ /register ဖြင့် အရင်မှတ်ပုံတင်ပါ။")
        return

    keyboard = [[telegram.KeyboardButton("📍 လက်ရှိတည်နေရာ ပေးပို့ရန်", request_location=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    await update.message.reply_text(
        "🔌 အနီးဆုံး အားသွင်းစခန်းများ ရှာဖွေရန် သင့်လက်ရှိတည်နေရာကို ပေးပို့ပါ။",
        reply_markup=reply_markup
    )

async def receive_location(update: Update, context) -> None:
    """Receives user's location and finds nearby charging stations."""
    user_location = update.message.location
    user_id = update.effective_user.id
    
    update_user_location(user_id, user_location.latitude, user_location.longitude)

    await update.message.reply_text("အားသွင်းစခန်းများ ရှာဖွေနေပါသည်။ ခဏစောင့်ပါ။", reply_markup=ReplyKeyboardRemove())

    stations = get_nearby_charging_stations(user_location.latitude, user_location.longitude)

    if not stations:
        await update.message.reply_text("အနီးအနားတွင် အားသွင်းစခန်းများ မတွေ့ပါ။")
        return

    message = "🔌 **အနီးဆုံး အားသွင်းစခန်းများ** 🔌\n\n"
    for station in stations:
        address_info = station.get("addressInfo", {})
        connections = station.get("connections", [])

        station_name = address_info.get("title", "N/A")
        distance = address_info.get("distance", "N/A")
        address = address_info.get("addressLine1", "")
        town = address_info.get("town", "")

        message += f"**{station_name}** ({distance:.2f} KM)\n"
        message += f"  {address}, {town}\n"
        if connections:
            message += "  **Chargers:**\n"
            for conn in connections:
                conn_type = conn.get("connectionType", {}).get("title", "N/A")
                power_kw = conn.get("powerKW", "N/A")
                message += f"    - {conn_type} ({power_kw} kW)\n"
        message += "\n"
    await update.message.reply_text(message)

async def charge_time_start(update: Update, context) -> int:
    """Starts the charge time calculation conversation."""
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("ကျေးဇူးပြု၍ /register ဖြင့် အရင်မှတ်ပုံတင်ပါ။")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "🔋 လက်ရှိ Battery ရာခိုင်နှုန်းကို ရိုက်ထည့်ပါ။ (ဥပမာ: 20)"
    )
    return CHARGE_TIME_START_PERCENT

async def charge_time_get_start_percent(update: Update, context) -> int:
    """Gets start battery percent and asks for target percent."""
    try:
        start_percent = int(update.message.text)
        if not (0 <= start_percent <= 100):
            raise ValueError
        context.user_data["charge_time_start_percent"] = start_percent
        await update.message.reply_text(
            "🎯 အားသွင်းလိုသော Battery ရာခိုင်နှုန်းကို ရိုက်ထည့်ပါ။ (ဥပမာ: 80)"
        )
        return CHARGE_TIME_TARGET_PERCENT
    except ValueError:
        await update.message.reply_text(
            "မှားယွင်းသော ရာခိုင်နှုန်း ဖြစ်ပါသည်။ 0 မှ 100 အတွင်း ဂဏန်းဖြင့်သာ ရိုက်ထည့်ပါ။"
        )
        return CHARGE_TIME_START_PERCENT

async def charge_time_calculate(update: Update, context) -> int:
    """Calculates and displays charge time."""
    try:
        target_percent = int(update.message.text)
        if not (0 <= target_percent <= 100):
            raise ValueError
        
        start_percent = context.user_data["charge_time_start_percent"]
        user_id = update.effective_user.id
        user = get_user(user_id)

        if not user:
            await update.message.reply_text("ကျေးဇူးပြု၍ /register ဖြင့် အရင်မှတ်ပုံတင်ပါ။")
            return ConversationHandler.END

        car_model = user[1] # car_model
        battery_capacity_kwh = user[2] # battery_capacity_kwh
        
        car_model_info = get_car_model_info(car_model)
        max_charge_rate_kw = DEFAULT_MAX_CHARGE_RATE_KW
        if car_model_info and car_model_info[3]: # max_charge_rate_kw
            max_charge_rate_kw = car_model_info[3]

        charge_time_minutes = calculate_charge_time(
            start_percent, target_percent, battery_capacity_kwh, max_charge_rate_kw
        )

        await update.message.reply_text(
            f"⏱️ **အားသွင်းကြာချိန် ခန့်မှန်းခြေ:** {charge_time_minutes} မိနစ်ခန့်\n"
            f"({start_percent}% မှ {target_percent}% အထိ၊ {max_charge_rate_kw} kW ဖြင့်)"
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text(
            "မှားယွင်းသော ရာခိုင်နှုန်း ဖြစ်ပါသည်။ 0 မှ 100 အတွင်း ဂဏန်းဖြင့်သာ ရိုက်ထည့်ပါ။"
        )
        return CHARGE_TIME_TARGET_PERCENT

async def charge_log_start(update: Update, context) -> int:
    """Starts the charge logging conversation."""
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("ကျေးဇူးပြု၍ /register ဖြင့် အရင်မှတ်ပုံတင်ပါ။")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "🔋 အားသွင်းမစခင် Battery ရာခိုင်နှုန်းကို ရိုက်ထည့်ပါ။ (ဥပမာ: 20)"
    )
    return CHARGE_START_PERCENT

async def charge_log_get_start_percent(update: Update, context) -> int:
    """Gets start battery percent and asks for end percent."""
    try:
        start_percent = int(update.message.text)
        if not (0 <= start_percent <= 100):
            raise ValueError
        context.user_data["charge_log_start_percent"] = start_percent
        context.user_data["charge_log_start_time"] = datetime.now()
        await update.message.reply_text(
            "🎯 အားသွင်းပြီးစီးချိန် Battery ရာခိုင်နှုန်းကို ရိုက်ထည့်ပါ။ (ဥပမာ: 80)"
        )
        return CHARGE_END_PERCENT
    except ValueError:
        await update.message.reply_text(
            "မှားယွင်းသော ရာခိုင်နှုန်း ဖြစ်ပါသည်။ 0 မှ 100 အတွင်း ဂဏန်းဖြင့်သာ ရိုက်ထည့်ပါ။"
        )
        return CHARGE_START_PERCENT

async def charge_log_get_end_percent(update: Update, context) -> int:
    """Gets end battery percent and asks for station name."""
    try:
        end_percent = int(update.message.text)
        if not (0 <= end_percent <= 100):
            raise ValueError
        context.user_data["charge_log_end_percent"] = end_percent
        context.user_data["charge_log_end_time"] = datetime.now()
        await update.message.reply_text(
            "📍 အားသွင်းခဲ့သော Station အမည်ကို ရိုက်ထည့်ပါ။ (မသိပါက 'မသိပါ' ဟု ရိုက်ထည့်နိုင်သည်)"
        )
        return CHARGE_STATION_NAME
    except ValueError:
        await update.message.reply_text(
            "မှားယွင်းသော ရာခိုင်နှုန်း ဖြစ်ပါသည်။ 0 မှ 100 အတွင်း ဂဏန်းဖြင့်သာ ရိုက်ထည့်ပါ။"
        )
        return CHARGE_END_PERCENT

async def charge_log_get_station_name(update: Update, context) -> int:
    """Gets station name and asks for cost."""
    station_name = update.message.text
    context.user_data["charge_log_station_name"] = station_name if station_name.lower() != 'မသိပါ' else None
    await update.message.reply_text(
        "💸 ကုန်ကျစရိတ်ကို ရိုက်ထည့်ပါ။ (မသိပါက '0' ဟု ရိုက်ထည့်နိုင်သည်)"
    )
    return CHARGE_COST

async def charge_log_get_cost(update: Update, context) -> int:
    """Gets cost and asks for charger type."""
    try:
        cost = float(update.message.text)
        if cost < 0:
            raise ValueError
        context.user_data["charge_log_cost"] = cost if cost > 0 else None
        
        keyboard = [[charger_type] for charger_type in CHARGER_TYPES]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        await update.message.reply_text(
            "🔌 အားသွင်းကြိုး အမျိုးအစားကို ရွေးချယ်ပါ သို့မဟုတ် ရိုက်ထည့်ပါ။",
            reply_markup=reply_markup
        )
        return CHARGE_TYPE
    except ValueError:
        await update.message.reply_text(
            "မှားယွင်းသော ကုန်ကျစရိတ် ဖြစ်ပါသည်။ ဂဏန်းဖြင့်သာ ရိုက်ထည့်ပါ။"
        )
        return CHARGE_COST

async def charge_log_complete(update: Update, context) -> int:
    """Completes charge logging."""
    charger_type = update.message.text
    user_id = update.effective_user.id
    user = get_user(user_id)

    if not user:
        await update.message.reply_text("ကျေးဇူးပြု၍ /register ဖြင့် အရင်မှတ်ပုံတင်ပါ။")
        return ConversationHandler.END

    start_percent = context.user_data["charge_log_start_percent"]
    end_percent = context.user_data["charge_log_end_percent"]
    start_time = context.user_data["charge_log_start_time"]
    end_time = context.user_data["charge_log_end_time"]
    station_name = context.user_data["charge_log_station_name"]
    cost = context.user_data["charge_log_cost"]

    battery_capacity_kwh = user[2] # battery_capacity_kwh
    kwh_charged = battery_capacity_kwh * (end_percent - start_percent) / 100

    add_charge_history(
        user_id, start_time, end_time, start_percent, end_percent,
        kwh_charged, cost, station_name, None, charger_type
    )
    update_user_battery_status(user_id, end_percent) # Update current battery status

    await update.message.reply_text(
        "✅ အားသွင်းမှတ်တမ်းကို သိမ်းဆည်းပြီးပါပြီ။", reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def view_history(update: Update, context) -> None:
    """Displays user's charge history."""
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not user:
        await update.message.reply_text("ကျေးဇူးပြု၍ /register ဖြင့် အရင်မှတ်ပုံတင်ပါ။")
        return

    history = get_charge_history(user_id)
    message = format_charge_history(history)
    await update.message.reply_text(message)

async def monthly_report(update: Update, context) -> None:
    """Displays user's monthly charge report."""
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not user:
        await update.message.reply_text("ကျေးဇူးပြု၍ /register ဖြင့် အရင်မှတ်ပုံတင်ပါ။")
        return
    
    history = get_charge_history(user_id, limit=None) # Get all history for report
    message = get_monthly_report(user_id, history)
    await update.message.reply_text(message)

async def battery_tips(update: Update, context) -> None:
    """Displays battery health tips."""
    await update.message.reply_text(get_battery_health_tips())

async def off_peak_reminder(update: Update, context) -> None:
    """Displays off-peak charging reminder."""
    await update.message.reply_text(get_off_peak_reminder())

async def service_reminder(update: Update, context) -> None:
    """Displays service reminder."""
    await update.message.reply_text(get_service_reminder())

async def tyre_pressure_reminder(update: Update, context) -> None:
    """Displays tyre pressure reminder."""
    await update.message.reply_text(get_tyre_pressure_reminder())

async def error_handler(update: Update, context) -> None:
    """Log the error and send a telegram message to notify the user."""
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    await update.message.reply_text(
        "တစ်ခုခု မှားယွင်းသွားပါသည်။ ကျေးဇူးပြု၍ နောက်မှ ထပ်ကြိုးစားပါ။"
    )

def main():
    # Variables စစ်ဆေးခြင်း
    if not TELEGRAM_BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN is missing!")
        return

    # Application ကို Build လုပ်ခြင်း
    # PTB Version 21+ အတွက် ပိုမိုတည်ငြိမ်သော နည်းလမ်း
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Commands များ ထည့်သွင်းခြင်း
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("register", register))
    application.add_handler(CommandHandler("battery", battery_update))
    application.add_handler(CommandHandler("findstation", find_station))
    application.add_handler(CommandHandler("chargetime", charge_time_calc))
    application.add_handler(CommandHandler("chargecomplete", charge_complete))
    application.add_handler(CommandHandler("history", history))
    application.add_handler(CommandHandler("monthlyreport", monthly_report))
    application.add_handler(CommandHandler("tips", tips))
    
    # Location handler
    application.add_handler(MessageHandler(filters.LOCATION, handle_location))
    
    # Registration conversation
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Bot ကို စတင်ခြင်း
    print("Bot is starting...")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
