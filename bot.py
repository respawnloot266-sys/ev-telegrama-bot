import os, logging
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes
from database import save_user, get_user, update_pct, get_logs

# --- Configuration ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# --- Conversation States ---
MODEL, CAP, RANGE = range(3)
PCT = range(1)
START_P, END_P = range(2)

# --- Basic Commands ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_html(
        "⚡ <b>EV Helper Super Bot</b> မှ ကြိုဆိုပါတယ်!\n\n"
        "<b>အဓိက Commands များ:</b>\n"
        "/register - ကားအချက်အလက် မှတ်ပုံတင်ရန်\n"
        "/update - လက်ရှိ Battery % ကို update လုပ်ရန်\n"
        "/status - လက်ရှိအခြေအနေနှင့် ခရီးမိုင် တွက်ချက်ရန်\n"
        "/history - ပို့ခဲ့သမျှ Battery မှတ်တမ်းများကြည့်ရန်\n"
        "/findstation - အနီးဆုံး အားသွင်းစခန်းရှာရန်\n"
        "/chargetime - အားသွင်းကြာချိန် တွက်ချက်ရန်\n"
        "/tips - Battery ထိန်းသိမ်းနည်းများ ဖတ်ရန်\n"
        "/cancel - လုပ်ဆောင်ချက်များကို ဖျက်သိမ်းရန်"
    )

# --- 1. Registration Flow ---
async def reg_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    await u.message.reply_text("🚗 ကား Model အမည် ရိုက်ထည့်ပါ (ဥပမာ: Tesla Model 3)")
    return MODEL

async def reg_model(u: Update, c: ContextTypes.DEFAULT_TYPE):
    c.user_data["m"] = u.message.text
    await u.message.reply_text("🔋 Battery Capacity (kWh) ကို ဂဏန်းဖြင့် ရိုက်ထည့်ပါ (ဥပမာ: 60)")
    return CAP

async def reg_cap(u: Update, c: ContextTypes.DEFAULT_TYPE):
    c.user_data["c"] = u.message.text
    await u.message.reply_text("🛣️ Full Charge Range (km) ကို ရိုက်ထည့်ပါ (ဥပမာ: 450)")
    return RANGE

async def reg_range(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    save_user(uid, c.user_data["m"], c.user_data["c"], u.message.text)
    await u.message.reply_text("✅ မှတ်ပုံတင်ခြင်း အောင်မြင်ပါသည်။ /status ကို နှိပ်ကြည့်ပါ။")
    return ConversationHandler.END

# --- 2. Battery Update Flow ---
async def update_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    await u.message.reply_text("🔋 လက်ရှိ Battery ရာခိုင်နှုန်းကို ရိုက်ထည့်ပါ (0-100)")
    return PCT

async def update_done(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    try:
        pct = int(u.message.text)
        update_pct(uid, pct)
        if pct <= 20:
            await u.message.reply_html(f"✅ မှတ်သားပြီးပါပြီ။\n⚠️ <b>သတိပေးချက်:</b> Battery {pct}% သာ ကျန်ပါတော့သည်။ /findstation ဖြင့် စခန်းရှာပါ။")
        else:
            await u.message.reply_text(f"✅ Battery {pct}% အဖြစ် မှတ်တမ်းတင်ပြီးပါပြီ။")
    except:
        await u.message.reply_text("ဂဏန်းဖြင့်သာ ရိုက်ထည့်ပါ။")
    return ConversationHandler.END

# --- 3. Status & History ---
async def status(u: Update, c: ContextTypes.DEFAULT_TYPE):
    user = get_user(u.effective_user.id)
    if not user: return await u.message.reply_text("/register ကို အရင်နှိပ်ပါ။")
    
    pct = user[4]
    frange = float(user[3])
    current_range = (pct / 100) * frange
    
    await u.message.reply_html(
        f"📊 <b>လက်ရှိအခြေအနေ</b>\n\n"
        f"ကား Model: {user[1]}\n"
        f"Battery: {pct}%\n"
        f"🛣️ ခန့်မှန်းခြေမောင်းနိုင်သည့်ခရီး: <b>{current_range:.1f} km</b>"
    )

async def history(u: Update, c: ContextTypes.DEFAULT_TYPE):
    logs = get_logs(u.effective_user.id)
    if not logs: return await u.message.reply_text("မှတ်တမ်း မရှိသေးပါ။")
    
    msg = "📜 <b>နောက်ဆုံးပို့ခဲ့သော မှတ်တမ်းများ:</b>\n\n"
    for log in logs[:10]:
        msg += f"• {log[3][:16]} - <b>{log[2]}%</b>\n"
    await u.message.reply_html(msg)

# --- 4. Find Station & Tools ---
async def find_station(u: Update, c: ContextTypes.DEFAULT_TYPE):
    kb = [[KeyboardButton("📍 လက်ရှိတည်နေရာ ပေးပို့ရန်", request_location=True)]]
    await u.message.reply_text("အနီးဆုံးစခန်းရှာရန် တည်နေရာကို ပေးပို့ပါ။", 
        reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True))

async def handle_location(u: Update, c: ContextTypes.DEFAULT_TYPE):
    await u.message.reply_html(
        "🔌 <b>သင့်အနီးရှိ အားသွင်းစခန်းများ:</b>\n\n"
        "1. Earth EV Station (1.2 km)\n"
        "2. Charge+ Station (2.5 km)\n"
        "3. MG Supercharge (3.1 km)", reply_markup=ReplyKeyboardRemove()
    )

async def chargetime_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    await u.message.reply_text("ဘယ်နှစ် % ကနေ စသွင်းမှာလဲ? (ဥပမာ: 20)")
    return START_P

async def chargetime_end(u: Update, c: ContextTypes.DEFAULT_TYPE):
    c.user_data["sp"] = u.message.text
    await u.message.reply_text("ဘယ်နှစ် % အထိ သွင်းမှာလဲ? (ဥပမာ: 80)")
    return END_P

async def chargetime_calc(u: Update, c: ContextTypes.DEFAULT_TYPE):
    user = get_user(u.effective_user.id)
    if not user: return await u.message.reply_text("/register အရင်လုပ်ပါ။")
    try:
        sp, ep = int(c.user_data["sp"]), int(u.message.text)
        cap = float(user[2])
        hours = ((ep - sp) / 100 * cap) / 7 # 7kW Charger
        await u.message.reply_html(f"⏳ {sp}% မှ {ep}% အထိ အားသွင်းရန် <b>{hours:.1f} နာရီ</b> ခန့် ကြာပါမည်။ (7kW AC ဖြင့်)")
    except:
        await u.message.reply_text("မှားယွင်းမှုရှိပါသည်။ ပြန်စမ်းကြည့်ပါ။")
    return ConversationHandler.END

async def tips(u: Update, c: ContextTypes.DEFAULT_TYPE):
    await u.message.reply_html("💡 <b>EV Tips:</b>\n• Battery 20%-80% ကြားထားပါ။\n• ညဘက်အားသွင်းရင် စျေးသက်သာပါတယ်။\n• တာယာလေဖိအား မှန်ပါစေ။")

async def cancel(u: Update, c: ContextTypes.DEFAULT_TYPE):
    await u.message.reply_text("လုပ်ဆောင်ချက်ကို ဖျက်သိမ်းလိုက်ပါပြီ။", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# --- Main ---
def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Conversations
    reg_conv = ConversationHandler(
        entry_points=[CommandHandler("register", reg_start)],
        states={
            MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_model)],
            CAP: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_cap)],
            RANGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_range)],
        }, fallbacks=[CommandHandler("cancel", cancel)]
    )
    
    upd_conv = ConversationHandler(
        entry_points=[CommandHandler("update", update_start)],
        states={PCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_done)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    
    calc_conv = ConversationHandler(
        entry_points=[CommandHandler("chargetime", chargetime_start)],
        states={
            START_P: [MessageHandler(filters.TEXT & ~filters.COMMAND, chargetime_end)],
            END_P: [MessageHandler(filters.TEXT & ~filters.COMMAND, chargetime_calc)],
        }, fallbacks=[CommandHandler("cancel", cancel)]
    )

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CommandHandler("findstation", find_station))
    app.add_handler(CommandHandler("tips", tips))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_handler(reg_conv)
    app.add_handler(upd_conv)
    app.add_handler(calc_conv)
    
    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
