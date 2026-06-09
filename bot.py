import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ConversationHandler, CallbackQueryHandler, ContextTypes
)
import database as db
import charge_api
import utils

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# --- States ---
CAR_NAME, MODEL, CAP, RANGE = range(4)
PCT = range(1)
CHARGE_START_PCT, CHARGE_END_PCT = range(2)

CAR_CHARGE_RATES = {
    "tesla model 3": 250, "tesla model y": 250,
    "tesla model s": 200, "tesla model x": 200,
    "nissan leaf": 50, "hyundai ioniq 5": 220,
    "hyundai ioniq 6": 230, "kia ev6": 230,
    "bmw i4": 200, "volkswagen id.4": 135,
    "audi e-tron": 150, "chevrolet bolt": 55,
    "ford mustang mach-e": 150, "toyota bz3x": 150,
    "toyota bz4x": 150, "mg zs ev": 90,
}

def get_charge_rate(model):
    return CAR_CHARGE_RATES.get(model.lower().strip(), 50)

def get_lang(uid):
    return db.get_language(uid)

# ================================================================
# MENUS
# ================================================================
def get_main_menu(lang="MM"):
    if lang == "MM":
        keyboard = [
            [InlineKeyboardButton("🚗 ကား မှတ်ပုံတင်", callback_data="reg_start"),
             InlineKeyboardButton("🔋 Battery အပ်ဒိတ်", callback_data="upd_start")],
            [InlineKeyboardButton("📊 အခြေအနေ", callback_data="stat"),
             InlineKeyboardButton("📜 မှတ်တမ်း", callback_data="hist")],
            [InlineKeyboardButton("🔌 Station ရှာ", callback_data="find"),
             InlineKeyboardButton("⏱️ အားသွင်းကြာချိန်", callback_data="chargetime_start")],
            [InlineKeyboardButton("🚗 ကားများ", callback_data="cars"),
             InlineKeyboardButton("📍 Favorites", callback_data="favs")],
            [InlineKeyboardButton("🌐 EN/MM", callback_data="lang"),
             InlineKeyboardButton("💡 Tips", callback_data="tips")],
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("🚗 Register Car", callback_data="reg_start"),
             InlineKeyboardButton("🔋 Update Battery", callback_data="upd_start")],
            [InlineKeyboardButton("📊 My Status", callback_data="stat"),
             InlineKeyboardButton("📜 History", callback_data="hist")],
            [InlineKeyboardButton("🔌 Find Station", callback_data="find"),
             InlineKeyboardButton("⏱️ Charge Time", callback_data="chargetime_start")],
            [InlineKeyboardButton("🚗 My Cars", callback_data="cars"),
             InlineKeyboardButton("📍 Favorites", callback_data="favs")],
            [InlineKeyboardButton("🌐 EN/MM", callback_data="lang"),
             InlineKeyboardButton("💡 Tips", callback_data="tips")],
        ]
    return InlineKeyboardMarkup(keyboard)

def back_button(lang="MM"):
    """🔙 Back button — နေရာတိုင်းမှာ ပါအောင်"""
    label = "🔙 Menu သို့ပြန်" if lang == "MM" else "🔙 Back to Menu"
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, callback_data="back_menu")]])

def back_row(lang="MM"):
    label = "🔙 Menu သို့ပြန်" if lang == "MM" else "🔙 Back to Menu"
    return [InlineKeyboardButton(label, callback_data="back_menu")]

# ================================================================
# /start — မှတ်ပုံတင်ပြီးသား user ကို ကြိုဆိုစာ ပြ
# ================================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.get_or_create_user(uid)
    lang = get_lang(uid)
    car = db.get_active_car(uid)
    name = update.effective_user.first_name or ""

    if car:
        pct = car[7]
        icon = utils.get_battery_icon(pct)
        if lang == "MM":
            msg = (f"👋 ပြန်လာတာ ကြိုဆိုပါတယ်, <b>{name}</b>!\n\n"
                   f"🚗 လက်ရှိကား: <b>{car[2]}</b> ({car[3]})\n"
                   f"{icon} Battery: <b>{pct}%</b>\n\n"
                   f"ဘာကူညီရမလဲ?")
        else:
            msg = (f"👋 Welcome back, <b>{name}</b>!\n\n"
                   f"🚗 Active car: <b>{car[2]}</b> ({car[3]})\n"
                   f"{icon} Battery: <b>{pct}%</b>\n\n"
                   f"How can I help you?")
    else:
        if lang == "MM":
            msg = (f"⚡ <b>EV Helper Smart Assistant</b>\n\n"
                   f"မင်္ဂလာပါ, <b>{name}</b>!\n"
                   f"အောက်မှ ကား မှတ်ပုံတင်ပြီး စတင်ပါ။")
        else:
            msg = (f"⚡ <b>EV Helper Smart Assistant</b>\n\n"
                   f"Hello, <b>{name}</b>!\n"
                   f"Please register your car to get started.")

    if update.message:
        await update.message.reply_html(msg, reply_markup=get_main_menu(lang))
    else:
        await update.callback_query.message.edit_text(msg, reply_markup=get_main_menu(lang), parse_mode="HTML")

# ================================================================
# BUTTON HANDLER
# ================================================================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    lang = get_lang(uid)

    if query.data in ("back_menu", "start"):
        await start(update, context)
    elif query.data == "stat":
        await status(update, context)
    elif query.data == "hist":
        await history(update, context)
    elif query.data == "find":
        await find_station(update, context)
    elif query.data == "tips":
        await tips(update, context)
    elif query.data == "cars":
        await show_cars(update, context)
    elif query.data == "favs":
        await show_favorites(update, context)
    elif query.data == "lang":
        await lang_menu(update, context)
    elif query.data == "lang_mm":
        db.set_language(uid, "MM")
        await query.message.reply_html(utils.t("MM", "lang_set"), reply_markup=get_main_menu("MM"))
    elif query.data == "lang_en":
        db.set_language(uid, "EN")
        await query.message.reply_html(utils.t("EN", "lang_set"), reply_markup=get_main_menu("EN"))
    elif query.data.startswith("switch_car_"):
        car_id = int(query.data.replace("switch_car_", ""))
        db.switch_car(uid, car_id)
        await query.answer("✅ ကား ပြောင်းပြီးပါပြီ။" if lang == "MM" else "✅ Car switched!", show_alert=True)
        await show_cars(update, context)
    elif query.data.startswith("del_car_"):
        car_id = int(query.data.replace("del_car_", ""))
        db.delete_car(uid, car_id)
        await query.answer("🗑️ ဖျက်ပြီးပါပြီ။" if lang == "MM" else "🗑️ Deleted!", show_alert=True)
        await show_cars(update, context)
    elif query.data.startswith("del_fav_"):
        fav_id = int(query.data.replace("del_fav_", ""))
        db.delete_favorite(uid, fav_id)
        await query.answer(utils.t(lang, "deleted"), show_alert=True)
        await show_favorites(update, context)
    elif query.data.startswith("save_fav_"):
        parts = query.data.split("|")
        db.add_favorite(uid, parts[1], parts[2], float(parts[3]), float(parts[4]))
        await query.answer(utils.t(lang, "saved"), show_alert=True)

# ================================================================
# LANGUAGE MENU
# ================================================================
async def lang_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update.effective_user.id)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🇲🇲 မြန်မာ", callback_data="lang_mm"),
         InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
        back_row(lang)
    ])
    await update.callback_query.message.reply_text(
        "🌐 ဘာသာစကား ရွေးပါ / Select language:", reply_markup=kb
    )

# ================================================================
# REGISTRATION
# ================================================================
async def reg_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    msg_obj = u.callback_query.message if u.callback_query else u.message
    if u.callback_query:
        await u.callback_query.answer()
    lang = get_lang(u.effective_user.id)
    prompt = "🚗 ကားအမည် ရိုက်ပါ။\n(ဥပမာ: ကျွန်တော့်ကား)" if lang == "MM" else "🚗 Enter a name for this car.\n(e.g. My Tesla)"
    await msg_obj.reply_text(prompt)
    return CAR_NAME

async def reg_car_name(u: Update, c: ContextTypes.DEFAULT_TYPE):
    c.user_data["car_name"] = u.message.text.strip()
    lang = get_lang(u.effective_user.id)
    await u.message.reply_text(
        "🚗 Model ရိုက်ပါ။ (ဥပမာ: Toyota bZ3X)" if lang == "MM"
        else "🚗 Enter car model. (e.g. Tesla Model 3)"
    )
    return MODEL

async def reg_model(u: Update, c: ContextTypes.DEFAULT_TYPE):
    model = u.message.text.strip()
    c.user_data["model"] = model
    rate = get_charge_rate(model)
    c.user_data["rate"] = rate
    lang = get_lang(u.effective_user.id)
    detected = f"⚡ Charge Rate: <b>{rate} kW</b> (Auto-detected)\n\n"
    await u.message.reply_html(
        detected + ("🔋 Battery Capacity (kWh) ရိုက်ပါ။ (ဥပမာ: 72.8)" if lang == "MM"
                    else "🔋 Enter battery capacity in kWh. (e.g. 72.8)")
    )
    return CAP

async def reg_cap(u: Update, c: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(u.effective_user.id)
    try:
        c.user_data["cap"] = float(u.message.text.strip())
        await u.message.reply_text(
            "🛣️ Full Range (km) ရိုက်ပါ။ (ဥပမာ: 450)" if lang == "MM"
            else "🛣️ Enter full range in km. (e.g. 450)"
        )
        return RANGE
    except ValueError:
        await u.message.reply_text(
            "❌ ဂဏန်းသာ ရိုက်ပါ။ (ဥပမာ: 72.8)" if lang == "MM"
            else "❌ Please enter a number only. (e.g. 72.8)"
        )
        return CAP

async def reg_range(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    try:
        full_range = float(u.message.text.strip())
        db.add_car(uid, c.user_data["car_name"], c.user_data["model"],
                   c.user_data["cap"], full_range, c.user_data.get("rate", 50))
        await u.message.reply_html(
            f"✅ <b>မှတ်ပုံတင်ပြီးပါပြီ။</b>\n"
            f"🚗 {c.user_data['car_name']} ({c.user_data['model']})\n"
            f"🔋 {c.user_data['cap']} kWh | 🛣️ {full_range} km\n"
            f"⚡ {c.user_data.get('rate', 50)} kW",
            reply_markup=get_main_menu(lang)
        )
    except ValueError:
        await u.message.reply_text(
            "❌ ဂဏန်းသာ ရိုက်ပါ။ (ဥပမာ: 450)" if lang == "MM"
            else "❌ Please enter a number only. (e.g. 450)"
        )
        return RANGE
    except Exception as e:
        logger.error(f"Reg Error: {e}")
        await u.message.reply_text(
            "❌ Error ဖြစ်သွားပါတယ်။ /start မှ ပြန်စပါ။" if lang == "MM"
            else "❌ Something went wrong. Please try /start again."
        )
    return ConversationHandler.END

# ================================================================
# BATTERY UPDATE
# ================================================================
async def update_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    msg_obj = u.callback_query.message if u.callback_query else u.message
    if u.callback_query:
        await u.callback_query.answer("🔋 Battery % ထည့်ပါ...")
    lang = get_lang(u.effective_user.id)
    await msg_obj.reply_text(
        "🔋 လက်ရှိ Battery % ရိုက်ပါ။ (0-100)" if lang == "MM"
        else "🔋 Enter current battery % (0-100)"
    )
    return PCT

async def update_done(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    try:
        pct = int(u.message.text.strip())
        if not (0 <= pct <= 100):
            raise ValueError("Out of range")
        db.update_pct(uid, pct)
        warning = ""
        if pct <= 20:
            warning = f"\n\n{utils.t(lang, 'battery_low')}"
        elif pct >= 90:
            warning = f"\n\n{utils.t(lang, 'battery_high')}"
        msg = (f"✅ Battery <b>{pct}%</b> မှတ်သားပြီးပါပြီ။" if lang == "MM"
               else f"✅ Battery updated to <b>{pct}%</b>.") + warning
        await u.message.reply_html(msg, reply_markup=get_main_menu(lang))
    except ValueError:
        await u.message.reply_text(
            "❌ 0 မှ 100 အတွင်း ဂဏန်းဖြင့်သာ ရိုက်ပါ။" if lang == "MM"
            else "❌ Please enter a number between 0 and 100."
        )
        return PCT
    return ConversationHandler.END

# ================================================================
# STATUS
# ================================================================
async def status(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    car = db.get_active_car(uid)
    msg_obj = u.callback_query.message if u.callback_query else u.message

    if not car:
        return await msg_obj.reply_html(
            utils.t(lang, "no_car"),
            reply_markup=get_main_menu(lang)
        )

    pct = car[7]
    current_range = (pct / 100) * float(car[5])
    icon = utils.get_battery_icon(pct)
    warning = ""
    if pct <= 20:
        warning = f"\n{utils.t(lang, 'battery_low')}"
    elif pct >= 90:
        warning = f"\n{utils.t(lang, 'battery_high')}"

    weather_text = ""
    if c.user_data.get("last_lat"):
        weather_data = utils.get_weather_and_range(
            c.user_data["last_lat"], c.user_data["last_lon"], float(car[5]), pct
        )
        weather_text = utils.format_weather_range(weather_data, lang)

    if lang == "MM":
        msg = (f"📊 <b>လက်ရှိအခြေအနေ</b>\n\n"
               f"🚗 {car[2]} ({car[3]})\n"
               f"{icon} Battery: <b>{pct}%</b>{warning}\n"
               f"🛣️ မောင်းနိုင်သည့်ခရီး: <b>{current_range:.1f} km</b>\n"
               f"⚡ Charge Rate: {get_charge_rate(car[3])} kW{weather_text}")
    else:
        msg = (f"📊 <b>Current Status</b>\n\n"
               f"🚗 {car[2]} ({car[3]})\n"
               f"{icon} Battery: <b>{pct}%</b>{warning}\n"
               f"🛣️ Est. Range: <b>{current_range:.1f} km</b>\n"
               f"⚡ Charge Rate: {get_charge_rate(car[3])} kW{weather_text}")

    kb = InlineKeyboardMarkup([back_row(lang)])
    await msg_obj.reply_html(msg, reply_markup=kb)

# ================================================================
# CHARGE TIME
# ================================================================
async def chargetime_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    msg_obj = u.callback_query.message if u.callback_query else u.message
    if u.callback_query:
        await u.callback_query.answer("⏱️ ကြာချိန် တွက်မယ်...")
    lang = get_lang(u.effective_user.id)
    await msg_obj.reply_text(
        "🔋 လက်ရှိ Battery % ရိုက်ပါ။" if lang == "MM"
        else "🔋 Enter current battery %"
    )
    return CHARGE_START_PCT

async def chargetime_get_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(u.effective_user.id)
    try:
        pct = int(u.message.text.strip())
        if not (0 <= pct <= 100): raise ValueError
        c.user_data["charge_start"] = pct
        await u.message.reply_text(
            "🎯 အားသွင်းလိုသော % ရိုက်ပါ။ (ဥပမာ: 80)" if lang == "MM"
            else "🎯 Enter target battery % (e.g. 80)"
        )
        return CHARGE_END_PCT
    except ValueError:
        await u.message.reply_text(
            "❌ 0-100 ဂဏန်းဖြင့်သာ ရိုက်ပါ။" if lang == "MM"
            else "❌ Enter a number between 0-100."
        )
        return CHARGE_START_PCT

async def chargetime_calculate(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    try:
        end_pct = int(u.message.text.strip())
        if not (0 <= end_pct <= 100): raise ValueError
        start_pct = c.user_data["charge_start"]

        if end_pct <= start_pct:
            await u.message.reply_text(
                f"❌ Target % သည် {start_pct}% ထက် ကြီးရမည်။" if lang == "MM"
                else f"❌ Target must be greater than current ({start_pct}%)."
            )
            return CHARGE_END_PCT

        car = db.get_active_car(uid)
        if not car:
            await u.message.reply_text(utils.t(lang, "no_car"), reply_markup=get_main_menu(lang))
            return ConversationHandler.END

        cap = float(car[4])
        rate = get_charge_rate(car[3])
        minutes = utils.calculate_charge_time(start_pct, end_pct, cap, rate)
        time_str = utils.format_charge_time(minutes)
        kwh = cap * (end_pct - start_pct) / 100

        if lang == "MM":
            msg = (f"⏱️ <b>အားသွင်းကြာချိန်</b>\n\n"
                   f"🚗 {car[2]} ({car[3]})\n"
                   f"⚡ {rate} kW\n"
                   f"🔋 {start_pct}% → {end_pct}%\n"
                   f"🔌 {kwh:.1f} kWh\n"
                   f"⏱️ ကြာချိန်: <b>{time_str}</b>")
        else:
            msg = (f"⏱️ <b>Charge Time Estimate</b>\n\n"
                   f"🚗 {car[2]} ({car[3]})\n"
                   f"⚡ {rate} kW\n"
                   f"🔋 {start_pct}% → {end_pct}%\n"
                   f"🔌 {kwh:.1f} kWh needed\n"
                   f"⏱️ Time: <b>{time_str}</b>")

        await u.message.reply_html(msg, reply_markup=InlineKeyboardMarkup([back_row(lang)]))
        return ConversationHandler.END
    except ValueError:
        await u.message.reply_text(
            "❌ 0-100 ဂဏန်းဖြင့်သာ ရိုက်ပါ။" if lang == "MM"
            else "❌ Enter a number between 0-100."
        )
        return CHARGE_END_PCT

# ================================================================
# HISTORY
# ================================================================
async def history(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    logs = db.get_logs(uid)
    msg_obj = u.callback_query.message if u.callback_query else u.message
    if not logs:
        return await msg_obj.reply_text(
            utils.t(lang, "no_history"), reply_markup=back_button(lang)
        )
    title = "📜 <b>Battery မှတ်တမ်းများ</b>\n\n" if lang == "MM" else "📜 <b>Battery History</b>\n\n"
    await msg_obj.reply_html(
        title + utils.format_logs_chart(logs),
        reply_markup=back_button(lang)
    )

# ================================================================
# FIND STATION
# ================================================================
async def find_station(u: Update, c: ContextTypes.DEFAULT_TYPE):
    msg_obj = u.callback_query.message if u.callback_query else u.message
    lang = get_lang(u.effective_user.id)
    label = "📍 တည်နေရာပေးပို့ရန်" if lang == "MM" else "📍 Share Location"
    kb = [[KeyboardButton(label, request_location=True)]]
    await msg_obj.reply_text(
        "အနီးဆုံး Charging Station ရှာရန် တည်နေရာပေးပါ။" if lang == "MM"
        else "Share your location to find nearby charging stations.",
        reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True)
    )

async def location_handler(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    lat = u.message.location.latitude
    lon = u.message.location.longitude
    c.user_data["last_lat"] = lat
    c.user_data["last_lon"] = lon

    # ⚡ Loading indicator
    loading_msg = await u.message.reply_text(
        "🔍 Station ရှာဖွေနေပါသည်..." if lang == "MM" else "🔍 Searching for stations...",
        reply_markup=ReplyKeyboardRemove()
    )

    try:
        stations = charge_api.get_nearby_charging_stations(lat, lon, distance=10, max_results=5)
    except Exception as e:
        logger.error(f"Station search error: {e}")
        await loading_msg.delete()
        return await u.message.reply_text(
            "❌ Station ရှာမရပါ။ နောက်မှ ထပ်စမ်းပါ။" if lang == "MM"
            else "❌ Could not search stations. Please try again later.",
            reply_markup=get_main_menu(lang)
        )

    await loading_msg.delete()

    if not stations:
        return await u.message.reply_text(
            "😔 သင့်အနီးတွင် Station မတွေ့ပါ။" if lang == "MM"
            else "😔 No stations found nearby.",
            reply_markup=get_main_menu(lang)
        )

    title = "🔌 <b>အနီးဆုံး အားသွင်းစခန်းများ:</b>\n\n" if lang == "MM" else "🔌 <b>Nearby Charging Stations:</b>\n\n"
    msg = title
    keyboard = []

    for i, station in enumerate(stations):
        info = station.get("addressInfo", {})
        name = info.get("title", "N/A")
        address = info.get("addressLine1", "")
        dist = info.get("distance", 0)
        s_lat = info.get("latitude")
        s_lon = info.get("longitude")

        maps_link = f"https://www.google.com/maps/dir/?api=1&destination={s_lat},{s_lon}"
        view_link = f"https://www.google.com/maps/search/?api=1&query={s_lat},{s_lon}"

        msg += f"{i+1}. <b>{name}</b> ({dist:.1f} km)\n"
        if address:
            msg += f"   📍 {address}\n"
        conns = station.get("connections", [])
        if conns:
            details = [f"{cn.get('connectionType',{}).get('title','?')} ({cn.get('powerKW','?')}kW)" for cn in conns]
            msg += f"   ⚡ {', '.join(details)}\n"
        msg += f"   <a href=\"{maps_link}\">🗺️ Navigate</a> | <a href=\"{view_link}\">📌 View</a>\n\n"

        cb = f"save_fav_|{name}|{address or 'N/A'}|{s_lat}|{s_lon}"
        keyboard.append([InlineKeyboardButton(f"⭐ {name[:25]}", callback_data=cb)])

    keyboard.append(back_row(lang))
    await u.message.reply_html(msg, disable_web_page_preview=True,
                                reply_markup=InlineKeyboardMarkup(keyboard))

# ================================================================
# MULTIPLE CARS
# ================================================================
async def show_cars(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    cars = db.get_all_cars(uid)
    msg_obj = u.callback_query.message

    if not cars:
        return await msg_obj.reply_html(
            utils.t(lang, "no_car"), reply_markup=get_main_menu(lang)
        )

    msg = "🚗 <b>သင့်ကားများ:</b>\n\n" if lang == "MM" else "🚗 <b>Your Cars:</b>\n\n"
    keyboard = []
    for car in cars:
        active = "✅ " if car[8] == 1 else ""
        msg += f"{active}<b>{car[2]}</b> — {car[3]} | {car[4]}kWh | {car[7]}%\n"
        row = []
        if car[8] != 1:
            row.append(InlineKeyboardButton(f"✅ {car[2]}", callback_data=f"switch_car_{car[0]}"))
        row.append(InlineKeyboardButton(f"🗑️ {car[2]}", callback_data=f"del_car_{car[0]}"))
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("➕ ကားထပ်ထည့်" if lang == "MM" else "➕ Add Car", callback_data="reg_start")])
    keyboard.append(back_row(lang))
    await msg_obj.reply_html(msg, reply_markup=InlineKeyboardMarkup(keyboard))

# ================================================================
# FAVORITES
# ================================================================
async def show_favorites(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    favs = db.get_favorites(uid)
    msg_obj = u.callback_query.message

    if not favs:
        return await msg_obj.reply_html(
            utils.t(lang, "no_favorites"), reply_markup=back_button(lang)
        )

    msg = "📍 <b>Favorite Stations:</b>\n\n"
    keyboard = []
    for fav in favs:
        maps_link = f"https://www.google.com/maps/dir/?api=1&destination={fav[4]},{fav[5]}"
        msg += f"⭐ <b>{fav[2]}</b>\n   📍 {fav[3]}\n   <a href=\"{maps_link}\">🗺️ Navigate</a>\n\n"
        keyboard.append([InlineKeyboardButton(f"🗑️ {fav[2][:25]}", callback_data=f"del_fav_{fav[0]}")])

    keyboard.append(back_row(lang))
    await msg_obj.reply_html(msg, disable_web_page_preview=True,
                              reply_markup=InlineKeyboardMarkup(keyboard))

# ================================================================
# TIPS
# ================================================================
async def tips(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    msg_obj = u.callback_query.message if u.callback_query else u.message
    if lang == "MM":
        msg = ("💡 <b>EV Battery Tips:</b>\n\n"
               "• 🟢 Battery <b>20%-80%</b> ကြားထားပါ\n"
               "• 🌙 ညဘက် Off-peak မှာ အားသွင်းပါ\n"
               "• ❄️ အအေးမှာ range ကျနိုင်တယ်\n"
               "• ⚡ DC Fast Charge မကြာမကြာ မသုံးပါနဲ့\n"
               "• 🔄 တစ်လတစ်ကြိမ် 100% calibrate လုပ်ပါ")
    else:
        msg = ("💡 <b>EV Battery Tips:</b>\n\n"
               "• 🟢 Keep battery between <b>20%-80%</b>\n"
               "• 🌙 Charge during off-peak hours\n"
               "• ❄️ Cold weather reduces range\n"
               "• ⚡ Avoid frequent DC Fast Charging\n"
               "• 🔄 Calibrate monthly with full charge")
    await msg_obj.reply_html(msg, reply_markup=back_button(lang))

# ================================================================
# OFF-PEAK REMINDER
# ================================================================
async def send_off_peak_reminder(context: ContextTypes.DEFAULT_TYPE):
    for uid in db.get_all_user_ids():
        try:
            lang = db.get_language(uid)
            msg = ("🌙 ည Off-Peak အားသွင်းချိန်ရောက်ပြီ! Battery 80% ထိသာ သွင်းပါ။"
                   if lang == "MM" else
                   "🌙 Off-peak charging time! Charge to 80% only.")
            await context.bot.send_message(chat_id=uid, text=msg)
        except Exception as e:
            logger.error(f"Reminder failed for {uid}: {e}")

# ================================================================
# CANCEL
# ================================================================
async def cancel(u: Update, c: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(u.effective_user.id)
    await u.message.reply_text(
        "ဖျက်သိမ်းပြီးပါပြီ။" if lang == "MM" else "Cancelled.",
        reply_markup=get_main_menu(lang)
    )
    return ConversationHandler.END

# ================================================================
# MAIN
# ================================================================
def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN မရှိပါ!")
        return

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    from datetime import time as dtime
    app.job_queue.run_daily(send_off_peak_reminder, time=dtime(hour=22, minute=0))

    reg_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(reg_start, pattern="^reg_start$"),
            CommandHandler("register", reg_start)
        ],
        states={
            CAR_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_car_name)],
            MODEL:    [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_model)],
            CAP:      [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_cap)],
            RANGE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_range)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    upd_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(update_start, pattern="^upd_start$"),
            CommandHandler("update", update_start)
        ],
        states={PCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_done)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    chargetime_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(chargetime_start, pattern="^chargetime_start$"),
            CommandHandler("chargetime", chargetime_start)
        ],
        states={
            CHARGE_START_PCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, chargetime_get_start)],
            CHARGE_END_PCT:   [MessageHandler(filters.TEXT & ~filters.COMMAND, chargetime_calculate)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(reg_conv)
    app.add_handler(upd_conv)
    app.add_handler(chargetime_conv)
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.LOCATION, location_handler))

    print("✅ EV Helper Bot running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
