import logging
from datetime import datetime, time
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters
)
from config import BOT_TOKEN, COST_PER_KWH, LOW_BATTERY_ALERT
import database
import charge_api

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CAR_MODEL, BATTERY_CAPACITY, FULL_RANGE = range(3)
UPDATE_BATTERY = range(1)
TIME_POWER, TIME_PERCENT = range(2)
WAITING_END_PERCENT = range(1)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = database.get_user(update.effective_user.id)
    if user:
        await update.message.reply_text(
            f"👋 ပြန်လည်ကြိုဆိုပါတယ် {user[1]}!\n\n"
            f"🚗 Car: {user[2] or 'N/A'}\n"
            f"🔋 Battery: {user[4]}%\n\n"
            "📋 Commands:\n"
            "/register - အကောင့်ဖွဲ့\n"
            "/battery - Battery % update\n"
            "/findstation - အနီးဆုံး station\n"
            "/cheapest - အသက်သာဆုံး station\n"
            "/calctime - Charge ကြာချိန်\n"
            "/startcharge - Charge စတင်\n"
            "/history - Charge စရင်း"
        )
    else:
        await update.message.reply_text(
            "⚡ **EV Helper Bot** မှ ကြိုဆိုပါတယ်!\n\n"
            "စတင်ရန် /register ကို နှိပ်ပါ။"
        )

async def register_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚗 **ကား Model ရိုက်ထည့်ပါ**\n\n"
        "ဥပမာ: Tesla Model 3, BYD Atto 3, MG ZS EV"
    )
    return CAR_MODEL

async def get_car_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['car_model'] = update.message.text
    await update.message.reply_text(
        "🔋 **Battery Capacity (kWh) ရိုက်ထည့်ပါ**\n\n"
        "ဥပမာ: 60"
    )
    return BATTERY_CAPACITY

async def get_battery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data['battery'] = float(update.message.text)
        await update.message.reply_text(
            "🛣️ **Full Charge Range (km) ရိုက်ထည့်ပါ**\n\n"
            "ဥပမာ: 450"
        )
        return FULL_RANGE
    except ValueError:
        await update.message.reply_text("❌ ကျန်စစ် နံပါတ် ရိုက်ထည့်ပါ")
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
        await update.message.reply_text(
            "✅ **မှတ်ပုံတင် ပြီးပါပြီ!**\n\n"
            "Location share လုပ်ပြီး /findstation နှိပ်ပါ"
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ ကျန်စစ် နံပါတ် ရိုက်ထည့်ပါ")
        return FULL_RANGE

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ ပယ်ဖျက်လိုက်ပါပြီ")
    return ConversationHandler.END

async def battery_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔋 **လက်ရှိ Battery % ရိုက်ထည့်ပါ**\n\nဥပမာ: 45")
    return UPDATE_BATTERY

async def battery_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        percent = float(update.message.text)
        if percent < 0 or percent > 100:
            raise ValueError
        database.update_battery(update.effective_user.id, percent)
        user = database.get_user(update.effective_user.id)
        full_range = user[5]
        current_range = round(full_range * percent / 100, 1)
        warning = "\n\n⚠️ **Battery နည်းနေပါတယ်! Charge ဖြည့်ပါ။**" if percent <= 20 else ""
        await update.message.reply_text(
            f"✅ Battery {percent}% သိမ်းပြီးပါပြီ\n\n"
            f"🔋 Range: {current_range} km{warning}"
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ 0-100 ကြား နံပါတ် ရိုက်ထည့်ပါ")
        return UPDATE_BATTERY

async def find_station(update: Update, context: ContextTypes.DEFAULT_TYPE):
    location_btn = KeyboardButton("📍 Location ပို့ပါ", request_location=True)
    reply_markup = ReplyKeyboardMarkup([[location_btn]], one_time_keyboard=True)
    await update.message.reply_text(
        "📍 Location ပို့ပေးပါ (သို့) Lat,Lon ရိ