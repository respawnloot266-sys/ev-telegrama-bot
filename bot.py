import os
import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes
import database as db

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# States
MODEL, CAP, RANGE = range(3)
PCT = range(1)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_html(
        "⚡ <b>EV Helper Bot</b>\n\n"
        "/register - ကားအချက်အလက်သွင်းရန်\n"
        "/update - Battery % update လုပ်ရန်\n"
        "/status - လက်ရှိအခြေအနေ\n"
        "/history - မှတ်တမ်းများကြည့်ရန်\n"
        "/findstation - အနီးဆုံးစခန်းရှာရန်"
    )

# --- Registration Flow ---
async def reg_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    await u.message.reply_text("🚗 ကား Model အမည် (ဥပမာ: Tesla Model 3)?")
    return MODEL

async def reg_model(u: Update, c: ContextTypes.DEFAULT_TYPE):
    c.user_data["m"] = u.message.text
    await u.message.reply_text("🔋 Battery Capacity (kWh) (ဥပမာ: 60)?")
    return CAP

async def reg_cap(u: Update, c: ContextTypes.DEFAULT_TYPE):
    c.user_data["c"] = u.message.text
    await u.message.reply_text("🛣️ Full Range (km) (ဥပမာ: 450)?")
    return RANGE

async def reg_range(u: Update, c: ContextTypes.DEFAULT_TYPE):
    try:
        db.save_user(u.effective_user.id, c.user_data["m"], c.user_data["c"], u.message.text)
        await u.message.reply_text("✅ မှတ်ပုံတင်ပြီးပါပြီ။ /status ကို နှိပ်ကြည့်ပါ။")
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
        await u.message.reply_text(f"✅ Battery {pct}% အဖြစ် မှတ်သားပြီးပါပြီ။")
    except:
        await u.message.reply_text("ဂဏန်းဖြင့်သာ ရိုက်ထည့်ပါ။")
    return ConversationHandler.END

# --- Tools ---
async def status(u: Update, c: ContextTypes.DEFAULT_TYPE):
    user = db.get_user(u.effective_user.id)
    if not user: return await u.message.reply_text("/register အရင်လုပ်ပါ။")
    pct = user[4]
    current_range = (pct / 100) * float(user[3])
    await u.message.reply_html(f"📊 <b>အခြေအနေ</b>\nModel: {user[1]}\nBattery: {pct}%\n🛣️ မောင်းနိုင်သည့်ခရီး: {current_range:.1f} km")

async def history(u: Update, c: ContextTypes.DEFAULT_TYPE):
    logs = db.get_logs(u.effective_user.id)
    if not logs: return await u.message.reply_text("မှတ်တမ်း မရှိပါ။")
    msg = "📜 <b>မှတ်တမ်းများ:</b>\n"
    for log in logs: msg += f"• {log[3][:16]} - {log[2]}%\n"
    await u.message.reply_html(msg)

async def find_station(u: Update, c: ContextTypes.DEFAULT_TYPE):
    kb = [[KeyboardButton("📍 တည်နေရာပေးပို့ရန်", request_location=True)]]
    await u.message.reply_text("တည်နေရာပေးပို့ပါ", reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True))

async def location_handler(u: Update, c: ContextTypes.DEFAULT_TYPE):
    await u.message.reply_html("🔌 <b>အနီးဆုံးစခန်းများ:</b>\n1. Earth EV (1.2km)\n2. Charge+ (2.5km)", reply_markup=ReplyKeyboardRemove())

async def cancel(u: Update, c: ContextTypes.DEFAULT_TYPE):
    await u.message.reply_text("ဖျက်သိမ်းလိုက်ပါပြီ။", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CommandHandler("findstation", find_station))
    app.add_handler(MessageHandler(filters.LOCATION, location_handler))
    
    # Conversations
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("register", reg_start)],
        states={
            MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_model)],
            CAP: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_cap)],
            RANGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_range)],
        }, fallbacks=[CommandHandler("cancel", cancel)]
    ))
    
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("update", update_start)],
        states={PCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_done)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    ))
    
    print("Bot is running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()