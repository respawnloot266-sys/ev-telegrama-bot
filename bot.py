import os, logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes
from database import save_user, get_user, update_pct, get_logs

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
MODEL, CAP, RANGE = range(3)
PCT = range(1)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_html(
        "⚡ <b>EV Memory Bot</b>\n\n"
        "/register - ကားအချက်အလက်သွင်းရန်\n"
        "/update - Battery % update လုပ်ရန်\n"
        "/status - လက်ရှိအခြေအနေကြည့်ရန်\n"
        "/history - <b>ပို့ခဲ့သမျှ မှတ်တမ်းများ ပြန်ကြည့်ရန်</b>"
    )

# --- Registration ---
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
    uid = u.effective_user.id
    save_user(uid, c.user_data["m"], c.user_data["c"], u.message.text)
    await u.message.reply_text("✅ မှတ်ပုံတင်ပြီးပါပြီ။")
    return ConversationHandler.END

# --- Update Battery ---
async def update_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    await u.message.reply_text("🔋 လက်ရှိ Battery % ဘယ်လောက်လဲ?")
    return PCT

async def update_done(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    pct = int(u.message.text)
    update_pct(uid, pct) # ဒီမှာ database ထဲကို အသစ်ရော၊ မှတ်တမ်းရော သိမ်းသွားပါမယ်
    await u.message.reply_text(f"✅ Battery {pct}% အဖြစ် မှတ်တမ်းတင်ပြီးပါပြီ။")
    return ConversationHandler.END

# --- View History (ဒါက သင်လိုချင်တဲ့ အပိုင်းပါ) ---
async def history(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    logs = get_logs(uid)
    if not logs:
        return await u.message.reply_text("မှတ်တမ်း မရှိသေးပါ။")
    
    msg = "📜 <b>သင်ပို့ခဲ့သမျှ Battery မှတ်တမ်းများ</b>\n\n"
    for log in logs:
        # log[3] က date, log[2] က value
        date_str = log[3][:16] # နေ့စွဲနဲ့ အချိန်
        msg += f"• {date_str} - <b>{log[2]}%</b>\n"
    
    await u.message.reply_html(msg)

async def status(u: Update, c: ContextTypes.DEFAULT_TYPE):
    user = get_user(u.effective_user.id)
    if not user: return await u.message.reply_text("/register အရင်လုပ်ပါ။")
    pct = user[4]
    current_range = (pct / 100) * float(user[3])
    await u.message.reply_html(f"📊 <b>လက်ရှိအခြေအနေ</b>\nModel: {user[1]}\nBattery: {pct}%\n🛣️ မောင်းနိုင်သည့်ခရီး: {current_range:.1f} km")

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("history", history))
    
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("register", reg_start)],
        states={
            MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_model)],
            CAP: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_cap)],
            RANGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_range)],
        }, fallbacks=[]
    ))
    
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("update", update_start)],
        states={PCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_done)]},
        fallbacks=[]
    ))
    
    app.run_polling()

if __name__ == "__main__":
    main()
