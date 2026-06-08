import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackQueryHandler, ContextTypes
import database as db

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# States
MODEL, CAP, RANGE = range(3)
PCT = range(1)

# --- Main Menu (Buttons) ---
def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("🚗 Register Car", callback_data='reg'),
         InlineKeyboardButton("🔋 Update Battery", callback_data='upd')],
        [InlineKeyboardButton("📊 My Status", callback_data='stat'),
         InlineKeyboardButton("📜 History", callback_data='hist')],
        [InlineKeyboardButton("🔌 Find Station", callback_data='find'),
         InlineKeyboardButton("💡 Battery Tips", callback_data='tips')]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "⚡ <b>EV Helper Smart Assistant</b>\n\nကြိုဆိုပါတယ်! အောက်ပါခလုတ်များကို အသုံးပြု၍ စတင်နိုင်ပါပြီ။"
    if update.message:
        await update.message.reply_html(msg, reply_markup=get_main_menu())
    else:
        await update.callback_query.message.edit_text(msg, reply_markup=get_main_menu(), parse_mode='HTML')

# --- Callback Handler (Buttons နှိပ်တာကို ကိုင်တွယ်ခြင်း) ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'reg':
        await query.message.reply_text("🚗 ကား Model အမည် (ဥပမာ: Tesla Model 3)?")
        return MODEL # ဒီနေရာမှာ Conversation စဖို့ လိုအပ်ပါက အောက်က handler တွေနဲ့ ချိတ်ရပါမယ်
    elif query.data == 'upd':
        await query.message.reply_text("🔋 လက်ရှိ Battery % (0-100)?")
    elif query.data == 'stat':
        await status(update, context)
    elif query.data == 'hist':
        await history(update, context)
    elif query.data == 'find':
        await find_station(update, context)
    elif query.data == 'tips':
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
    db.save_user(u.effective_user.id, c.user_data["m"], c.user_data["c"], u.message.text)
    await u.message.reply_text("✅ မှတ်ပုံတင်ပြီးပါပြီ။", reply_markup=get_main_menu())
    return ConversationHandler.END

# --- Battery Update ---
async def update_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    await u.message.reply_text("🔋 လက်ရှိ Battery %?")
    return PCT

async def update_done(u: Update, c: ContextTypes.DEFAULT_TYPE):
    try:
        pct = int(u.message.text)
        db.update_pct(u.effective_user.id, pct)
        await u.message.reply_text(f"✅ Battery {pct}% အဖြစ် မှတ်သားပြီးပါပြီ။", reply_markup=get_main_menu())
    except:
        await u.message.reply_text("ဂဏန်းဖြင့်သာ ရိုက်ထည့်ပါ။")
    return ConversationHandler.END

# --- Tools (Modified for Callback) ---
async def status(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    user = db.get_user(uid)
    msg_obj = u.callback_query.message if u.callback_query else u.message
    
    if not user: 
        return await msg_obj.reply_text("/register အရင်လုပ်ပါ။")
    
    pct = user[4]
    current_range = (pct / 100) * float(user[3])
    await msg_obj.reply_html(f"📊 <b>အခြေအနေ</b>\nModel: {user[1]}\nBattery: {pct}%\n🛣️ မောင်းနိုင်သည့်ခရီး: {current_range:.1f} km")

async def history(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    logs = db.get_logs(uid)
    msg_obj = u.callback_query.message if u.callback_query else u.message
    
    if not logs: return await msg_obj.reply_text("မှတ်တမ်း မရှိပါ။")
    msg = "📜 <b>မှတ်တမ်းများ:</b>\n"
    for log in logs: msg += f"• {str(log[4])[:16]} - {log[3]}%\n"
    await msg_obj.reply_html(msg)

async def find_station(u: Update, c: ContextTypes.DEFAULT_TYPE):
    msg_obj = u.callback_query.message if u.callback_query else u.message
    kb = [[KeyboardButton("📍 တည်နေရာပေးပို့ရန်", request_location=True)]]
    await msg_obj.reply_text("အနီးဆုံးစခန်းရှာရန် တည်နေရာပေးပို့ပါ", 
        reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True))

async def tips(u: Update, c: ContextTypes.DEFAULT_TYPE):
    msg_obj = u.callback_query.message if u.callback_query else u.message
    await msg_obj.reply_html("💡 <b>EV Tips:</b>\n• Battery 20%-80% ကြားထားပါ။\n• ညဘက်အားသွင်းရင် စျေးသက်သာပါတယ်။")

async def cancel(u: Update, c: ContextTypes.DEFAULT_TYPE):
    await u.message.reply_text("ဖျက်သိမ်းလိုက်ပါပြီ။", reply_markup=get_main_menu())
    return ConversationHandler.END

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.LOCATION, lambda u, c: u.message.reply_text("🔌 အနီးဆုံးစခန်း: Earth EV (1.2km)", reply_markup=get_main_menu())))
    
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
