import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import database as db

# Logging ကို အသေးစိတ် ပြခိုင်းပါမယ်
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.DEBUG # DEBUG level ကို ပြောင်းလိုက်ပါပြီ
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("DEBUG: /start command received!") # Railway Logs မှာ ပေါ်လာပါလိမ့်မယ်
    await update.message.reply_text("⚡ EV Helper Bot အလုပ်လုပ်နေပါပြီ! /register ကို နှိပ်ကြည့်ပါ။")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ဘာစာပို့ပို့ ပြန်ပြောခိုင်းကြည့်ပါမယ် (Test လုပ်ဖို့ပါ)
    print(f"DEBUG: Message received: {update.message.text}")
    await update.message.reply_text(f"သင် ပို့လိုက်တဲ့စာက: {update.message.text}")

def main():
    if not TELEGRAM_BOT_TOKEN:
        print("CRITICAL ERROR: TELEGRAM_BOT_TOKEN is missing!")
        return

    # Application ကို တည်ဆောက်ပါ
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # အခြေခံ Handler များ
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    
    print("Bot is starting and polling...")
    
    # drop_pending_updates=True က စာဟောင်းတွေ ပိတ်နေရင် ဖယ်ပေးပါလိမ့်မယ်
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
