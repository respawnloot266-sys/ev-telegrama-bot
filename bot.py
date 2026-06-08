import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackQueryHandler, ContextTypes, JobQueue
import database as db
import charge_api
from datetime import time

# Logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPEN_CHARGE_MAP_API_KEY = os.getenv("OPEN_CHARGE_MAP_API_KEY") # Ensure this is set in Railway variables

# States for Conversations
MODEL, CAP, RANGE = range(3) # For Registration
PCT = range(1) # For Battery Update
CHARGE_START_PCT, CHARGE_END_PCT = range(2) # For Charge Time Calculation

# --- Main Menu (Buttons) ---
def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("🚗 Register Car", callback_data=\'reg_start\'),
         InlineKeyboardButton("🔋 Update Battery", callback_data=\'upd_start\')],
        [InlineKeyboardButton("📊 My Status", callback_data=\'stat\'),
         InlineKeyboardButton("📜 History", callback_data=\'hist\')],
        [InlineKeyboardButton("🔌 Find Station", callback_data=\'find\'),
         InlineKeyboardButton("⏱️ Charge Time", callback_data=\'chargetime_start\')],
        [InlineKeyboardButton("💡 Battery Tips", callback_data=\'tips\')]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "⚡ <b>EV Helper Smart Assistant</b>\n\nကြိုဆိုပါတယ်! အောက်ပါခလုတ်များကို အသုံးပြု၍ စတင်နိုင်ပါပြီ။"
    if update.message:
        await update.message.reply_html(msg, reply_markup=get_main_menu())
    else:
        await update.callback_query.message.edit_text(msg, reply_markup=get_main_menu(), parse_mode=\'HTML\')

# --- Callback Handler (Buttons နှိပ်တာကို ကိုင်တွယ်ခြင်း) ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == \'reg_start\':
        await query.message.reply_text("🚗 ကား Model အမည် (ဥပမာ: Tesla Model 3)?")
        return MODEL # Start Registration Conversation
    elif query.data == \'upd_start\':
        await query.message.reply_text("🔋 လက်ရှိ Battery % (0-100)?")
        return PCT # Start Battery Update Conversation
    elif query.data == \'stat\':
        await status(update, context)
    elif query.data == \'hist\':
        await history(update, context)
    elif query.data == \'find\':
        await find_station(update, context)
    elif query.data == \'chargetime_start\':
        await chargetime_start(update, context)
        return CHARGE_START_PCT # Start Charge Time Conversation
    elif query.data == \'tips\':
        await tips(update, context)

# --- Registration (Conversation) ---
async def reg_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    await u.message.reply_text("🚗 ကား Model အမည်?")
    return MODEL

async def reg_model(u: Update, c: ContextTypes.DEFAULT_TYPE):
    c.user_data["m"] = u.message.text
    await u.message.reply_text("🔋 Battery Capacity (kWh)?")
    return CAP

async def reg_cap(u: Update, c: ContextTypes.DEFAULT_TYPE):
    c.user_data["c"] = u.message.text
    await u.message.reply_text("🛣️ Full Range (km)?")
    return RANGE

async def reg_range(u: Update, c: ContextTypes.DEFAULT_TYPE):
    try:
        db.save_user(u.effective_user.id, c.user_data["m"], c.user_data["c"], u.message.text)
        await u.message.reply_text("✅ မှတ်ပုံတင်ပြီးပါပြီ။", reply_markup=get_main_menu())
    except Exception as e:
        logger.error(f"Reg Error: {e}")
        await u.message.reply_text("Error ဖြစ်သွားပါတယ်။ ပြန်စမ်းကြည့်ပါ။")
    return ConversationHandler.END

# --- Battery Update ---
async def update_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    await u.message.reply_text("🔋 လက်ရှိ Battery % (0-100)?")
    return PCT

async def update_done(u: Update, c: ContextTypes.DEFAULT_TYPE):
    try:
        pct = int(u.message.text)
        db.update_pct(u.effective_user.id, pct)
        await u.message.reply_text(f"✅ Battery {pct}% အဖြစ် မှတ်သားပြီးပါပြီ။", reply_markup=get_main_menu())
    except Exception as e:
        logger.error(f"Update Error: {e}")
        await u.message.reply_text("ဂဏန်းဖြင့်သာ ရိုက်ထည့်ပါ။")
    return ConversationHandler.END

# --- Charge Time Calculator ---
async def chargetime_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    msg_obj = u.callback_query.message if u.callback_query else u.message
    await msg_obj.reply_text("🔋 လက်ရှိ Battery ရာခိုင်နှုန်းကို ရိုက်ထည့်ပါ။ (ဥပမာ: 20)")
    return CHARGE_START_PCT

async def chargetime_get_start_pct(u: Update, c: ContextTypes.DEFAULT_TYPE):
    try:
        start_pct = int(u.message.text)
        if not (0 <= start_pct <= 100):
            raise ValueError
        c.user_data["charge_start_pct"] = start_pct
        await u.message.reply_text("🎯 အားသွင်းလိုသော Battery ရာခိုင်နှုန်းကို ရိုက်ထည့်ပါ။ (ဥပမာ: 80)")
        return CHARGE_END_PCT
    except ValueError:
        await u.message.reply_text("မှားယွင်းသော ရာခိုင်နှုန်း ဖြစ်ပါသည်။ 0 မှ 100 အတွင်း ဂဏန်းဖြင့်သာ ရိုက်ထည့်ပါ။")
        return CHARGE_START_PCT

async def chargetime_calculate(u: Update, c: ContextTypes.DEFAULT_TYPE):
    try:
        end_pct = int(u.message.text)
        if not (0 <= end_pct <= 100):
            raise ValueError
        
        start_pct = c.user_data["charge_start_pct"]
        user = db.get_user(u.effective_user.id)

        if not user:
            await u.message.reply_text("/register အရင်လုပ်ပါ။", reply_markup=get_main_menu())
            return ConversationHandler.END

        battery_capacity_kwh = float(user[2]) # user[2] is battery_cap
        # For simplicity, using a default charge rate. Can be improved by getting car_model_info
        max_charge_rate_kw = 50 # Default to 50kW DC fast charger

        # Simple calculation for demonstration
        kwh_needed = (end_pct - start_pct) / 100 * battery_capacity_kwh
        charge_time_hours = kwh_needed / max_charge_rate_kw
        charge_time_minutes = round(charge_time_hours * 60)

        await u.message.reply_html(
            f"⏱️ <b>အားသွင်းကြာချိန် ခန့်မှန်းခြေ:</b> {charge_time_minutes} မိနစ်ခန့်\n"
            f"({start_pct}% မှ {end_pct}% အထိ၊ {max_charge_rate_kw} kW ဖြင့်)", reply_markup=get_main_menu())
        return ConversationHandler.END
    except ValueError:
        await u.message.reply_text("မှားယွင်းသော ရာခိုင်နှုန်း ဖြစ်ပါသည်။ 0 မှ 100 အတွင်း ဂဏန်းဖြင့်သာ ရိုက်ထည့်ပါ။")
        return CHARGE_END_PCT

# --- Tools ---
async def status(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    user = db.get_user(uid)
    msg_obj = u.callback_query.message if u.callback_query else u.message
    
    if not user: 
        return await msg_obj.reply_text("/register အရင်လုပ်ပါ။", reply_markup=get_main_menu())
    
    pct = user[4]
    current_range = (pct / 100) * float(user[3])
    await msg_obj.reply_html(f"📊 <b>အခြေအနေ</b>\nModel: {user[1]}\nBattery: {pct}%\n🛣️ မောင်းနိုင်သည့်ခရီး: {current_range:.1f} km", reply_markup=get_main_menu())

async def history(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    logs = db.get_logs(uid)
    msg_obj = u.callback_query.message if u.callback_query else u.message
    
    if not logs: return await msg_obj.reply_text("မှတ်တမ်း မရှိပါ။", reply_markup=get_main_menu())
    msg = "📜 <b>မှတ်တမ်းများ:</b>\n"
    for log in logs:
        date_str = str(log[4])[:16] 
        pct_val = log[3]
        msg += f"• {date_str} - <b>{pct_val}%</b>\n"
    await msg_obj.reply_html(msg, reply_markup=get_main_menu())

async def find_station(u: Update, c: ContextTypes.DEFAULT_TYPE):
    msg_obj = u.callback_query.message if u.callback_query else u.message
    kb = [[KeyboardButton("📍 တည်နေရာပေးပို့ရန်", request_location=True)]]
    await msg_obj.reply_text("အနီးဆုံးစခန်းရှာရန် တည်နေရာကို ပေးပို့ပါ။", 
        reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True))

async def location_handler(u: Update, c: ContextTypes.DEFAULT_TYPE):
    # This handler is for messages that contain location, not callback queries
    msg_obj = u.message

    if not OPEN_CHARGE_MAP_API_KEY:
        logger.error("OPEN_CHARGE_MAP_API_KEY is not set.")
        await msg_obj.reply_text("အားသွင်းစခန်းရှာဖွေရန် API Key မရှိပါ။", reply_markup=get_main_menu())
        return

    latitude = u.message.location.latitude
    longitude = u.message.location.longitude
    
    await msg_obj.reply_text("အားသွင်းစခန်းများ ရှာဖွေနေပါသည်။ ခဏစောင့်ပါ။", reply_markup=ReplyKeyboardRemove())
    
    stations = charge_api.get_nearby_charging_stations(latitude, longitude, distance=10, max_results=5)
    
    if stations:
        msg = "🔌 <b>အနီးဆုံး အားသွင်းစခန်းများ:</b>\n\n"
        for i, station in enumerate(stations):
            title = station.get("addressInfo", {}).get("title", "N/A")
            address = station.get("addressInfo", {}).get("addressLine1", "")
            distance = station.get("addressInfo", {}).get("distance", 0)
            s_lat = station.get("addressInfo", {}).get("latitude")
            s_lon = station.get("addressInfo", {}).get("longitude")
            
            google_maps_link = f"https://www.google.com/maps/search/?api=1&query={s_lat},{s_lon}"

            msg += f"{i+1}. <a href=\"{google_maps_link}\">{title}</a> ({distance:.1f} KM)\n"
            if address: msg += f"   {address}\n"
            
            connections = station.get("connections", [])
            if connections:
                msg += "   ချိတ်ဆက်မှုများ: "
                conn_details = []
                for conn in connections:
                    conn_type = conn.get("connectionType", {}).get("title", "N/A")
                    power_kw = conn.get("powerKW", "N/A")
                    conn_details.append(f"{conn_type} ({power_kw}kW)")
                msg += ", ".join(conn_details) + "\n"
            msg += "---\n"
        await msg_obj.reply_html(msg, disable_web_page_preview=True, reply_markup=get_main_menu())
    else:
        await msg_obj.reply_text("သင့်အနီးအနားတွင် အားသွင်းစခန်း ရှာမတွေ့ပါ။", reply_markup=get_main_menu())

async def tips(u: Update, c: ContextTypes.DEFAULT_TYPE):
    msg_obj = u.callback_query.message if u.callback_query else u.message
    await msg_obj.reply_html("💡 <b>EV Tips:</b>\n• Battery 20%-80% ကြားထားပါ။\n• ညဘက်အားသွင်းရင် စျေးသက်သာပါတယ်။", reply_markup=get_main_menu())

async def cancel(u: Update, c: ContextTypes.DEFAULT_TYPE):
    await u.message.reply_text("လုပ်ဆောင်ချက်ကို ဖျက်သိမ်းလိုက်ပါပြီ။", reply_markup=get_main_menu())
    return ConversationHandler.END

# --- JobQueue Functions ---
async def send_off_peak_reminder(context: ContextTypes.DEFAULT_TYPE):
    # This is a placeholder. In a real scenario, you'd fetch user preferences
    # and send personalized reminders.
    # For now, we'll send a message to a hardcoded chat_id for testing.
    # You would need to store chat_ids of users who want reminders.
    # For demonstration, let's assume a user with chat_id = 123456789 (replace with a real chat_id for testing)
    # Or, we could fetch all user IDs from the database and iterate.
    
    # For testing, let's try to get all user IDs and send a message to them.
    # This requires a new function in database.py: get_all_user_ids()
    user_ids = db.get_all_user_ids()
    for user_id in user_ids:
        try:
            await context.bot.send_message(chat_id=user_id, text="ညဘက် အားသွင်းဖို့ မမေ့ပါနဲ့နော်။ (Off-peak Charging Reminder)")
            logger.info(f"Sent off-peak reminder to user {user_id}")
        except Exception as e:
            logger.error(f"Failed to send off-peak reminder to user {user_id}: {e}")
    # Example: context.bot.send_message(chat_id=YOUR_TEST_CHAT_ID, text="ညဘက် အားသွင်းဖို့ မမေ့ပါနဲ့နော်။")

def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("No TELEGRAM_BOT_TOKEN found!")
        return

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Get the JobQueue instance
    job_queue = app.job_queue

    # Schedule the off-peak reminder job
    # For testing, schedule it to run every minute
    # In a real scenario, you'd schedule it for specific off-peak hours
    job_queue.run_repeating(send_off_peak_reminder, interval=60, first=0, name="off_peak_reminder")

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.LOCATION, location_handler))
    
    # Conversations
    reg_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern=\'^reg_start$\'), CommandHandler("register", reg_start)],
        states={
            MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_model)],
            CAP: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_cap)],
            RANGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_range)],
        }, fallbacks=[CommandHandler("cancel", cancel)]
    )
    
    upd_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern=\'^upd_start$\'), CommandHandler("update", update_start)],
        states={PCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_done)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    chargetime_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern=\'^chargetime_start$\'), CommandHandler("chargetime", chargetime_start)],
        states={
            CHARGE_START_PCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, chargetime_get_start_pct)],
            CHARGE_END_PCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, chargetime_calculate)],
        }, fallbacks=[CommandHandler("cancel", cancel)]
    )
    
    app.add_handler(reg_conv)
    app.add_handler(upd_conv)
    app.add_handler(chargetime_conv)
    
    print("Bot is running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()