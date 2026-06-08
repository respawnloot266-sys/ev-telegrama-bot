import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ConversationHandler, CallbackQueryHandler, ContextTypes
)
import database as db
import charge_api

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPEN_CHARGE_MAP_API_KEY = os.getenv("OPEN_CHARGE_MAP_API_KEY")

# --- Conversation States ---
MODEL, CAP, RANGE, CHARGE_RATE = range(4)       # Registration
PCT = range(1)                                    # Battery Update
CHARGE_START_PCT, CHARGE_END_PCT = range(2)       # Charge Time

# --- ⚡ Charge Rate Database (ကားမော်ဒယ်အလိုက်) ---
CAR_CHARGE_RATES = {
    "tesla model 3": 250,
    "tesla model y": 250,
    "tesla model s": 200,
    "tesla model x": 200,
    "nissan leaf": 50,
    "hyundai ioniq 5": 220,
    "hyundai ioniq 6": 230,
    "kia ev6": 230,
    "bmw i4": 200,
    "volkswagen id.4": 135,
    "audi e-tron": 150,
    "chevrolet bolt": 55,
    "rivian r1t": 200,
    "ford mustang mach-e": 150,
}

def get_charge_rate(model: str) -> int:
    """ကားမော်ဒယ်ပေါ်မူတည်ပြီး charge rate ရယူတယ်။"""
    return CAR_CHARGE_RATES.get(model.lower().strip(), 50)

def detect_charge_rate_message(model: str) -> str:
    """ကားမော်ဒယ်ကို auto-detect လုပ်ပြီး rate message ပြတယ်။"""
    rate = get_charge_rate(model)
    if model.lower().strip() in CAR_CHARGE_RATES:
        return f"⚡ <b>{model}</b> အတွက် Charge Rate: <b>{rate} kW</b> (Auto-detected)"
    else:
        return f"⚡ Charge Rate: <b>{rate} kW</b> (Default — မသိသောမော်ဒယ်)"

# --- Main Menu ---
def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("🚗 Register Car", callback_data="reg_start"),
         InlineKeyboardButton("🔋 Update Battery", callback_data="upd_start")],
        [InlineKeyboardButton("📊 My Status", callback_data="stat"),
         InlineKeyboardButton("📜 History", callback_data="hist")],
        [InlineKeyboardButton("🔌 Find Station", callback_data="find"),
         InlineKeyboardButton("⏱️ Charge Time", callback_data="chargetime_start")],
        [InlineKeyboardButton("💡 Battery Tips", callback_data="tips")]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "⚡ <b>EV Helper Smart Assistant</b>\n\nကြိုဆိုပါတယ်! အောက်ပါခလုတ်များကို အသုံးပြု၍ စတင်နိုင်ပါပြီ။"
    if update.message:
        await update.message.reply_html(msg, reply_markup=get_main_menu())
    else:
        await update.callback_query.message.edit_text(msg, reply_markup=get_main_menu(), parse_mode="HTML")

# --- Callback Handler ---
# BUG FIX: button_handler သည် ConversationHandler entry_points နဲ့ ထပ်နေသည့် ပြဿနာကို
# ဖြေရှင်းရန် — button_handler မှ conversation states တွေ return မလုပ်တော့ဘဲ
# ConversationHandler တွေကိုသာ entry_point အဖြစ် သုံးတယ်။
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "stat":
        await status(update, context)
    elif query.data == "hist":
        await history(update, context)
    elif query.data == "find":
        await find_station(update, context)
    elif query.data == "tips":
        await tips(update, context)

# ================================================================
# REGISTRATION CONVERSATION
# ================================================================
async def reg_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    msg_obj = u.callback_query.message if u.callback_query else u.message
    if u.callback_query:
        await u.callback_query.answer()
    await msg_obj.reply_text("🚗 ကား Model အမည် ရိုက်ထည့်ပါ။ (ဥပမာ: Tesla Model 3)")
    return MODEL

async def reg_model(u: Update, c: ContextTypes.DEFAULT_TYPE):
    c.user_data["m"] = u.message.text
    rate = get_charge_rate(u.message.text)
    rate_info = detect_charge_rate_message(u.message.text)
    c.user_data["r"] = rate
    await u.message.reply_html(
        f"{rate_info}\n\n🔋 Battery Capacity (kWh) ရိုက်ထည့်ပါ။ (ဥပမာ: 75)"
    )
    return CAP

async def reg_cap(u: Update, c: ContextTypes.DEFAULT_TYPE):
    try:
        cap = float(u.message.text)
        c.user_data["c"] = cap
        await u.message.reply_text("🛣️ Full Range (km) ရိုက်ထည့်ပါ။ (ဥပမာ: 450)")
        return RANGE
    except ValueError:
        await u.message.reply_text("ဂဏန်းဖြင့်သာ ရိုက်ထည့်ပါ။ (ဥပမာ: 75)")
        return CAP

async def reg_range(u: Update, c: ContextTypes.DEFAULT_TYPE):
    try:
        full_range = float(u.message.text)
        db.save_user(
            u.effective_user.id,
            c.user_data["m"],
            c.user_data["c"],
            full_range,
            c.user_data.get("r", 50)
        )
        await u.message.reply_html(
            f"✅ <b>မှတ်ပုံတင်ပြီးပါပြီ။</b>\n"
            f"🚗 Model: {c.user_data['m']}\n"
            f"🔋 Capacity: {c.user_data['c']} kWh\n"
            f"🛣️ Range: {full_range} km\n"
            f"⚡ Charge Rate: {c.user_data.get('r', 50)} kW",
            reply_markup=get_main_menu()
        )
    except Exception as e:
        logger.error(f"Reg Error: {e}")
        await u.message.reply_text("Error ဖြစ်သွားပါတယ်။ ပြန်စမ်းကြည့်ပါ။")
    return ConversationHandler.END

# ================================================================
# BATTERY UPDATE CONVERSATION
# ================================================================
async def update_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    msg_obj = u.callback_query.message if u.callback_query else u.message
    if u.callback_query:
        await u.callback_query.answer()
    await msg_obj.reply_text("🔋 လက်ရှိ Battery % (0-100) ရိုက်ထည့်ပါ။")
    return PCT

async def update_done(u: Update, c: ContextTypes.DEFAULT_TYPE):
    try:
        pct = int(u.message.text)
        if not (0 <= pct <= 100):
            raise ValueError
        db.update_pct(u.effective_user.id, pct)

        # 🔔 BUG FIX + NEW FEATURE: Battery Warning
        warning = ""
        if pct <= 20:
            warning = "\n\n⚠️ <b>Warning:</b> Battery နည်းနေပါပြီ! အကောင်းဆုံး အားသွင်းပါ။"
        elif pct >= 90:
            warning = "\n\n💡 <b>Tip:</b> Battery 80% ကျော်ရင် အားသွင်းရပ်ဖို့ ကောင်းပါတယ်။"

        await u.message.reply_html(
            f"✅ Battery <b>{pct}%</b> အဖြစ် မှတ်သားပြီးပါပြီ။{warning}",
            reply_markup=get_main_menu()
        )
    except ValueError:
        await u.message.reply_text("0 မှ 100 အတွင်း ဂဏန်းဖြင့်သာ ရိုက်ထည့်ပါ။")
        return PCT
    return ConversationHandler.END

# ================================================================
# CHARGE TIME CONVERSATION
# ================================================================
async def chargetime_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    msg_obj = u.callback_query.message if u.callback_query else u.message
    if u.callback_query:
        await u.callback_query.answer()
    await msg_obj.reply_text("🔋 လက်ရှိ Battery ရာခိုင်နှုန်းကို ရိုက်ထည့်ပါ။ (ဥပမာ: 20)")
    return CHARGE_START_PCT

async def chargetime_get_start_pct(u: Update, c: ContextTypes.DEFAULT_TYPE):
    try:
        start_pct = int(u.message.text)
        if not (0 <= start_pct <= 100):
            raise ValueError
        c.user_data["charge_start_pct"] = start_pct
        await u.message.reply_text("🎯 အားသွင်းလိုသော Battery ရာခိုင်နှုန်းကို ရိုက်ထည့်ပါ။ (ဥပမာ: 80)")
        return CHARGE_END_PCT
    except ValueError:
        await u.message.reply_text("0 မှ 100 အတွင်း ဂဏန်းဖြင့်သာ ရိုက်ထည့်ပါ။")
        return CHARGE_START_PCT

async def chargetime_calculate(u: Update, c: ContextTypes.DEFAULT_TYPE):
    try:
        end_pct = int(u.message.text)
        if not (0 <= end_pct <= 100):
            raise ValueError

        start_pct = c.user_data["charge_start_pct"]
        if end_pct <= start_pct:
            await u.message.reply_text(f"အားသွင်းလိုသော % သည် လက်ရှိ % ({start_pct}%) ထက် ကြီးရပါမည်။")
            return CHARGE_END_PCT

        user = db.get_user(u.effective_user.id)
        if not user:
            await u.message.reply_text("/start မှ Register အရင်လုပ်ပါ။", reply_markup=get_main_menu())
            return ConversationHandler.END

        battery_capacity_kwh = float(user[2])
        # ⚡ NEW: ကားမော်ဒယ်အလိုက် charge rate auto-detect
        model = user[1]
        max_charge_rate_kw = get_charge_rate(model)

        kwh_needed = (end_pct - start_pct) / 100 * battery_capacity_kwh
        charge_time_hours = kwh_needed / max_charge_rate_kw
        charge_time_minutes = round(charge_time_hours * 60)

        hours = charge_time_minutes // 60
        minutes = charge_time_minutes % 60
        time_str = f"{hours} နာရီ {minutes} မိနစ်" if hours > 0 else f"{minutes} မိနစ်"

        await u.message.reply_html(
            f"⏱️ <b>အားသွင်းကြာချိန် ခန့်မှန်းချက်</b>\n\n"
            f"🚗 Model: {model}\n"
            f"⚡ Charge Rate: {max_charge_rate_kw} kW\n"
            f"🔋 {start_pct}% → {end_pct}%\n"
            f"🔌 လိုအပ်သော kWh: {kwh_needed:.1f} kWh\n"
            f"⏱️ ကြာချိန်: <b>{time_str}</b>",
            reply_markup=get_main_menu()
        )
        return ConversationHandler.END
    except ValueError:
        await u.message.reply_text("0 မှ 100 အတွင်း ဂဏန်းဖြင့်သာ ရိုက်ထည့်ပါ။")
        return CHARGE_END_PCT

# ================================================================
# STATUS
# ================================================================
async def status(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    user = db.get_user(uid)
    msg_obj = u.callback_query.message if u.callback_query else u.message

    if not user:
        return await msg_obj.reply_text("Register အရင်လုပ်ပါ။", reply_markup=get_main_menu())

    pct = user[4]
    current_range = (pct / 100) * float(user[3])

    # 🔔 Battery Warning
    if pct <= 20:
        battery_icon = "🔴"
        warning = "\n⚠️ Battery နည်းနေပါပြီ! အကောင်းဆုံး အားသွင်းပါ။"
    elif pct <= 50:
        battery_icon = "🟡"
        warning = ""
    else:
        battery_icon = "🟢"
        warning = ""

    await msg_obj.reply_html(
        f"📊 <b>လက်ရှိအခြေအနေ</b>\n\n"
        f"🚗 Model: {user[1]}\n"
        f"{battery_icon} Battery: <b>{pct}%</b>{warning}\n"
        f"🛣️ မောင်းနိုင်သည့်ခရီး: <b>{current_range:.1f} km</b>\n"
        f"⚡ Charge Rate: {get_charge_rate(user[1])} kW",
        reply_markup=get_main_menu()
    )

# ================================================================
# HISTORY — 📈 ASCII Chart ပြ
# ================================================================
async def history(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    logs = db.get_logs(uid)
    msg_obj = u.callback_query.message if u.callback_query else u.message

    if not logs:
        return await msg_obj.reply_text("မှတ်တမ်း မရှိပါ။", reply_markup=get_main_menu())

    # 📈 ASCII Bar Chart (Telegram မှာ image မပြနိုင်သောကြောင့်)
    msg = "📜 <b>Battery မှတ်တမ်းများ</b>\n\n"
    msg += "<code>"
    recent_logs = logs[-10:]  # နောက်ဆုံး 10 ခု
    for log in recent_logs:
        date_str = str(log[4])[:10]
        pct_val = int(log[3])
        bar_len = pct_val // 5  # 20 chars max
        bar = "█" * bar_len + "░" * (20 - bar_len)
        msg += f"{date_str} |{bar}| {pct_val}%\n"
    msg += "</code>"

    await msg_obj.reply_html(msg, reply_markup=get_main_menu())

# ================================================================
# FIND STATION — 🗺️ Google Maps Link တိုက်ရိုက်
# ================================================================
async def find_station(u: Update, c: ContextTypes.DEFAULT_TYPE):
    msg_obj = u.callback_query.message if u.callback_query else u.message
    kb = [[KeyboardButton("📍 တည်နေရာပေးပို့ရန်", request_location=True)]]
    await msg_obj.reply_text(
        "အနီးဆုံး Charging Station ရှာရန် တည်နေရာကို ပေးပို့ပါ။",
        reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True)
    )

async def location_handler(u: Update, c: ContextTypes.DEFAULT_TYPE):
    msg_obj = u.message

    if not OPEN_CHARGE_MAP_API_KEY:
        await msg_obj.reply_text("API Key မရှိသောကြောင့် Station ရှာမရပါ။", reply_markup=get_main_menu())
        return

    lat = u.message.location.latitude
    lon = u.message.location.longitude

    await msg_obj.reply_text("🔍 အားသွင်းစခန်းများ ရှာဖွေနေပါသည်...", reply_markup=ReplyKeyboardRemove())

    stations = charge_api.get_nearby_charging_stations(lat, lon, distance=10, max_results=5)

    if stations:
        msg = "🔌 <b>အနီးဆုံး အားသွင်းစခန်းများ:</b>\n\n"
        for i, station in enumerate(stations):
            title = station.get("addressInfo", {}).get("title", "N/A")
            address = station.get("addressInfo", {}).get("addressLine1", "")
            distance = station.get("addressInfo", {}).get("distance", 0)
            s_lat = station.get("addressInfo", {}).get("latitude")
            s_lon = station.get("addressInfo", {}).get("longitude")

            # 🗺️ NEW: Google Maps Direct Link
            maps_link = f"https://www.google.com/maps/dir/?api=1&destination={s_lat},{s_lon}"
            navigate_link = f"https://www.google.com/maps/search/?api=1&query={s_lat},{s_lon}"

            msg += f"{i+1}. <b>{title}</b> ({distance:.1f} km)\n"
            if address:
                msg += f"   📍 {address}\n"

            connections = station.get("connections", [])
            if connections:
                conn_details = []
                for conn in connections:
                    conn_type = conn.get("connectionType", {}).get("title", "N/A")
                    power_kw = conn.get("powerKW", "N/A")
                    conn_details.append(f"{conn_type} ({power_kw}kW)")
                msg += f"   ⚡ {', '.join(conn_details)}\n"

            msg += f"   <a href=\"{maps_link}\">🗺️ Navigate</a> | <a href=\"{navigate_link}\">📌 View on Map</a>\n\n"

        await msg_obj.reply_html(msg, disable_web_page_preview=True, reply_markup=get_main_menu())
    else:
        await msg_obj.reply_text("သင့်အနီးအနားတွင် Station ရှာမတွေ့ပါ။", reply_markup=get_main_menu())

# ================================================================
# TIPS
# ================================================================
async def tips(u: Update, c: ContextTypes.DEFAULT_TYPE):
    msg_obj = u.callback_query.message if u.callback_query else u.message
    await msg_obj.reply_html(
        "💡 <b>EV Battery Tips:</b>\n\n"
        "• 🟢 Battery <b>20%-80%</b> ကြားထားပါ — lifetime တိုးတယ်။\n"
        "• 🌙 ညဘက် (Off-peak) အားသွင်းရင် စျေးသက်သာပါတယ်။\n"
        "• ❄️ အအေးချိန်မှာ range ကျတတ်သည် — သတိထားပါ။\n"
        "• ⚡ DC Fast Charge ကို မကြာမကြာ မသုံးပါနဲ့ — battery ထိခိုက်နိုင်တယ်။\n"
        "• 🔄 တစ်လတစ်ကြိမ် 100% အထိ အားသွင်းပြီး calibrate လုပ်ပါ။",
        reply_markup=get_main_menu()
    )

# ================================================================
# OFF-PEAK REMINDER (JobQueue)
# ================================================================
async def send_off_peak_reminder(context: ContextTypes.DEFAULT_TYPE):
    user_ids = db.get_all_user_ids()
    for user_id in user_ids:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="🌙 Off-Peak Reminder: ညဘက် အားသွင်းဖို့ မမေ့ပါနဲ့! Battery 80% ထိသာ အားသွင်းပါ။"
            )
        except Exception as e:
            logger.error(f"Reminder failed for {user_id}: {e}")

# ================================================================
# CANCEL
# ================================================================
async def cancel(u: Update, c: ContextTypes.DEFAULT_TYPE):
    await u.message.reply_text("လုပ်ဆောင်ချက်ကို ဖျက်သိမ်းလိုက်ပါပြီ။", reply_markup=get_main_menu())
    return ConversationHandler.END

# ================================================================
# MAIN
# ================================================================
def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN မရှိပါ!")
        return

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # JobQueue — Off-Peak Reminder (ည ၁၀ နာရी တိုင်း)
    job_queue = app.job_queue
    from datetime import time as dtime
    job_queue.run_daily(
        send_off_peak_reminder,
        time=dtime(hour=22, minute=0),  # ည ၁၀ နာရི
        name="off_peak_reminder"
    )

    # --- Conversation Handlers ---
    reg_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(reg_start, pattern="^reg_start$"),
            CommandHandler("register", reg_start)
        ],
        states={
            MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_model)],
            CAP:   [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_cap)],
            RANGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_range)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    upd_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(update_start, pattern="^upd_start$"),
            CommandHandler("update", update_start)
        ],
        states={
            PCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_done)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    chargetime_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(chargetime_start, pattern="^chargetime_start$"),
            CommandHandler("chargetime", chargetime_start)
        ],
        states={
            CHARGE_START_PCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, chargetime_get_start_pct)],
            CHARGE_END_PCT:   [MessageHandler(filters.TEXT & ~filters.COMMAND, chargetime_calculate)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    # --- Handlers Register ---
    app.add_handler(CommandHandler("start", start))
    app.add_handler(reg_conv)
    app.add_handler(upd_conv)
    app.add_handler(chargetime_conv)
    app.add_handler(CallbackQueryHandler(button_handler))  # stat, hist, find, tips
    app.add_handler(MessageHandler(filters.LOCATION, location_handler))

    print("✅ EV Helper Bot running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
