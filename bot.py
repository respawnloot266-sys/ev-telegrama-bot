import os, logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes
from database import save_user, get_user, update_pct

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
MODEL, CAP, RANGE = range(3)
PCT = range(1)

# --- Automation: ညဘက် အားသွင်းရန် သတိပေးချက် (Daily Job) ---
async def off_peak_reminder(context: ContextTypes.DEFAULT_TYPE):
    # ည ၁၁ နာရီမှာ အလိုအလျောက် ပို့ပေးမယ့် message
    # မှတ်ချက် - Railway timezone အပေါ် မူတည်ပါသည်
    await context.bot.send_message(chat_id=context.job.chat_id, text="🌙 <b>Off-peak Reminder:</b> အခုအချိန်က မီးခစျေးနှုန်း သက်သာချိန် ဖြစ်ပါတယ်။ သင့်ကားကို အားသွင်းဖို့ မမေ့ပါနဲ့ဦး။", parse_mode='HTML')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_html("⚡ <b>EV Automation Bot</b>\n\n/register - စတင်မှတ်ပုံတင်ရန်\n/status - လက်ရှိအခြေအနေကြည့်ရန်\n/update - Battery update လုပ်ရန်")

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
    
    # Automation Job စတင်ခြင်း (ဥပမာ - နေ့စဉ် သတိပေးချက်)
    c.job_queue.run_daily(off_peak_reminder, time=datetime.time(hour=23, minute=0), chat_id=uid, name=str(uid))
    
    await u.message.reply_text("✅ မှတ်ပုံတင်ပြီးပါပြီ။ Automation စနစ် စတင်ပါပြီ။")
    return ConversationHandler.END

# --- Status & Prediction ---
async def status(u: Update, c: ContextTypes.DEFAULT_TYPE):
    user = get_user(u.effective_user.id)
    if not user: return await u.message.reply_text("/register အရင်လုပ်ပါ။")
    
    # Smart Prediction Logic
    pct = user[4]
    frange = float(user[3])
    current_range = (pct / 100) * frange
    
    msg = (
        f"📊 <b>ကားအခြေအနေ</b>\n\n"
        f"Model: {user[1]}\n"
        f"Battery: {pct}%\n"
        f"🛣️ ခန့်မှန်းခြေမောင်းနှင်နိုင်မှု: <b>{current_range:.1f} km</b>\n\n"
    )
    if pct <= 20: msg += "⚠️ Battery အားနည်းနေပါသည်။ အားသွင်းရန် အကြံပြုပါသည်။"
    await u.message.reply_html(msg)

async def update_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    await u.message.reply_text("🔋 လက်ရှိ Battery % ဘယ်လောက်လဲ?")
    return PCT

async def update_done(u: Update, c: ContextTypes.DEFAULT_TYPE):
    update_pct(u.effective_user.id, int(u.message.text))
    await u.message.reply_text("✅ Update လုပ်ပြီးပါပြီ။")
    return ConversationHandler.END

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    
    reg = ConversationHandler(
        entry_points=[CommandHandler("register", reg_start)],
        states={
            MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_model)],
            CAP: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_cap)],
            RANGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_range)],
        },
        fallbacks=[]
    )
    
    upd = ConversationHandler(
        entry_points=[CommandHandler("update", update_start)],
        states={PCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_done)]},
        fallbacks=[]
    )
    
    app.add_handler(reg)
    app.add_handler(upd)
    app.run_polling()

if __name__ == "__main__":
    from datetime import datetime
    import datetime
    main()
