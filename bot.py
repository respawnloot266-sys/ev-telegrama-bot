import logging
import os
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, ConversationHandler, ContextTypes
)

# --- Configuration ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# --- Conversation States ---
CAR_MODEL, BATTERY_CAPACITY, FULL_CHARGE_RANGE = range(3)
CURRENT_BATTERY = range(1)
START_PCT, END_PCT, STATION_NAME = range(3)

# --- Database Mock (သင့် database.py နဲ့ ချိတ်ဆက်ဖို့ လိုအပ်ပါက ပြင်နိုင်ပါတယ်) ---
# အခုက bot အလုပ်လုပ်ဖို့အတွက် အခြေခံ logic တွေကို ထည့်ပေးထားပါတယ်
user_db = {} 

# --- Command Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_html(
        "⚡ <b>EV Helper Bot မှ ကြိုဆိုပါတယ်!</b>\n\n"
        "အောက်ပါ commands များကို အသုံးပြုနိုင်ပါသည် -\n"
        "/register - ကားအချက်အလက် မှတ်ပုံတင်ရန်\n"
        "/battery - လက်ရှိ battery update လုပ်ရန်\n"
        "/findstation - အနီးဆုံး အားသွင်းစခန်း ရှာရန်\n"
        "/chargetime - အားသွင်းကြာချိန် တွက်ရန်\n"
        "/tips - Battery tips များ ဖတ်ရန်\n"
        "/cancel - လုပ်ဆောင်ချက်များကို ဖျက်သိမ်းရန်"
    )

# --- Registration Flow ---
async def register_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚗 ကား Model အမည် ရိုက်ထည့်ပါ (ဥပမာ: Tesla Model 3)")
    return CAR_MODEL

async def register_car_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["car_model"] = update.message.text
    await update.message.reply_text("🔋 Battery Capacity (kWh) ကို ဂဏန်းဖြင့် ရိုက်ထည့်ပါ (ဥပမာ: 60)")
    return BATTERY_CAPACITY

async def register_battery_capacity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["cap"] = update.message.text
    await update.message.reply_text("🛣️ Full Charge Range (km) ကို ရိုက်ထည့်ပါ (ဥပမာ: 450)")
    return FULL_CHARGE_RANGE

async def register_full_charge_range(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_db[user_id] = {
        "model": context.user_data["car_model"],
        "cap": context.user_data["cap"],
        "range": update.message.text
    }
    await update.message.reply_text("✅ မှတ်ပုံတင်ခြင်း အောင်မြင်ပါသည်။ /battery ဖြင့် battery update လုပ်နိုင်ပါပြီ။")
    return ConversationHandler.END

# --- Battery Update & Alert ---
async def battery_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔋 လက်ရှိ Battery ရာခိုင်နှုန်းကို ရိုက်ထည့်ပါ (0-100)")
    return CURRENT_BATTERY

async def battery_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        pct = int(update.message.text)
        if pct <= 20:
            await update.message.reply_text(f"⚠️ <b>သတိပေးချက်:</b> Battery {pct}% သာ ကျန်ပါတော့သည်။ အနီးဆုံးစခန်းကို /findstation ဖြင့် ရှာပါ။", parse_mode='HTML')
        else:
            await update.message.reply_text(f"✅ Battery {pct}% အဖြစ် မှတ်သားပြီးပါပြီ။")
    except:
        await update.message.reply_text("ဂဏန်းဖြင့်သာ ရိုက်ထည့်ပါ။")
    return ConversationHandler.END

# --- Find Station (Location) ---
async def find_station_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[KeyboardButton("📍 လက်ရှိတည်နေရာ ပေးပို့ရန်", request_location=True)]]
    markup = ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("🔌 အနီးဆုံးစခန်းများ ရှာရန် သင့်တည်နေရာကို ပေးပို့ပါ။", reply_markup=markup)

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ဒီနေရာမှာ API နဲ့ ချိတ်ဆက်ရမှာပါ၊ အခုက ဥပမာအနေနဲ့ပဲ ပြထားပါတယ်
    await update.message.reply_text(
        "🔌 <b>သင့်အနီးရှိ အားသွင်းစခန်းများ</b>\n\n"
        "1. Earth EV Station (1.2 km)\n"
        "2. Charge+ Station (2.5 km)\n"
        "3. MG Supercharge (3.1 km)", 
        parse_mode='HTML', reply_markup=ReplyKeyboardRemove()
    )

# --- Tips ---
async def tips_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tips_text = (
        "💡 <b>EV Battery Tips:</b>\n\n"
        "• Battery ကို 20% အောက် မကျအောင် ထိန်းပါ။\n"
        "• ပုံမှန်အားဖြင့် 80% အထိသာ အားသွင်းခြင်းက battery သက်တမ်းကို ရှည်စေပါသည်။\n"
        "• နေပူထဲတွင် ကားကို အကြာကြီး ရပ်မထားပါနှင့်။\n"
        "• ညဘက် (Off-peak) အားသွင်းခြင်းက မီးခစျေးနှုန်း သက်သာစေပါသည်။"
    )
    await update.message.reply_text(tips_text, parse_mode='HTML')

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("လုပ်ဆောင်ချက်ကို ဖျက်သိမ်းလိုက်ပါပြီ။", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# --- Main Function ---
def main():
    if not TELEGRAM_BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN is missing!")
        return

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tips", tips_cmd))
    app.add_handler(CommandHandler("findstation", find_station_cmd))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))

    # Register Conversation
    reg_conv = ConversationHandler(
        entry_points=[CommandHandler("register", register_start)],
        states={
            CAR_MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_car_model)],
            BATTERY_CAPACITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_battery_capacity)],
            FULL_CHARGE_RANGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_full_charge_range)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Battery Conversation
    batt_conv = ConversationHandler(
        entry_points=[CommandHandler("battery", battery_start)],
        states={
            CURRENT_BATTERY: [MessageHandler(filters.TEXT & ~filters.COMMAND, battery_update)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(reg_conv)
    app.add_handler(batt_conv)

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
