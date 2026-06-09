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
from admin_bot import (
    send_payment_to_admin, admin_callback_handler, admin_stats,
    ADMIN_CHAT_ID, KPAY_NUMBER, WAVE_NUMBER, PLANS
)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# --- States ---
CAR_NAME, MODEL, CAP, RANGE = range(4)
PCT = range(1)
CHARGE_START_PCT, CHARGE_END_PCT = range(2)
PAYMENT_SCREENSHOT, PAYMENT_PLAN = range(2)

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
# PREMIUM CHECK HELPERS
# ================================================================
def check_premium(uid, feature, lang):
    """Premium feature စစ်ပြီး upgrade message ပြတယ်"""
    if db.is_premium(uid):
        return True, None
    
    if lang == "MM":
        msg = (f"⭐ <b>Premium Feature</b>\n\n"
               f"ဒီ feature ကို Premium plan နဲ့သာ သုံးနိုင်ပါတယ်။\n\n"
               f"📱 MMK 5,000/လ မှ စတင်နိုင်ပါတယ်။")
    else:
        msg = (f"⭐ <b>Premium Feature</b>\n\n"
               f"This feature requires a Premium plan.\n\n"
               f"📱 Starting from MMK 5,000/month.")
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ Upgrade to Premium", callback_data="upgrade")],
        back_row(lang)
    ])
    return False, (msg, kb)

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
             InlineKeyboardButton("📍 Favorites ⭐", callback_data="favs")],
            [InlineKeyboardButton("⭐ Premium", callback_data="upgrade"),
             InlineKeyboardButton("🌐 EN/MM", callback_data="lang")],
            [InlineKeyboardButton("💡 Tips", callback_data="tips")],
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
             InlineKeyboardButton("📍 Favorites ⭐", callback_data="favs")],
            [InlineKeyboardButton("⭐ Premium", callback_data="upgrade"),
             InlineKeyboardButton("🌐 EN/MM", callback_data="lang")],
            [InlineKeyboardButton("💡 Tips", callback_data="tips")],
        ]
    return InlineKeyboardMarkup(keyboard)

def back_row(lang="MM"):
    label = "🔙 Menu သို့ပြန်" if lang == "MM" else "🔙 Back to Menu"
    return [InlineKeyboardButton(label, callback_data="back_menu")]

def back_button(lang="MM"):
    return InlineKeyboardMarkup([back_row(lang)])

# ================================================================
# /start
# ================================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.get_or_create_user(uid)
    lang = get_lang(uid)
    car = db.get_active_car(uid)
    name = update.effective_user.first_name or ""
    plan = db.get_plan(uid)
    plan_badge = "⭐ Premium" if plan == "premium" else "🆓 Free"

    if car:
        pct = car[7]
        icon = utils.get_battery_icon(pct)
        if lang == "MM":
            msg = (f"👋 ပြန်လာတာ ကြိုဆိုပါတယ်, <b>{name}</b>! {plan_badge}\n\n"
                   f"🚗 {car[2]} ({car[3]})\n"
                   f"{icon} Battery: <b>{pct}%</b>\n\n"
                   f"ဘာကူညီရမလဲ?")
        else:
            msg = (f"👋 Welcome back, <b>{name}</b>! {plan_badge}\n\n"
                   f"🚗 {car[2]} ({car[3]})\n"
                   f"{icon} Battery: <b>{pct}%</b>\n\n"
                   f"How can I help you?")
    else:
        if lang == "MM":
            msg = (f"⚡ <b>EV Helper Smart Assistant</b>\n\n"
                   f"မင်္ဂလာပါ, <b>{name}</b>!\n"
                   f"ကား မှတ်ပုံတင်ပြီး စတင်ပါ။")
        else:
            msg = (f"⚡ <b>EV Helper Smart Assistant</b>\n\n"
                   f"Hello, <b>{name}</b>!\n"
                   f"Register your car to get started.")

    if update.message:
        await update.message.reply_html(msg, reply_markup=get_main_menu(lang))
    else:
        await update.callback_query.message.edit_text(msg, reply_markup=get_main_menu(lang), parse_mode="HTML")

# ================================================================
# PREMIUM UPGRADE FLOW
# ================================================================
async def upgrade_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    lang = get_lang(uid)
    msg_obj = update.callback_query.message

    if db.is_premium(uid):
        expire = db.get_expire_date(uid)
        from datetime import datetime
        expire_str = datetime.fromisoformat(expire).strftime("%Y-%m-%d") if expire else "N/A"
        if lang == "MM":
            msg = (f"⭐ <b>Premium Plan အသုံးပြုနေပြီ!</b>\n\n"
                   f"📅 သက်တမ်းကုန်ဆုံးရက်: <b>{expire_str}</b>\n\n"
                   f"Premium features အားလုံး အသုံးပြုနိုင်ပါတယ်။")
        else:
            msg = (f"⭐ <b>You're on Premium!</b>\n\n"
                   f"📅 Expires: <b>{expire_str}</b>\n\n"
                   f"Enjoy all Premium features!")
        return await msg_obj.reply_html(msg, reply_markup=back_button(lang))

    if lang == "MM":
        msg = ("⭐ <b>Premium Plan</b>\n\n"
               "🆓 Free Plan:\n"
               "• ကား ၁ စီးသာ\n"
               "• History ၇ ရက်\n"
               "• Favorites ❌\n"
               "• Weather Range ❌\n\n"
               "⭐ Premium Plan:\n"
               "• ကား အကန့်အသတ်မဲ့ ✅\n"
               "• History အကန့်အသတ်မဲ့ ✅\n"
               "• Favorites ✅\n"
               "• Weather Range ✅\n"
               "• Weekly Summary ✅\n\n"
               "Plan ရွေးပါ:")
    else:
        msg = ("⭐ <b>Premium Plan</b>\n\n"
               "🆓 Free Plan:\n"
               "• 1 car only\n"
               "• 7-day history\n"
               "• No Favorites\n"
               "• No Weather Range\n\n"
               "⭐ Premium Plan:\n"
               "• Unlimited cars ✅\n"
               "• Full history ✅\n"
               "• Favorites ✅\n"
               "• Weather Range ✅\n"
               "• Weekly Summary ✅\n\n"
               "Select a plan:")

    kb = []
    for key, plan in PLANS.items():
        kb.append([InlineKeyboardButton(f"⭐ {plan['label']}", callback_data=f"buy_plan_{key}")])
    kb.append(back_row(lang))
    await msg_obj.reply_html(msg, reply_markup=InlineKeyboardMarkup(kb))

async def buy_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    lang = get_lang(uid)
    plan_key = query.data.replace("buy_plan_", "")
    plan = PLANS.get(plan_key)
    if not plan:
        return

    context.user_data["selected_plan"] = plan_key

    if lang == "MM":
        msg = (f"💰 <b>ငွေလွှဲနည်း</b>\n\n"
               f"Plan: {plan['label']}\n\n"
               f"📱 <b>KPay:</b> <code>{KPAY_NUMBER}</code>\n"
               f"📱 <b>Wave:</b> <code>{WAVE_NUMBER}</code>\n\n"
               f"Amount: <b>MMK {plan['price']:,}</b>\n\n"
               f"ငွေလွှဲပြီးရင် screenshot ကို ဒီမှာ ပို့ပေးပါ။")
    else:
        msg = (f"💰 <b>Payment Instructions</b>\n\n"
               f"Plan: {plan['label']}\n\n"
               f"📱 <b>KPay:</b> <code>{KPAY_NUMBER}</code>\n"
               f"📱 <b>Wave:</b> <code>{WAVE_NUMBER}</code>\n\n"
               f"Amount: <b>MMK {plan['price']:,}</b>\n\n"
               f"After payment, send the screenshot here.")

    await query.message.reply_html(msg, reply_markup=back_button(lang))
    return PAYMENT_SCREENSHOT

async def payment_screenshot_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    lang = get_lang(uid)

    if not update.message.photo:
        await update.message.reply_text(
            "❌ Screenshot ဓါတ်ပုံ ပို့ပေးပါ။" if lang == "MM"
            else "❌ Please send a photo screenshot."
        )
        return PAYMENT_SCREENSHOT

    plan_key = context.user_data.get("selected_plan", "1")
    plan = PLANS.get(plan_key, PLANS["1"])
    screenshot_file_id = update.message.photo[-1].file_id

    payment_id = db.add_pending_payment(uid, plan["price"], plan["months"], screenshot_file_id)
    await send_payment_to_admin(context, payment_id, uid, plan["months"], plan["price"], screenshot_file_id)

    if lang == "MM":
        msg = (f"✅ <b>Screenshot လက်ခံရရှိပြီး!</b>\n\n"
               f"Payment ID: <code>#{payment_id}</code>\n"
               f"Admin မှ အတည်ပြုပြီးရင် Premium activate ဖြစ်သွားမည်။\n"
               f"ပုံမှန်အားဖြင့် မိနစ် ၃၀ အတွင်း ဖြေရှင်းပေးပါမည်။")
    else:
        msg = (f"✅ <b>Screenshot received!</b>\n\n"
               f"Payment ID: <code>#{payment_id}</code>\n"
               f"Admin will verify and activate your Premium.\n"
               f"Usually within 30 minutes.")

    await update.message.reply_html(msg, reply_markup=get_main_menu(lang))
    return ConversationHandler.END

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
    elif query.data == "upgrade":
        await upgrade_menu(update, context)
    elif query.data.startswith("buy_plan_"):
        await buy_plan(update, context)
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
        await query.answer("✅ ကား ပြောင်းပြီး!" if lang == "MM" else "✅ Car switched!", show_alert=True)
        await show_cars(update, context)
    elif query.data.startswith("del_car_"):
        car_id = int(query.data.replace("del_car_", ""))
        db.delete_car(uid, car_id)
        await query.answer("🗑️ ဖျက်ပြီး!" if lang == "MM" else "🗑️ Deleted!", show_alert=True)
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
    elif query.data.startswith("admin_"):
        await admin_callback_handler(update, context)

# ================================================================
# LANGUAGE
# ================================================================
async def lang_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update.effective_user.id)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🇲🇲 မြန်မာ", callback_data="lang_mm"),
         InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
        back_row(lang)
    ])
    await update.callback_query.message.reply_text("🌐 ဘာသာစကား ရွေးပါ:", reply_markup=kb)

# ================================================================
# REGISTRATION
# ================================================================
async def reg_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    msg_obj = u.callback_query.message if u.callback_query else u.message
    if u.callback_query:
        await u.callback_query.answer()

    # Free plan: ကား ၁ စီးသာ
    if not db.is_premium(uid) and db.get_cars_count(uid) >= 1:
        ok, data = check_premium(uid, "multiple_cars", lang)
        return await msg_obj.reply_html(data[0], reply_markup=data[1])

    await msg_obj.reply_text(
        "🚗 ကားအမည် ရိုက်ပါ။ (ဥပမာ: ကျွန်တော့်ကား)" if lang == "MM"
        else "🚗 Enter a name for this car. (e.g. My Tesla)"
    )
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
    await u.message.reply_html(
        f"⚡ Charge Rate: <b>{rate} kW</b> (Auto-detected)\n\n" +
        ("🔋 Battery Capacity (kWh) ရိုက်ပါ။ (ဥပမာ: 72.8)" if lang == "MM"
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
        await u.message.reply_text("❌ ဂဏန်းသာ ရိုက်ပါ။" if lang == "MM" else "❌ Numbers only.")
        return CAP

async def reg_range(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    try:
        full_range = float(u.message.text.strip())
        db.add_car(uid, c.user_data["car_name"], c.user_data["model"],
                   c.user_data["cap"], full_range, c.user_data.get("rate", 50))
        await u.message.reply_html(
            f"✅ <b>မှတ်ပုံတင်ပြီး!</b>\n"
            f"🚗 {c.user_data['car_name']} ({c.user_data['model']})\n"
            f"🔋 {c.user_data['cap']} kWh | 🛣️ {full_range} km | ⚡ {c.user_data.get('rate', 50)} kW",
            reply_markup=get_main_menu(lang)
        )
    except ValueError:
        await u.message.reply_text("❌ ဂဏန်းသာ ရိုက်ပါ။" if lang == "MM" else "❌ Numbers only.")
        return RANGE
    except Exception as e:
        logger.error(f"Reg Error: {e}")
        await u.message.reply_text("❌ Error ဖြစ်သည်။ /start မှ ပြန်စပါ။")
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
        if not (0 <= pct <= 100): raise ValueError
        db.update_pct(uid, pct)
        warning = ""
        if pct <= 20: warning = f"\n\n{utils.t(lang, 'battery_low')}"
        elif pct >= 90: warning = f"\n\n{utils.t(lang, 'battery_high')}"
        msg = (f"✅ Battery <b>{pct}%</b> မှတ်သားပြီး။" if lang == "MM"
               else f"✅ Battery updated to <b>{pct}%</b>.") + warning
        await u.message.reply_html(msg, reply_markup=get_main_menu(lang))
    except ValueError:
        await u.message.reply_text("❌ 0-100 ဂဏန်းဖြင့်သာ ရိုက်ပါ။" if lang == "MM" else "❌ Enter 0-100.")
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
        return await msg_obj.reply_text(utils.t(lang, "no_car"), reply_markup=get_main_menu(lang))

    pct = car[7]
    current_range = (pct / 100) * float(car[5])
    icon = utils.get_battery_icon(pct)
    warning = ""
    if pct <= 20: warning = f"\n{utils.t(lang, 'battery_low')}"
    elif pct >= 90: warning = f"\n{utils.t(lang, 'battery_high')}"

    # Weather — Premium only
    weather_text = ""
    if db.is_premium(uid) and c.user_data.get("last_lat"):
        weather_data = utils.get_weather_and_range(
            c.user_data["last_lat"], c.user_data["last_lon"], float(car[5]), pct
        )
        weather_text = utils.format_weather_range(weather_data, lang)
    elif not db.is_premium(uid):
        weather_text = "\n\n⭐ Weather Range: Premium feature"

    if lang == "MM":
        msg = (f"📊 <b>လက်ရှိအခြေအနေ</b>\n\n"
               f"🚗 {car[2]} ({car[3]})\n"
               f"{icon} Battery: <b>{pct}%</b>{warning}\n"
               f"🛣️ ခရီး: <b>{current_range:.1f} km</b>\n"
               f"⚡ {get_charge_rate(car[3])} kW{weather_text}")
    else:
        msg = (f"📊 <b>Current Status</b>\n\n"
               f"🚗 {car[2]} ({car[3]})\n"
               f"{icon} Battery: <b>{pct}%</b>{warning}\n"
               f"🛣️ Range: <b>{current_range:.1f} km</b>\n"
               f"⚡ {get_charge_rate(car[3])} kW{weather_text}")

    await msg_obj.reply_html(msg, reply_markup=InlineKeyboardMarkup([back_row(lang)]))

# ================================================================
# CHARGE TIME
# ================================================================
async def chargetime_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    msg_obj = u.callback_query.message if u.callback_query else u.message
    if u.callback_query:
        await u.callback_query.answer("⏱️ တွက်မယ်...")
    lang = get_lang(u.effective_user.id)
    await msg_obj.reply_text(
        "🔋 လက်ရှိ Battery % ရိုက်ပါ။" if lang == "MM" else "🔋 Enter current battery %"
    )
    return CHARGE_START_PCT

async def chargetime_get_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(u.effective_user.id)
    try:
        pct = int(u.message.text.strip())
        if not (0 <= pct <= 100): raise ValueError
        c.user_data["charge_start"] = pct
        await u.message.reply_text(
            "🎯 Target % ရိုက်ပါ။ (ဥပမာ: 80)" if lang == "MM" else "🎯 Enter target % (e.g. 80)"
        )
        return CHARGE_END_PCT
    except ValueError:
        await u.message.reply_text("❌ 0-100 ဂဏန်းဖြင့်သာ ရိုက်ပါ။")
        return CHARGE_START_PCT

async def chargetime_calculate(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    try:
        end_pct = int(u.message.text.strip())
        if not (0 <= end_pct <= 100): raise ValueError
        start_pct = c.user_data["charge_start"]
        if end_pct <= start_pct:
            await u.message.reply_text(f"❌ Target သည် {start_pct}% ထက် ကြီးရမည်။")
            return CHARGE_END_PCT
        car = db.get_active_car(uid)
        if not car:
            await u.message.reply_text(utils.t(lang, "no_car"))
            return ConversationHandler.END
        cap = float(car[4])
        rate = get_charge_rate(car[3])
        minutes = utils.calculate_charge_time(start_pct, end_pct, cap, rate)
        time_str = utils.format_charge_time(minutes)
        kwh = cap * (end_pct - start_pct) / 100
        if lang == "MM":
            msg = (f"⏱️ <b>အားသွင်းကြာချိန်</b>\n\n"
                   f"🚗 {car[2]} ({car[3]})\n⚡ {rate} kW\n"
                   f"🔋 {start_pct}% → {end_pct}% ({kwh:.1f} kWh)\n"
                   f"⏱️ <b>{time_str}</b>")
        else:
            msg = (f"⏱️ <b>Charge Time</b>\n\n"
                   f"🚗 {car[2]} ({car[3]})\n⚡ {rate} kW\n"
                   f"🔋 {start_pct}% → {end_pct}% ({kwh:.1f} kWh)\n"
                   f"⏱️ <b>{time_str}</b>")
        await u.message.reply_html(msg, reply_markup=InlineKeyboardMarkup([back_row(lang)]))
        return ConversationHandler.END
    except ValueError:
        await u.message.reply_text("❌ 0-100 ဂဏန်းဖြင့်သာ ရိုက်ပါ။")
        return CHARGE_END_PCT

# ================================================================
# HISTORY (Free: 7 days | Premium: unlimited)
# ================================================================
async def history(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    msg_obj = u.callback_query.message if u.callback_query else u.message
    days = None if db.is_premium(uid) else 7
    logs = db.get_logs(uid, days=days)
    if not logs:
        return await msg_obj.reply_text(utils.t(lang, "no_history"), reply_markup=back_button(lang))
    limit_note = "" if db.is_premium(uid) else ("\n<i>⭐ Premium: မှတ်တမ်း အကန့်အသတ်မဲ့</i>" if lang == "MM" else "\n<i>⭐ Premium: Unlimited history</i>")
    title = "📜 <b>Battery မှတ်တမ်း</b>" if lang == "MM" else "📜 <b>Battery History</b>"
    await msg_obj.reply_html(
        title + limit_note + "\n\n" + utils.format_logs_chart(logs),
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
        "Station ရှာရန် တည်နေရာပေးပါ။" if lang == "MM" else "Share location to find stations.",
        reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True)
    )

async def location_handler(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    lat = u.message.location.latitude
    lon = u.message.location.longitude
    c.user_data["last_lat"] = lat
    c.user_data["last_lon"] = lon

    loading = await u.message.reply_text(
        "🔍 ရှာဖွေနေပါသည်..." if lang == "MM" else "🔍 Searching...",
        reply_markup=ReplyKeyboardRemove()
    )
    try:
        stations = charge_api.get_nearby_charging_stations(lat, lon, distance=10, max_results=5)
    except Exception as e:
        logger.error(f"Station error: {e}")
        await loading.delete()
        return await u.message.reply_text(
            "❌ Station ရှာမရပါ။ နောက်မှ စမ်းပါ။" if lang == "MM" else "❌ Search failed. Try again later.",
            reply_markup=get_main_menu(lang)
        )
    await loading.delete()

    if not stations:
        return await u.message.reply_text(
            "😔 အနီးတွင် Station မတွေ့ပါ။" if lang == "MM" else "😔 No stations found nearby.",
            reply_markup=get_main_menu(lang)
        )

    title = "🔌 <b>အနီးဆုံး Station များ:</b>\n\n" if lang == "MM" else "🔌 <b>Nearby Stations:</b>\n\n"
    msg = title
    keyboard = []
    is_prem = db.is_premium(uid)

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
        if address: msg += f"   📍 {address}\n"
        conns = station.get("connections", [])
        if conns:
            details = [f"{cn.get('connectionType',{}).get('title','?')} ({cn.get('powerKW','?')}kW)" for cn in conns]
            msg += f"   ⚡ {', '.join(details)}\n"
        msg += f"   <a href=\"{maps_link}\">🗺️ Navigate</a> | <a href=\"{view_link}\">📌 View</a>\n\n"

        # Favorites — Premium only
        if is_prem:
            cb = f"save_fav_|{name}|{address or 'N/A'}|{s_lat}|{s_lon}"
            keyboard.append([InlineKeyboardButton(f"⭐ {name[:25]}", callback_data=cb)])

    if not is_prem:
        keyboard.append([InlineKeyboardButton("⭐ Favorites သိမ်းဖို့ Premium လိုသည်", callback_data="upgrade")])
    keyboard.append(back_row(lang))
    await u.message.reply_html(msg, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(keyboard))

# ================================================================
# MULTIPLE CARS
# ================================================================
async def show_cars(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    cars = db.get_all_cars(uid)
    msg_obj = u.callback_query.message
    if not cars:
        return await msg_obj.reply_text(utils.t(lang, "no_car"), reply_markup=get_main_menu(lang))
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
# FAVORITES (Premium only)
# ================================================================
async def show_favorites(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    msg_obj = u.callback_query.message

    ok, data = check_premium(uid, "favorites", lang)
    if not ok:
        return await msg_obj.reply_html(data[0], reply_markup=data[1])

    favs = db.get_favorites(uid)
    if not favs:
        return await msg_obj.reply_text(utils.t(lang, "no_favorites"), reply_markup=back_button(lang))

    msg = "📍 <b>Favorite Stations:</b>\n\n"
    keyboard = []
    for fav in favs:
        maps_link = f"https://www.google.com/maps/dir/?api=1&destination={fav[4]},{fav[5]}"
        msg += f"⭐ <b>{fav[2]}</b>\n   📍 {fav[3]}\n   <a href=\"{maps_link}\">🗺️ Navigate</a>\n\n"
        keyboard.append([InlineKeyboardButton(f"🗑️ {fav[2][:25]}", callback_data=f"del_fav_{fav[0]}")])
    keyboard.append(back_row(lang))
    await msg_obj.reply_html(msg, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(keyboard))

# ================================================================
# TIPS
# ================================================================
async def tips(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    msg_obj = u.callback_query.message if u.callback_query else u.message
    if lang == "MM":
        msg = ("💡 <b>EV Battery Tips:</b>\n\n"
               "• 🟢 Battery 20%-80% ကြားထားပါ\n"
               "• 🌙 ညဘက် Off-peak မှာ အားသွင်းပါ\n"
               "• ❄️ အအေးမှာ range ကျနိုင်တယ်\n"
               "• ⚡ DC Fast Charge မကြာမကြာ မသုံးပါနဲ့\n"
               "• 🔄 တစ်လတစ်ကြိမ် 100% calibrate လုပ်ပါ")
    else:
        msg = ("💡 <b>EV Battery Tips:</b>\n\n"
               "• 🟢 Keep battery 20%-80%\n"
               "• 🌙 Charge during off-peak hours\n"
               "• ❄️ Cold weather reduces range\n"
               "• ⚡ Avoid frequent DC Fast Charging\n"
               "• 🔄 Calibrate monthly")
    await msg_obj.reply_html(msg, reply_markup=back_button(lang))

# ================================================================
# OFF-PEAK REMINDER
# ================================================================
async def send_off_peak_reminder(context: ContextTypes.DEFAULT_TYPE):
    for uid in db.get_all_user_ids():
        try:
            lang = db.get_language(uid)
            msg = ("🌙 Off-Peak အားသွင်းချိန်! Battery 80% ထိသာ သွင်းပါ။"
                   if lang == "MM" else "🌙 Off-peak time! Charge to 80% only.")
            await context.bot.send_message(chat_id=uid, text=msg)
        except Exception as e:
            logger.error(f"Reminder failed {uid}: {e}")

# ================================================================
# CANCEL
# ================================================================
async def cancel(u: Update, c: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(u.effective_user.id)
    await u.message.reply_text(
        "ဖျက်သိမ်းပြီး။" if lang == "MM" else "Cancelled.",
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
        entry_points=[CallbackQueryHandler(reg_start, pattern="^reg_start$"), CommandHandler("register", reg_start)],
        states={
            CAR_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_car_name)],
            MODEL:    [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_model)],
            CAP:      [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_cap)],
            RANGE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_range)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    upd_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(update_start, pattern="^upd_start$"), CommandHandler("update", update_start)],
        states={PCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_done)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    chargetime_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(chargetime_start, pattern="^chargetime_start$"), CommandHandler("chargetime", chargetime_start)],
        states={
            CHARGE_START_PCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, chargetime_get_start)],
            CHARGE_END_PCT:   [MessageHandler(filters.TEXT & ~filters.COMMAND, chargetime_calculate)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    payment_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(buy_plan, pattern="^buy_plan_")],
        states={
            PAYMENT_SCREENSHOT: [MessageHandler(filters.PHOTO, payment_screenshot_received)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(reg_conv)
    app.add_handler(upd_conv)
    app.add_handler(chargetime_conv)
    app.add_handler(payment_conv)
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.LOCATION, location_handler))

    print("✅ EV Helper Bot running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
