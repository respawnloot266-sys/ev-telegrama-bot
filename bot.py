
import logging
import os
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Conversation states
CAR_MODEL, BATTERY_CAPACITY, FULL_CHARGE_RANGE = range(3)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚡ EV Helper Bot မှ ကြိုဆိုပါတယ်! /register နှိပ်ပါ။")

async def register_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚗 ကား Model ရိုက်ထည့်ပါ (ဥပမာ: Tesla Model 3)")
    return CAR_MODEL

async def register_car_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["car_model"] = update.message.text
    await update.message.reply_text("🔋 Battery Capacity (kWh) ရိုက်ထည့်ပါ")
    return BATTERY_CAPACITY

async def register_battery_capacity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["cap"] = update.message.text
    await update.message.reply_text("🛣️ Full Charge Range (km) ရိုက်ထည့်ပါ")
    return FULL_CHARGE_RANGE

async def register_full_charge_range(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ဒီနေရာမှာ data သိမ်းပြီး စာပြန်ပါမယ်
    await update.message.reply_text("✅ မှတ်ပုံတင်ပြီးပါပြီ!")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ဖျက်သိမ်းလိုက်ပါပြီ။")
    return ConversationHandler.END

def main():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    reg_handler = ConversationHandler(
        entry_points=[CommandHandler("register", register_start)],
        states={
            CAR_MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_car_model)],
            BATTERY_CAPACITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_battery_capacity)],
            FULL_CHARGE_RANGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_full_charge_range)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(reg_handler)
    application.run_polling()

if __name__ == "__main__":
    main()