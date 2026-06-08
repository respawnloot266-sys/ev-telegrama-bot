import logging
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    filters, ConversationHandler, Application
)

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

# Constants
DEFAULT_MAX_CHARGE_RATE_KW = 50

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Conversation States
CAR_MODEL, BATTERY_CAPACITY, FULL_CHARGE_RANGE = range(3)
CURRENT_BATTERY_PERCENT = range(1)
CHARGE_START_PERCENT, CHARGE_END_PERCENT, CHARGE_STATION_NAME, CHARGE_COST, CHARGE_TYPE = range(5)
CHARGE_TIME_START_PERCENT, CHARGE_TIME_TARGET_PERCENT = range(2)

# --- Functions ---

async def start(update: Update, context) -> int:
    user = update.effective_user
    await update.message.reply_html(f"⚡ EV Helper Bot မှ ကြိုဆိုပါတယ်, {user.mention_html()}!\nသင့်ကားအချက်အလက်တွေ သိမ်းဆည်းဖို့ /register နှိပ်ပါ။")
    return ConversationHandler.END

# Registration Logic
async def register_start(update: Update, context) -> int:
    await update.message.reply_text("🚗 ကား Model ရိုက်ထည့်ပါ (ဥပမာ: Tesla Model 3)")
    return CAR_MODEL

async def register_car_model(update: Update, context) -> int:
    context.user_data["car_model"] = update.message.text
    await update.message.reply_text("🔋 Battery Capacity (kWh) ရိုက်ထည့်ပါ (ဥပမာ: 60)")
    return BATTERY_CAPACITY

async def register_battery_capacity(update: Update, context) -> int:
    context.user_data["battery_capacity_kwh"] = float(update.message.text)
    await update.message.reply_text("🛣️ Full Charge Range (km) ရိုက်ထည့်ပါ (ဥပမာ: 450)")
    return FULL_CHARGE_RANGE

async def register_full_charge_range(update: Update, context) -> int:
    user_id = update.effective_user.id
    full_range = float(update.message.text)
    register_user(user_id, context.user_data["car_model"], context.user_data["battery_capacity_kwh"], full_range)
    add_car_model_info(context.user_data["car_model"], battery_capacity_kwh=context.user_data["battery_capacity_kwh"])
    await update.message.reply_text("✅ မှတ်ပုံတင်ပြီးပါပြီ!")
    return ConversationHandler.END

# Battery Status Logic
async def battery_status_start(update: Update, context) -> int:
    await update.message.reply_text("🔋 လက်ရှိ Battery ရာခိုင်နှုန်း (0-100) ရိုက်ထည့်ပါ။")
    return CURRENT_BATTERY_PERCENT

async def battery_status_update(update: Update, context) -> int:
    percent = int(update.message.text)
    update_user_battery_status(update.effective_user.id, percent)
    await update.message.reply_text(f"✅ Battery {percent}% အဖြစ် မှတ်တမ်းတင်ပြီးပါပြီ။")
    return ConversationHandler.END

# Find Station Logic
async def find_station(update: Update, context) -> None:
    keyboard = [[KeyboardButton("📍 လက်ရှိတည်နေရာ ပေးပို့ရန်", request_location=True)]]
    await update.message.reply_text("အနီးဆုံး အားသွင်းစခန်းများ ရှာဖွေရန် သင့်တည်နေရာကို ပေးပို့ပါ။", reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True))

async def receive_location(update: Update, context) -> None:
    loc = update.message.location
    stations = get_nearby_charging_stations(loc.latitude, loc.longitude)
    if not stations: await update.message.reply_text("အနီးနားတွင် အားသွင်းစခန်းများ မတွေ့ပါ။")
    else:
        msg = "🔌 အနီးဆုံး အားသွင်းစခန်းများ:\n"
        for s in stations[:5]:
            msg += f"- {s['addressInfo']['title']} ({s['addressInfo']['distance']:.2f} KM)\n"
        await update.message.reply_text(msg)

# Charge Time Calculation
async def charge_time_start(update: Update, context) -> int:
    await update.message.reply_text("🔋 လက်ရှိ Battery ရာခိုင်နှုန်းကို ရိုက်ထည့်ပါ။")
    return CHARGE_TIME_START_PERCENT

async def charge_time_get_start_percent(update: Update, context) -> int:
    context.user_data["start_p"] = int(update.message.text)
    await update.message.reply_text("🎯 အားသွင်းလိုသော ရာခိုင်နှုန်းကို ရိုက်ထည့်ပါ။")
    return CHARGE_TIME_TARGET_PERCENT

async def charge_time_calculate(update: Update, context) -> int:
    target = int(update.message.text)
    start = context.user_data["start_p"]
    user = get_user(update.effective_user.id)
    # Calculation using user data
    minutes = calculate_charge_time(start, target, user[2], DEFAULT_MAX_CHARGE_RATE_KW)
    await update.message.reply_text(f"⏱️ ခန့်မှန်းခြေ အားသွင်းကြာချိန်: {minutes} မိနစ်။")
    return ConversationHandler.END

# Charge Logging
async def charge_log_start(update: Update, context) -> int:
    await update.message.reply_text("🔋 စတင် Battery ရာခိုင်နှုန်းကို ရိုက်ထည့်ပါ။")
    return CHARGE_START_PERCENT

async def charge_log_get_start_percent(update: Update, context) -> int:
    context.user_data["s_p"] = int(update.message.text)
    context.user_data["s_t"] = datetime.now()
    await update.message.reply_text("🎯 ပြီးဆုံး Battery ရာခိုင်နှုန်းကို ရိုက်ထည့်ပါ။")
    return CHARGE_END_PERCENT

async def charge_log_get_end_percent(update: Update, context) -> int:
    context.user_data["e_p"] = int(update.message.text)
    await update.message.reply_text("📍 Station အမည်ကို ရိုက်ထည့်ပါ။")
    return CHARGE_STATION_NAME

async def charge_log_get_station_name(update: Update, context) -> int:
    context.user_data["station"] = update.message.text
    await update.message.reply_text("💸 ကုန်ကျစရိတ်ကို ရိုက်ထည့်ပါ။")
    return CHARGE_COST

async def charge_log_get_cost(update: Update, context) -> int:
    context.user_data["cost"] = float(update.message.text)
    keyboard = [[c] for c in CHARGER_TYPES]
    await update.message.reply_text("🔌 အားသွင်းကြိုး အမျိုးအစားကို ရွေးပါ။", reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True))
    return CHARGE_TYPE

async def charge_log_complete(update: Update, context) -> int:
    # Logic to save to DB
    user = get_user(update.effective_user.id)
    add_charge_history(update.effective_user.id, context.user_data["s_t"], datetime.now(), 
                       context.user_data["s_p"], context.user_data["e_p"], 
                       0, context.user_data["cost"], context.user_data["station"], None, update.message.text)
    await update.message.reply_text("✅ အားသွင်းမှတ်တမ်းကို သိမ်းဆည်းပြီးပါပြီ။")
    return ConversationHandler.END

# Other
async def view_history(update: Update, context) -> None: 
    h = get_charge_history(update.effective_user.id)
    await update.message.reply_text(format_charge_history(h))

async def monthly_report(update: Update, context) -> None: 
    h = get_charge_history(update.effective_user.id)
    await update.message.reply_text(get_monthly_report(update.effective_user.id, h))

async def battery_tips(update: Update, context) -> None: await update.message.reply_text(get_battery_health_tips())
async def cancel(update: Update, context) -> int: await update.message.reply_text("ဖျက်သိမ်းလိုက်ပါပြီ။", reply_markup=ReplyKeyboardRemove()); return ConversationHandler.END

# --- Main ---
def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    reg_conv = ConversationHandler(entry_points=[CommandHandler("register", register_start)],
        states={CAR_MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_car_model)],
                BATTERY_CAPACITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_battery_capacity)],
                FULL_CHARGE_RANGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_full_charge_range)]},
        fallbacks=[CommandHandler("cancel", cancel)])

    battery_conv = ConversationHandler(entry_points=[CommandHandler("battery", battery_status_start)],
        states={CURRENT_BATTERY_PERCENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, battery_status_update)]},
        fallbacks=[CommandHandler("cancel", cancel)])

    charge_time_conv = ConversationHandler(entry_points=[CommandHandler("chargetime", charge_time_start)],
        states={CHARGE_TIME_START_PERCENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, charge_time_get_start_percent)],
                CHARGE_TIME_TARGET_PERCENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, charge_time_calculate)]},
        fallbacks=[CommandHandler("cancel", cancel)])

    log_conv = ConversationHandler(entry_points=[CommandHandler("chargecomplete", charge_log_start)],
        states={CHARGE_START_PERCENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, charge_log_get_start_percent)],
                CHARGE_END_PERCENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, charge_log_get_end_percent)],
                CHARGE_STATION_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, charge_log_get_station_name)],
                CHARGE_COST: [MessageHandler(filters.TEXT & ~filters.COMMAND, charge_log_get_cost)],
                CHARGE_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, charge_log_complete)]},
        fallbacks=[CommandHandler("cancel", cancel)])

    app.add_handler(reg_conv)
    app.add_handler(battery_conv)
    app.add_handler(charge_time_conv)
    app.add_handler(log_conv)
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("findstation", find_station))
    app.add_handler(CommandHandler("history", view_history))
    app.add_handler(CommandHandler("monthlyreport", monthly_report))
    app.add_handler(CommandHandler("tips", battery_tips))
    app.add_handler(MessageHandler(filters.LOCATION, receive_location))

    print("Bot is running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
