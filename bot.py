import logging
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters
)
from config import BOT_TOKEN
import database
import charge_api

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CAR_MODEL, BATTERY_CAPACITY, FULL_RANGE = range(3)
UPDATE_BATTERY = range(1)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = database.get_user(update.effective_user.id)
    if user:
        await update.message.reply_text(
            f"👋 ပြန်လည်ကြိုဆိုပါတယ် {user[1]}!\n\n"
            f"🚗 Car: {user[2] or 'N/A'}\n"
            f"🔋 Battery: {user[4]}%\n\n"
            "Commands:\n"
            "/register - အကောင့်ဖွဲ့\n"
            "/battery - Battery update\n"
            "/findstation - Station ရှာ\n"
            "/history - စရင်း"
        )
    else:
        await update.message.reply_text(
            "⚡ EV Helper Bot မှ ကြိုဆိုပါတယ်!\n\n"
            "စတင်ရန် /register ကို နှိပ်ပါ။"
        )

async def register_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚗 ကား Model ရိုက်ထည့်ပါ\n\nဥပမာ: Tesla Model 3")
    return CAR_MODEL

async def get_car_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['car_model'] = update.message.text
    await update.message.reply_text("🔋 Battery Capacity (kWh) ရိုက်ထည့်ပါ\n\nဥပမာ: 60")
    return BATTERY_CAPACITY

async def get_battery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data['battery'] = float(update.message.text)
        await update.message.reply_text("🛣️ Full Charge Range (km) ရိုက်ထည့်ပါ\n\nဥပမာ: 450")
        return FULL_RANGE
    except ValueError:
        await update.message.reply_text("❌ နံပါတ် ရိုက်ထည့်ပါ")
        return BATTERY_CAPACITY

async def get_range(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        full_range = float(update.message.text)
        user = update.effective_user
        database.register_user(
            user.id, user.username or user.first_name,
            context.user_data['car_model'],
            context.user_data['battery'],
            full_range
        )
        await update.message.reply_text("✅ မှတ်ပုံတင် ပြီးပါပြီ!\n\nLocation share လုပ်ပြီး /findstation နှိပ်ပါ")
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ နံပါတ် ရိုက်ထည့်ပါ")
        return FULL_RANGE

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ ပယ်ဖျက်လိုက်ပါပြီ")
    return ConversationHandler.END

async def battery_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔋 Battery % ရိုက်ထည့်ပါ\n\nဥပမာ: 45")
    return UPDATE_BATTERY

async def battery_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        percent = float(update.message.text)
        if percent < 0 or percent > 100:
            raise ValueError
        database.update_battery(update.effective_user.id, percent)
        await update.message.reply_text(f"✅ Battery {percent}% သိမ်းပြီးပါပြီ")
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ 0-100 ကြား နံပါတ် ရိုက်ထည့်ပါ")
        return UPDATE_BATTERY

async def find_station(update: Update, context: ContextTypes.DEFAULT_TYPE):
    location_btn = KeyboardButton("📍 Location ပို့ပါ", request_location=True)
    await update.message.reply_text(
        "📍 Location ပို့ပေးပါ (သို့) Lat,Lon ရိုက်ထည့်ပါ\n\nဥပမာ: 16.8409, 96.1735",
        reply_markup=ReplyKeyboardMarkup([[location_btn]], one_time_keyboard=True)
    )

async def location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    loc = update.message.location
    if loc:
        lat, lon = loc.latitude, loc.longitude
    else:
        try:
            parts = update.message.text.split(',')
            lat, lon = float(parts[0]), float(parts[1])
        except:
            await update.message.reply_text("❌ Location ပို့ပါ (သို့) Lat,Lon ပုံစံ")
            return
    await update.message.reply_text("🔍 Station ရှာနေပါတယ်...")
    try:
        stations = charge_api.find_nearest(lat, lon)
        if not stations:
            await update.message.reply_text("❌ Station မတွေ့ပါ")
            return
        msg = "⚡ အနီးဆုံး Stations:\n\n"
        for i, s in enumerate(stations[:5], 1):
            msg += f"{i}. {s['name']}\n   📍 {s['address']}\n   🔌 {s['power']}kW\n   💰 {s.get('cost', 'N/A')} Ks/kWh\n\n"
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    records = database.get_history(update.effective_user.id)
    if not records:
        await update.message.reply_text("📭 စရင်း မရှိသေးပါ")
        return
    msg = "📊 Charge စရင်း:\n\n"
    for r in records[-10:]:
        msg += f"📅 {r[1]}\n🔋 {r[2]}% → {r[3]}%\n⚡ {r[4]}kWh\n💰 {r[5]} Ks\n\n"
    await update.message.reply_text(msg)

def main():
    print("Bot starting...")
    app = Application.builder().token(BOT_TOKEN).build()
    
    reg_handler = ConversationHandler(
        entry_points=[CommandHandler('register', register_start)],
        states={
            CAR_MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_car_model)],
            BATTERY_CAPACITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_battery)],
            FULL_RANGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_range)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    bat_handler = ConversationHandler(
        entry_points=[CommandHandler('battery', battery_start)],
        states={UPDATE_BATTERY: [MessageHandler(filters.TEXT & ~filters.COMMAND, battery_save)]},
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    app.add_handler(reg_handler)
    app.add_handler(bat_handler)
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('findstation', find_station))
    app.add_handler(CommandHandler('history', history))
    app.add_handler(MessageHandler(filters.LOCATION | filters.TEXT, location_handler))
    
    print("Bot running")
    app.run_polling()

if __name__ == "__main__":
    main()