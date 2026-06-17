import os
import logging
import html
from datetime import datetime
from telegram import (Update, InlineKeyboardButton, InlineKeyboardMarkup,
                       KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove)
from telegram.ext import (Application, CommandHandler, MessageHandler, filters,
                           ConversationHandler, CallbackQueryHandler, ContextTypes)
import database as db
import charge_api
import utils
import visuals
from admin_bot import (send_payment_to_admin, admin_callback_handler, admin_stats,
                       ADMIN_CHAT_ID, KPAY_NUMBER, WAVE_NUMBER, PLANS)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ELECTRICITY_RATE_MMK = 200

# ================================================================
# STATE CONSTANTS — unique values, no conflicts
# ================================================================
# Registration
S_CAR_NAME   = 100
S_MODEL      = 101
S_CAP        = 102
S_RANGE      = 103
# Battery update
S_PCT        = 200
# Charge time
S_CT_START   = 300
S_CT_END     = 301
# Payment
S_PAYMENT    = 400
# Route
S_RT_FROM    = 500
S_RT_TO      = 501
S_RT_PCT     = 502
# Cost
S_COST_START = 600
S_COST_END   = 601
# AI Chat
S_AI_CHAT    = 700
# Battery Health
S_BH_SOH     = 800
S_BH_MILEAGE = 801
# Expense
S_EXP_CAT    = 900
S_EXP_AMT    = 901
S_EXP_NOTE   = 902

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

# Myanmar city name mapping (မြန်မာဘာသာ → English)
MM_CITY_MAP = {
    "ရန်ကုန်": "Yangon", "မန္တလေး": "Mandalay", "နေပြည်တော်": "Naypyidaw",
    "ပဲခူး": "Bago", "တောင်ငူ": "Taungoo", "ပြည်": "Pyay",
    "မော်လမြိုင်": "Mawlamyine", "မိုင်းဆတ်": "Mong Hsat",
    "တာချီလိတ်": "Tachileik", "ကျိုင်းတုံ": "Kengtung",
    "လွိုင်ကော်": "Loikaw", "မိတ္ထီလာ": "Meiktila",
    "စစ်ကိုင်း": "Sagaing", "မုံရွာ": "Monywa",
    "ကလေး": "Kalay", "ဘားအံ": "Hpa-An",
    "ထားဝယ်": "Dawei", "မြိတ်": "Myeik",
    "သထုံ": "Thaton", "ကျောက်ဆည်": "Kyaukse",
    "အင်းဝ": "Inwa", "ပင်လောင်း": "Pinlaung",
    "လင်းခေး": "Linkhe", "ဟားခါး": "Hakha",
    "ဖလမ်း": "Falam", "မင်းတပ်": "Mindat",
}

def get_charge_rate(model):
    return CAR_CHARGE_RATES.get(model.lower().strip(), 50)

def get_lang(uid):
    return db.get_language(uid)

# ================================================================
# UI HELPERS
# ================================================================
def back_row(lang="MM"):
    label = "🔙 Menu သို့ပြန်" if lang == "MM" else "🔙 Back to Menu"
    return [InlineKeyboardButton(label, callback_data="back_menu")]

def back_button(lang="MM"):
    return InlineKeyboardMarkup([back_row(lang)])

def check_premium(uid, lang):
    if db.is_premium(uid):
        return True, None
    msg = ("⭐ <b>Premium Feature</b>\n\nဒီ feature ကို Premium plan နဲ့သာ သုံးနိုင်ပါတယ်။\nMMK 5,000/လ မှ စတင်နိုင်ပါတယ်။"
           if lang == "MM" else
           "⭐ <b>Premium Feature</b>\n\nThis requires a Premium plan.\nFrom MMK 5,000/month.")
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⭐ Upgrade to Premium", callback_data="upgrade")], back_row(lang)])
    return False, (msg, kb)

def get_main_menu(lang="MM"):
    if lang == "MM":
        kb = [
            [InlineKeyboardButton("🚗 ကား မှတ်ပုံတင်", callback_data="reg_start"),
             InlineKeyboardButton("🔋 Battery အပ်ဒိတ်", callback_data="upd_start")],
            [InlineKeyboardButton("📊 အခြေအနေ", callback_data="stat"),
             InlineKeyboardButton("📜 မှတ်တမ်း", callback_data="hist")],
            [InlineKeyboardButton("🔌 Station ရှာ", callback_data="find"),
             InlineKeyboardButton("⏱️ အားသွင်းကြာချိန်", callback_data="chargetime_start")],
            [InlineKeyboardButton("🗺️ Route Planner ⭐", callback_data="route_start"),
             InlineKeyboardButton("💰 Cost Calculator", callback_data="cost_start")],
            [InlineKeyboardButton("📊 Visual Charts ⭐", callback_data="visual_charts")],
            [InlineKeyboardButton("🔔 Reminders", callback_data="reminders"),
             InlineKeyboardButton("🤖 AI Chat ⭐", callback_data="ai_chat_start")],
            [InlineKeyboardButton("🚗 ကားများ", callback_data="cars"),
             InlineKeyboardButton("📍 Favorites ⭐", callback_data="favs")],
            [InlineKeyboardButton("⭐ Premium", callback_data="upgrade"),
             InlineKeyboardButton("🌐 EN/MM", callback_data="lang")],
            [InlineKeyboardButton("🔋 Battery Health", callback_data="bhealth_start"),
             InlineKeyboardButton("💰 Expense", callback_data="expense_start")],
            [InlineKeyboardButton("📊 Monthly Report", callback_data="monthly_report"),
             InlineKeyboardButton("💡 Tips", callback_data="tips")],
        ]
    else:
        kb = [
            [InlineKeyboardButton("🚗 Register Car", callback_data="reg_start"),
             InlineKeyboardButton("🔋 Update Battery", callback_data="upd_start")],
            [InlineKeyboardButton("📊 My Status", callback_data="stat"),
             InlineKeyboardButton("📜 History", callback_data="hist")],
            [InlineKeyboardButton("🔌 Find Station", callback_data="find"),
             InlineKeyboardButton("⏱️ Charge Time", callback_data="chargetime_start")],
            [InlineKeyboardButton("🗺️ Route Planner ⭐", callback_data="route_start"),
             InlineKeyboardButton("💰 Cost Calculator", callback_data="cost_start")],
            [InlineKeyboardButton("📊 Visual Charts ⭐", callback_data="visual_charts")],
            [InlineKeyboardButton("🔔 Reminders", callback_data="reminders"),
             InlineKeyboardButton("🤖 AI Chat ⭐", callback_data="ai_chat_start")],
            [InlineKeyboardButton("🚗 My Cars", callback_data="cars"),
             InlineKeyboardButton("📍 Favorites ⭐", callback_data="favs")],
            [InlineKeyboardButton("⭐ Premium", callback_data="upgrade"),
             InlineKeyboardButton("🌐 EN/MM", callback_data="lang")],
            [InlineKeyboardButton("🔋 Battery Health", callback_data="bhealth_start"),
             InlineKeyboardButton("💰 Expense", callback_data="expense_start")],
            [InlineKeyboardButton("📊 Monthly Report", callback_data="monthly_report"),
             InlineKeyboardButton("💡 Tips", callback_data="tips")],
        ]
    return InlineKeyboardMarkup(kb)

# ================================================================
# /start
# ================================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.get_or_create_user(uid)
    lang = get_lang(uid)
    car = db.get_active_car(uid)
    name = html.escape(update.effective_user.first_name or "User")
    plan_badge = "⭐ Premium" if db.is_premium(uid) else "🆓 Free"
    points = db.get_user_points(uid)
    
    if car:
        car_name = html.escape(str(car[2]))
        car_model = html.escape(str(car[3]))
        pct = car[7]
        icon = utils.get_battery_icon(pct)
        bar = utils.format_battery_bar(pct, 15)
        if lang == "MM":
            msg = (f"⚡━━━━━━━━━━━━━━━━━━⚡\n"
                   f"   <b>EV HELPER</b> — {plan_badge}\n"
                   f"⚡━━━━━━━━━━━━━━━━━━⚡\n\n"
                   f"👋 ကြိုဆိုပါတယ်, <b>{name}</b>!\n"
                   f"🏆 သင်၏ Points: <b>{points}</b>\n\n"
                   f"🚗 <b>{car_name}</b> ({car_model})\n"
                   f"{icon} Battery: <b>{pct}%</b>\n"
                   f"<code>[{bar}]</code>\n\n"
                   f"🔽 <i>ဘာကူညီရမလဲ?</i>")
        else:
            msg = (f"⚡━━━━━━━━━━━━━━━━━━⚡\n"
                   f"   <b>EV HELPER</b> — {plan_badge}\n"
                   f"⚡━━━━━━━━━━━━━━━━━━⚡\n\n"
                   f"👋 Welcome back, <b>{name}</b>!\n"
                   f"🏆 Your Points: <b>{points}</b>\n\n"
                   f"🚗 <b>{car_name}</b> ({car_model})\n"
                   f"{icon} Battery: <b>{pct}%</b>\n"
                   f"<code>[{bar}]</code>\n\n"
                   f"🔽 <i>How can I help?</i>")
    else:
        if lang == "MM":
            msg = (f"⚡━━━━━━━━━━━━━━━━━━⚡\n"
                   f"   <b>EV HELPER BOT</b>\n"
                   f"⚡━━━━━━━━━━━━━━━━━━⚡\n\n"
                   f"🚀 မင်္ဂလာပါ, <b>{name}</b>!\n"
                   f"🏆 သင်၏ Points: <b>{points}</b>\n\n"
                   f"Myanmar ရဲ့ အပြည့်စုံဆုံး EV Assistant ကို ကြိုဆိုပါတယ်!\n\n"
                   f"🔋 Battery Tracking\n"
                   f"🗺️ Route Planning\n"
                   f"🔌 Charging Stations\n"
                   f"🤖 AI Assistant\n\n"
                   f"👇 ကား မှတ်ပုံတင်ပြီး စတင်ပါ!")
        else:
            msg = (f"⚡━━━━━━━━━━━━━━━━━━⚡\n"
                   f"   <b>EV HELPER BOT</b>\n"
                   f"⚡━━━━━━━━━━━━━━━━━━⚡\n\n"
                   f"🚀 Hello, <b>{name}</b>!\n"
                   f"🏆 Your Points: <b>{points}</b>\n\n"
                   f"Myanmar's most complete EV Assistant!\n\n"
                   f"🔋 Battery Tracking\n"
                   f"🗺️ Route Planning\n"
                   f"🔌 Charging Stations\n"
                   f"🤖 AI Assistant\n\n"
                   f"👇 Register your car to get started!")

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

    data = query.data
    if data in ("back_menu", "start"):        await start(update, context)
    elif data == "stat":                       await status(update, context)
    elif data == "hist":                       await history(update, context)
    elif data == "find":                       await find_station(update, context)
    elif data == "tips":                       await tips(update, context)
    elif data == "cars":                       await show_cars(update, context)
    elif data == "favs":                       await show_favorites(update, context)
    elif data == "lang":                       await lang_menu(update, context)
    elif data == "upgrade":                    await upgrade_menu(update, context)
    elif data == "reminders":                  await show_reminders(update, context)
    elif data == "bhealth_start":              await bhealth_start(update, context)
    elif data == "degrade_start":              await degrade_show(update, context)
    elif data == "expense_start":              await expense_menu(update, context)
    elif data == "monthly_report":             await monthly_report(update, context)
    elif data == "visual_charts":              await visual_charts_menu(update, context)
    elif data == "chart_battery":              await send_battery_chart(update, context)
    elif data == "chart_expense":              await send_expense_chart(update, context)
    elif data == "export_history":             await export_history(update, context)
    elif data == "knowledge_base":             await knowledge_base(update, context)
    elif data.startswith("kb_"):               await knowledge_base_article(update, context)
    elif data.startswith("report_station_"):   await report_station_menu(update, context)
    elif data.startswith("do_report_"):        await do_station_report(update, context)
    elif data.startswith("exp_cat_"):          await expense_set_cat(update, context)
    elif data == "add_reminder_menu":          await add_reminder_menu(update, context)
    elif data.startswith("add_reminder_"):
        rtype = data.replace("add_reminder_", "")
        await do_add_reminder(update, context, rtype)
    elif data == "lang_mm":
        db.set_language(uid, "MM")
        await query.message.reply_html(utils.t("MM", "lang_set"), reply_markup=get_main_menu("MM"))
    elif data == "lang_en":
        db.set_language(uid, "EN")
        await query.message.reply_html(utils.t("EN", "lang_set"), reply_markup=get_main_menu("EN"))
    elif data.startswith("switch_car_"):
        db.switch_car(uid, int(data.replace("switch_car_", "")))
        await query.answer("✅ ကား ပြောင်းပြီး!", show_alert=True)
        await show_cars(update, context)
    elif data.startswith("del_car_"):
        db.delete_car(uid, int(data.replace("del_car_", "")))
        await query.answer("🗑️ ဖျက်ပြီး!", show_alert=True)
        await show_cars(update, context)
    elif data.startswith("del_fav_"):
        db.delete_favorite(uid, int(data.replace("del_fav_", "")))
        await query.answer(utils.t(lang, "deleted"), show_alert=True)
        await show_favorites(update, context)
    elif data.startswith("save_fav_"):
        parts = data.split("|")
        if len(parts) >= 5:
            db.add_favorite(uid, parts[1], parts[2], float(parts[3]), float(parts[4]))
            await query.answer(utils.t(lang, "saved"), show_alert=True)
    elif data.startswith("del_reminder_"):
        db.delete_reminder(uid, int(data.replace("del_reminder_", "")))
        await query.answer("🗑️ ဖျက်ပြီး!", show_alert=True)
        await show_reminders(update, context)
    elif data.startswith("admin_"):
        await admin_callback_handler(update, context)

# ================================================================
# REGISTRATION
# ================================================================
async def reg_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    msg_obj = u.callback_query.message if u.callback_query else u.message
    if u.callback_query: await u.callback_query.answer()
    if not db.is_premium(uid) and db.get_cars_count(uid) >= 1:
        ok, data = check_premium(uid, lang)
        return await msg_obj.reply_html(data[0], reply_markup=data[1])
    await msg_obj.reply_text("🚗 ကားအမည် ရိုက်ပါ။ (ဥပမာ: ကျွန်တော့်ကား)" if lang == "MM"
                              else "🚗 Enter a name for your car. (e.g. My Tesla)")
    return S_CAR_NAME

async def reg_car_name(u: Update, c: ContextTypes.DEFAULT_TYPE):
    c.user_data["car_name"] = u.message.text.strip()
    lang = get_lang(u.effective_user.id)
    await u.message.reply_text("🚗 Model ရိုက်ပါ။ (ဥပမာ: Toyota bZ3X)" if lang == "MM"
                                else "🚗 Enter car model. (e.g. Tesla Model 3)")
    return S_MODEL

async def reg_model(u: Update, c: ContextTypes.DEFAULT_TYPE):
    model = u.message.text.strip()
    c.user_data["model"] = model
    rate = get_charge_rate(model)
    c.user_data["rate"] = rate
    lang = get_lang(u.effective_user.id)
    await u.message.reply_html(
        f"⚡ Charge Rate: <b>{rate} kW</b> (Auto-detected)\n\n" +
        ("🔋 Battery Capacity (kWh) ရိုက်ပါ။ (ဥပမာ: 72.8)" if lang == "MM"
         else "🔋 Enter battery capacity in kWh. (e.g. 72.8)"))
    return S_CAP

async def reg_cap(u: Update, c: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(u.effective_user.id)
    try:
        c.user_data["cap"] = float(u.message.text.strip())
        await u.message.reply_text("🛣️ Full Range (km) ရိုက်ပါ။ (ဥပမာ: 450)" if lang == "MM"
                                    else "🛣️ Enter full range in km. (e.g. 450)")
        return S_RANGE
    except ValueError:
        await u.message.reply_text("❌ ဂဏန်းသာ ရိုက်ပါ။ (ဥပမာ: 72.8)")
        return S_CAP

async def reg_range(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    try:
        full_range = float(u.message.text.strip())
        db.add_car(uid, c.user_data["car_name"], c.user_data["model"],
                   c.user_data["cap"], full_range, c.user_data.get("rate", 50))
        await u.message.reply_html(
            f"🏆 <b>မှတ်ပုံတင်ပြီးပါပြီ!</b>\n\n"
            f"🚗 <b>{c.user_data['car_name']}</b> ({c.user_data['model']})\n"
            f"{'─' * 22}\n"
            f"🔋 Battery: <b>{c.user_data['cap']} kWh</b>\n"
            f"🛣️ Range: <b>{full_range} km</b>\n"
            f"⚡ Charge Rate: <b>{c.user_data.get('rate',50)} kW</b>\n"
            f"{'─' * 22}\n"
            f"✅ EV Helper Bot မှ ကြိုဆိုပါတယ်! 🎉",
            reply_markup=get_main_menu(lang))
    except ValueError:
        await u.message.reply_text("❌ ဂဏန်းသာ ရိုက်ပါ။")
        return S_RANGE
    return ConversationHandler.END

# ================================================================
# BATTERY UPDATE
# ================================================================
async def update_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    msg_obj = u.callback_query.message if u.callback_query else u.message
    if u.callback_query: await u.callback_query.answer()
    lang = get_lang(u.effective_user.id)
    await msg_obj.reply_text("🔋 လက်ရှိ Battery % (0-100)" if lang == "MM" else "🔋 Enter battery % (0-100)")
    return S_PCT

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
        await u.message.reply_html(
            (f"✅ Battery <b>{pct}%</b> မှတ်သားပြီး။" if lang == "MM"
             else f"✅ Battery updated to <b>{pct}%</b>.") + warning,
            reply_markup=get_main_menu(lang))
    except ValueError:
        await u.message.reply_text("❌ 0-100 ဂဏန်းဖြင့်သာ ရိုက်ပါ။")
        return S_PCT
    return ConversationHandler.END

# ================================================================
# CHARGE TIME
# ================================================================
async def chargetime_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    msg_obj = u.callback_query.message if u.callback_query else u.message
    if u.callback_query: await u.callback_query.answer()
    lang = get_lang(u.effective_user.id)
    await msg_obj.reply_text("🔋 လက်ရှိ Battery % :" if lang == "MM" else "🔋 Current battery %:")
    return S_CT_START

async def chargetime_get_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    try:
        pct = int(u.message.text.strip())
        if not (0 <= pct <= 100): raise ValueError
        c.user_data["ct_start"] = pct
        await u.message.reply_text("🎯 Target % :")
        return S_CT_END
    except ValueError:
        await u.message.reply_text("❌ 0-100 ဂဏန်းဖြင့်သာ ရိုက်ပါ။")
        return S_CT_START

async def chargetime_calculate(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    try:
        end_pct = int(u.message.text.strip())
        if not (0 <= end_pct <= 100): raise ValueError
        start_pct = c.user_data["ct_start"]
        if end_pct <= start_pct:
            await u.message.reply_text(f"❌ Target {start_pct}% ထက် ကြီးရမည်။")
            return S_CT_END
        car = db.get_active_car(uid)
        if not car:
            await u.message.reply_text(utils.t(lang, "no_car"), reply_markup=get_main_menu(lang))
            return ConversationHandler.END
        cap, rate = float(car[4]), get_charge_rate(car[3])
        minutes = utils.calculate_charge_time(start_pct, end_pct, cap, rate)
        kwh = cap * (end_pct - start_pct) / 100
        await u.message.reply_html(
            f"⏱️ <b>{'အားသွင်းကြာချိန်' if lang=='MM' else 'Charge Time'}</b>\n\n"
            f"🚗 {car[2]} | ⚡ {rate}kW\n"
            f"🔋 {start_pct}% → {end_pct}% ({kwh:.1f}kWh)\n"
            f"⏱️ <b>{utils.format_charge_time(minutes)}</b>",
            reply_markup=InlineKeyboardMarkup([back_row(lang)]))
        return ConversationHandler.END
    except ValueError:
        await u.message.reply_text("❌ 0-100 ဂဏန်းဖြင့်သာ ရိုက်ပါ။")
        return S_CT_END

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
    weather_text = ""
    if db.is_premium(uid) and c.user_data.get("last_lat"):
        wd = utils.get_weather_and_range(c.user_data["last_lat"], c.user_data["last_lon"], float(car[5]), pct)
        weather_text = utils.format_weather_range(wd, lang)
    elif not db.is_premium(uid):
        weather_text = "\n\n⭐ Weather Range: Premium feature"
    bar = utils.format_battery_bar(pct, 15)
    if lang == "MM":
        msg = (f"📊 <b>လက်ရှိအခြေအနေ</b>\n\n"
               f"🚗 <b>{car[2]}</b> ({car[3]})\n"
               f"{'─' * 22}\n"
               f"{icon} Battery: <b>{pct}%</b>{warning}\n"
               f"<code>[{bar}]</code>\n"
               f"{'─' * 22}\n"
               f"🛣️ မောင်းနိုင်သည့်ခရီး: <b>{current_range:.1f} km</b>\n"
               f"⚡ Charge Rate: <b>{get_charge_rate(car[3])} kW</b>{weather_text}")
    else:
        msg = (f"📊 <b>Current Status</b>\n\n"
               f"🚗 <b>{car[2]}</b> ({car[3]})\n"
               f"{'─' * 22}\n"
               f"{icon} Battery: <b>{pct}%</b>{warning}\n"
               f"<code>[{bar}]</code>\n"
               f"{'─' * 22}\n"
               f"🛣️ Est. Range: <b>{current_range:.1f} km</b>\n"
               f"⚡ Charge Rate: <b>{get_charge_rate(car[3])} kW</b>{weather_text}")
    await msg_obj.reply_html(msg, reply_markup=InlineKeyboardMarkup([back_row(lang)]))

# ================================================================
# HISTORY
# ================================================================
async def history(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    days = None if db.is_premium(uid) else 7
    logs = db.get_logs(uid, days=days)
    msg_obj = u.callback_query.message if u.callback_query else u.message
    if not logs:
        return await msg_obj.reply_text(utils.t(lang, "no_history"), reply_markup=back_button(lang))
    note = ("" if db.is_premium(uid) else
            ("\n<i>⭐ Premium: မှတ်တမ်း အကန့်အသတ်မဲ့</i>" if lang=="MM"
             else "\n<i>⭐ Premium: Unlimited history</i>"))
    title = "📜 <b>Battery မှတ်တမ်း</b>" if lang=="MM" else "📜 <b>Battery History</b>"
    await msg_obj.reply_html(title + note + "\n\n" + utils.format_logs_chart(logs),
                              reply_markup=back_button(lang))

# ================================================================
# FIND STATION — FIXED
# ================================================================
async def find_station(u: Update, c: ContextTypes.DEFAULT_TYPE):
    msg_obj = u.callback_query.message if u.callback_query else u.message
    lang = get_lang(u.effective_user.id)
    label = "📍 တည်နေရာပေးပို့" if lang == "MM" else "📍 Share Location"
    kb = [[KeyboardButton(label, request_location=True)]]
    await msg_obj.reply_text(
        "Station ရှာရန် တည်နေရာပေးပါ။" if lang == "MM" else "Share location to find stations.",
        reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True))

async def location_handler(u: Update, c: ContextTypes.DEFAULT_TYPE):
    import html as html_lib
    uid = u.effective_user.id
    lang = get_lang(uid)
    lat = u.message.location.latitude
    lon = u.message.location.longitude
    c.user_data["last_lat"] = lat
    c.user_data["last_lon"] = lon

    loading = await u.message.reply_text(
        "🔍 အားသွင်းစခန်းများ ရှာဖွေနေပါသည်..." if lang == "MM" else "🔍 Searching for stations...",
        reply_markup=ReplyKeyboardRemove())

    try:
        stations = charge_api.get_nearby_charging_stations(lat, lon, distance=10, max_results=5)
    except Exception as e:
        logger.error(f"Station API error: {e}")
        await loading.delete()
        return await u.message.reply_text(
            "❌ Station ရှာမရပါ။ နောက်မှ ထပ်စမ်းပါ။" if lang == "MM" else "❌ Search failed. Try again.",
            reply_markup=get_main_menu(lang))

    await loading.delete()

    if not stations:
        return await u.message.reply_text(
            "😔 သင့်အနီးတွင် Station မတွေ့ပါ။" if lang == "MM" else "😔 No stations found nearby.",
            reply_markup=get_main_menu(lang))

    is_prem = db.is_premium(uid)

    # Send each station as separate message to avoid HTML length/parse issues
    header = f"🔌 <b>အနီးဆုံး Station {len(stations[:5])} ခု တွေ့ပါသည်:</b>" if lang == "MM" else f"🔌 <b>Found {len(stations[:5])} nearby stations:</b>"
    await u.message.reply_html(header)

    for i, station in enumerate(stations[:5]):
        try:
            info = station.get("addressInfo", {})
            name = html_lib.escape(str(info.get("title", "Unknown"))[:60])
            address = html_lib.escape(str(info.get("addressLine1", "") or "")[:100])
            dist = float(info.get("distance", 0))
            s_lat = info.get("latitude") or lat
            s_lon = info.get("longitude") or lon

            maps_link = f"https://www.google.com/maps/dir/?api=1&destination={s_lat},{s_lon}"
            view_link = f"https://www.google.com/maps/search/?api=1&query={s_lat},{s_lon}"

            # Build connection info
            conns = station.get("connections", [])
            conn_text = ""
            if conns:
                details = []
                for cn in conns[:4]:
                    try:
                        ct = str(cn.get("connectionType", {}).get("title", "Unknown") or "Unknown")
                        pw = cn.get("powerKW")
                        pw_str = f"{int(pw)}kW" if pw else "?"
                        details.append(f"{html_lib.escape(ct)} ({pw_str})")
                    except:
                        continue
                if details:
                    conn_text = f"\n   ⚡ {', '.join(details)}"

            addr_text = f"\n   📍 {address}" if address else ""

            msg = (f"{i+1}. <b>{name}</b> ({dist:.1f} km)"
                   f"{addr_text}"
                   f"{conn_text}\n"
                   f"   <a href=\"{maps_link}\">🗺️ Navigate</a> | <a href=\"{view_link}\">📌 View on Map</a>")

            # Keyboard for this station
            station_kb = []
            # Community report status
            station_id = f"{s_lat:.4f}_{s_lon:.4f}"
            last_report = db.get_station_last_report(station_id)
            if last_report:
                from datetime import datetime as dt2
                status_icons = {"online": "🟢", "broken": "🔴", "no_power": "🟡", "busy": "🟠"}
                status_labels = {"online": "အလုပ်လုပ်နေတယ်", "broken": "စက်ပျက်", "no_power": "မီးပျက်", "busy": "လူကျနေတယ်"}
                s_icon = status_icons.get(last_report[0], "⚪")
                s_label = status_labels.get(last_report[0], last_report[0])
                try:
                    reported_time = dt2.fromisoformat(last_report[1])
                    mins_ago = int((dt2.now() - reported_time).total_seconds() / 60)
                    time_str = f"{mins_ago} မိနစ်" if mins_ago < 60 else f"{mins_ago//60} နာရီ"
                except:
                    time_str = "မကြာမီ"
                msg += f"\n   {s_icon} <i>Last report ({time_str} ago): {s_label}</i>"
            station_kb.append([InlineKeyboardButton(
                "📢 Report Status", callback_data=f"report_station_{station_id}_{name[:15]}")])
            if is_prem:
                raw_name = str(info.get("title", "Unknown"))[:20]
                raw_addr = str(info.get("addressLine1", "") or "N/A")[:30]
                cb = f"save_fav_|{raw_name}|{raw_addr}|{s_lat}|{s_lon}"
                station_kb.append([InlineKeyboardButton("⭐ Save to Favorites", callback_data=cb)])

            await u.message.reply_html(
                msg,
                disable_web_page_preview=True,
                reply_markup=InlineKeyboardMarkup(station_kb) if station_kb else None)

        except Exception as e:
            logger.error(f"Station {i} send error: {e}")
            continue

    # Final menu
    footer_kb = []
    if not is_prem:
        footer_kb.append([InlineKeyboardButton("⭐ Favorites သိမ်းဖို့ Premium လိုသည်", callback_data="upgrade")])
    footer_kb.append(back_row(lang))
    await u.message.reply_text(
        "✅ ရှာဖွေမှု ပြီးပါပြီ။" if lang == "MM" else "✅ Search complete.",
        reply_markup=InlineKeyboardMarkup(footer_kb))

# ================================================================
# ROUTE PLANNER (Premium) — FIXED
# ================================================================
async def route_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    msg_obj = u.callback_query.message if u.callback_query else u.message
    if u.callback_query: await u.callback_query.answer()

    if not db.is_premium(uid):
        ok, data = check_premium(uid, lang)
        await msg_obj.reply_html(data[0], reply_markup=data[1])
        return ConversationHandler.END

    car = db.get_active_car(uid)
    if not car:
        await msg_obj.reply_text(utils.t(lang, "no_car"), reply_markup=get_main_menu(lang))
        return ConversationHandler.END

    await msg_obj.reply_text(
        "🗺️ ထွက်ခွာမြို့ ရိုက်ပါ။\n(ဥပမာ: Yangon, Mandalay, Bago ...)"
        if lang == "MM" else
        "🗺️ Enter origin city.\n(e.g. Yangon, Mandalay, Bago ...)")
    return S_RT_FROM

def resolve_city_name(city_input):
    """မြန်မာဘာသာ သို့မဟုတ် အင်္ဂလိပ် မြို့နာမည် ကို geocode လုပ်တယ်"""
    # မြန်မာဘာသာ mapping စစ်တယ်
    eng_name = MM_CITY_MAP.get(city_input.strip(), city_input.strip())
    return charge_api.geocode_city(eng_name)

async def route_get_from(u: Update, c: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(u.effective_user.id)
    city_input = u.message.text.strip()

    loading = await u.message.reply_text("🔍 မြို့ ရှာဖွေနေပါသည်..." if lang == "MM" else "🔍 Looking up city...")
    lat, lon, display_name = resolve_city_name(city_input)
    await loading.delete()

    if lat is None:
        await u.message.reply_text(
            f"❌ '{city_input}' မတွေ့ပါ။\nဥပမာ: ရန်ကုန်, မန္တလေး, Yangon, Mandalay"
            if lang == "MM" else
            f"❌ '{city_input}' not found.\nExample: Yangon, Mandalay, Bago")
        return S_RT_FROM

    c.user_data["rt_from_lat"] = lat
    c.user_data["rt_from_lon"] = lon
    c.user_data["rt_from_name"] = display_name.split(",")[0]

    await u.message.reply_text(
        f"✅ {display_name.split(',')[0]} တွေ့ပါပြီ!\n\n🏁 ဆုံးမှတ်မြို့ ရိုက်ပါ။"
        if lang == "MM" else
        f"✅ Found: {display_name.split(',')[0]}\n\n🏁 Enter destination city.")
    return S_RT_TO

async def route_get_to(u: Update, c: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(u.effective_user.id)
    city_input = u.message.text.strip()

    loading = await u.message.reply_text("🔍 မြို့ ရှာဖွေနေပါသည်..." if lang == "MM" else "🔍 Looking up city...")
    lat, lon, display_name = resolve_city_name(city_input)
    await loading.delete()

    if lat is None:
        await u.message.reply_text(
            f"❌ '{city_input}' မတွေ့ပါ။\nဥပမာ: ရန်ကုန်, မန္တလေး, Yangon, Mandalay"
            if lang == "MM" else
            f"❌ '{city_input}' not found.\nExample: Yangon, Mandalay, Bago")
        return S_RT_TO

    from_name = c.user_data.get("rt_from_name", "")
    if display_name.split(",")[0].lower() == from_name.lower():
        await u.message.reply_text("❌ ထွက်မြို့နဲ့ ဆုံးမြို့ မတူညီရပါ။" if lang == "MM" else "❌ Origin and destination must be different.")
        return S_RT_TO

    c.user_data["rt_to_lat"] = lat
    c.user_data["rt_to_lon"] = lon
    c.user_data["rt_to_name"] = display_name.split(",")[0]

    await u.message.reply_text(
        f"✅ {display_name.split(',')[0]} တွေ့ပါပြီ!\n\n🔋 လက်ရှိ Battery % ရိုက်ပါ။"
        if lang == "MM" else
        f"✅ Found: {display_name.split(',')[0]}\n\n🔋 Enter current battery %")
    return S_RT_PCT

async def route_calculate(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    try:
        current_pct = int(u.message.text.strip())
        if not (0 <= current_pct <= 100): raise ValueError

        car = db.get_active_car(uid)
        full_range = float(car[5])
        battery_cap = float(car[4])
        charge_rate = get_charge_rate(car[3])

        from_name = c.user_data["rt_from_name"]
        to_name = c.user_data["rt_to_name"]
        from_lat = c.user_data["rt_from_lat"]
        from_lon = c.user_data["rt_from_lon"]
        to_lat = c.user_data["rt_to_lat"]
        to_lon = c.user_data["rt_to_lon"]

        total_distance = utils.calculate_distance(from_lat, from_lon, to_lat, to_lon)
        current_range = full_range * (current_pct / 100)

        # Google Maps link for full route
        gmaps_route = f"https://www.google.com/maps/dir/?api=1&origin={from_lat},{from_lon}&destination={to_lat},{to_lon}"

        if current_range >= total_distance * 1.1:
            remaining_pct = max(0, current_pct - int(total_distance / full_range * 100))
            if lang == "MM":
                msg = (f"🗺️ <b>Route Plan</b>\n\n"
                       f"📍 {from_name} → {to_name}\n"
                       f"📏 ခရီးဝေး: <b>{total_distance:.0f} km</b>\n"
                       f"🔋 Range: <b>{current_range:.0f} km</b>\n\n"
                       f"✅ <b>တစ်ကြိမ်တည်း မောင်းနိုင်သည်!</b>\n"
                       f"ဆုံးမှတ်ရောက်ရင် Battery: ~{remaining_pct}% ကျန်မည်\n\n"
                       f"<a href=\"{gmaps_route}\">🗺️ Google Maps တွင် ကြည့်ရန်</a>")
            else:
                msg = (f"🗺️ <b>Route Plan</b>\n\n"
                       f"📍 {from_name} → {to_name}\n"
                       f"📏 Distance: <b>{total_distance:.0f} km</b>\n"
                       f"🔋 Range: <b>{current_range:.0f} km</b>\n\n"
                       f"✅ <b>Can reach without charging!</b>\n"
                       f"Est. remaining: ~{remaining_pct}%\n\n"
                       f"<a href=\"{gmaps_route}\">🗺️ View on Google Maps</a>")
            await u.message.reply_html(msg, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup([back_row(lang)]))
            return ConversationHandler.END
        else:
            import html as html_lib
            safe_range = full_range * 0.75
            stops_needed = max(1, int(total_distance / safe_range))
            stop_every_km = total_distance / (stops_needed + 1)
            charge_to_pct = min(85, int(stop_every_km / full_range * 100) + 20)
            charge_time = utils.calculate_charge_time(20, charge_to_pct, battery_cap, charge_rate)

            # Send header first
            header = (f"🗺️ <b>Route Plan</b>\n\n"
                      f"📍 {from_name} → {to_name}\n"
                      f"📏 {'ခရီးဝေး' if lang=='MM' else 'Distance'}: <b>{total_distance:.0f} km</b>\n"
                      f"🔋 Range: <b>{current_range:.0f} km</b>\n\n"
                      f"⚡ <b>Charging Stop {stops_needed} {'ကြိမ် လိုသည်' if lang=='MM' else 'stop(s) needed'}</b>\n\n"
                      f"📋 <b>{'အကြံပြုချက်' if lang=='MM' else 'Recommendations'}:</b>\n"
                      f"• {'Stop တိုင်းမှာ' if lang=='MM' else 'Charge to'} <b>{charge_to_pct}%</b> {'အထိ အားသွင်းပါ' if lang=='MM' else 'at each stop'}\n"
                      f"• {'တစ် Stop ကြာချိန်' if lang=='MM' else 'Time per stop'}: ~<b>{utils.format_charge_time(charge_time)}</b>\n\n"
                      f"<a href=\"{gmaps_route}\">🗺️ {'Google Maps တွင် ကြည့်ရန်' if lang=='MM' else 'View on Google Maps'}</a>")
            await u.message.reply_html(header, disable_web_page_preview=True,
                                        reply_markup=InlineKeyboardMarkup([back_row(lang)]))

            # Send each stop with real station info
            for i in range(stops_needed):
                stop_lat = from_lat + (to_lat - from_lat) * (i + 1) / (stops_needed + 1)
                stop_lon = from_lon + (to_lon - from_lon) * (i + 1) / (stops_needed + 1)
                dist = stop_every_km * (i + 1)

                # Search real station near stop point
                try:
                    nearby = charge_api.get_nearby_charging_stations(stop_lat, stop_lon, distance=50, max_results=1)
                except:
                    nearby = []

                if nearby:
                    s = nearby[0]
                    info = s.get("addressInfo", {})
                    s_name = html_lib.escape(str(info.get("title", "Unknown"))[:50])
                    s_addr = html_lib.escape(str(info.get("addressLine1", "") or "")[:80])
                    s_lat = info.get("latitude") or stop_lat
                    s_lon = info.get("longitude") or stop_lon
                    s_dist = float(info.get("distance", 0))
                    conns = s.get("connections", [])
                    conn_details = []
                    for cn in conns[:3]:
                        try:
                            ct = html_lib.escape(str(cn.get("connectionType", {}).get("title", "?") or "?"))
                            pw = cn.get("powerKW")
                            conn_details.append(f"{ct} ({int(pw)}kW)" if pw else ct)
                        except:
                            continue
                    conn_text = f"\n   ⚡ {', '.join(conn_details)}" if conn_details else ""
                    addr_text = f"\n   📍 {s_addr}" if s_addr else ""
                    nav_link = f"https://www.google.com/maps/dir/?api=1&destination={s_lat},{s_lon}"
                    view_link = f"https://www.google.com/maps/search/?api=1&query={s_lat},{s_lon}"
                    stop_msg = (f"🔌 <b>Stop {i+1}</b> — {from_name} မှ <b>{dist:.0f} km</b> ({s_dist:.0f} km {'လမ်းကြောင်းမှ' if lang=='MM' else 'off route'})\n"
                                f"   <b>{s_name}</b>{addr_text}{conn_text}\n"
                                f"   <a href=\"{nav_link}\">🗺️ Navigate</a> | <a href=\"{view_link}\">📌 View on Map</a>")
                else:
                    search_link = f"https://www.google.com/maps/search/EV+charging+station/@{stop_lat:.4f},{stop_lon:.4f},10z"
                    stop_msg = (f"🔌 <b>Stop {i+1}</b> — {from_name} မှ <b>{dist:.0f} km</b>\n"
                                f"   <a href=\"{search_link}\">🔍 {'ဒီနေရာတွင် Station ရှာပါ' if lang=='MM' else 'Search Station here'}</a>")

                await u.message.reply_html(stop_msg, disable_web_page_preview=True)

            return ConversationHandler.END

    except ValueError:
        await u.message.reply_text("❌ 0-100 ဂဏန်းဖြင့်သာ ရိုက်ပါ။")
        return S_RT_PCT

# ================================================================
# COST CALCULATOR
# ================================================================
async def cost_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    msg_obj = u.callback_query.message if u.callback_query else u.message
    if u.callback_query: await u.callback_query.answer()
    uid = u.effective_user.id
    lang = get_lang(uid)
    car = db.get_active_car(uid)
    if not car:
        return await msg_obj.reply_text(utils.t(lang, "no_car"), reply_markup=get_main_menu(lang))
    await msg_obj.reply_text("🔋 လက်ရှိ Battery % :" if lang == "MM" else "🔋 Current battery %:")
    return S_COST_START

async def cost_get_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(u.effective_user.id)
    try:
        pct = int(u.message.text.strip())
        if not (0 <= pct <= 100): raise ValueError
        c.user_data["cost_start"] = pct
        await u.message.reply_text("🎯 Target % :" if lang == "MM" else "🎯 Target %:")
        return S_COST_END
    except ValueError:
        await u.message.reply_text("❌ 0-100 ဂဏန်းဖြင့်သာ ရိုက်ပါ။")
        return S_COST_START

async def cost_calculate(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    try:
        end_pct = int(u.message.text.strip())
        if not (0 <= end_pct <= 100): raise ValueError
        start_pct = c.user_data["cost_start"]
        if end_pct <= start_pct:
            await u.message.reply_text(f"❌ Target {start_pct}% ထက် ကြီးရမည်။")
            return S_COST_END
        car = db.get_active_car(uid)
        cap = float(car[4])
        kwh = cap * (end_pct - start_pct) / 100
        cost = int(kwh * ELECTRICITY_RATE_MMK)
        charge_time = utils.calculate_charge_time(start_pct, end_pct, cap, get_charge_rate(car[3]))
        await u.message.reply_html(
            f"💰 <b>{'Charging Cost' if lang=='EN' else 'အားသွင်းကုန်ကျစရိတ်'}</b>\n\n"
            f"🚗 {car[2]} ({car[3]})\n"
            f"🔋 {start_pct}% → {end_pct}%\n"
            f"⚡ {kwh:.1f} kWh\n"
            f"💵 <b>MMK {cost:,}</b>\n"
            f"⏱️ {utils.format_charge_time(charge_time)}\n\n"
            f"<i>* MMK {ELECTRICITY_RATE_MMK}/kWh</i>",
            reply_markup=InlineKeyboardMarkup([back_row(lang)]))
        return ConversationHandler.END
    except ValueError:
        await u.message.reply_text("❌ 0-100 ဂဏန်းဖြင့်သာ ရိုက်ပါ။")
        return S_COST_END

# ================================================================
# REMINDERS
# ================================================================

async def show_reminders(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    if u.callback_query:
        await u.callback_query.answer()
        msg_obj = u.callback_query.message
    else:
        msg_obj = u.message
    reminders = db.get_reminders(uid)

    kb_add = [InlineKeyboardButton("➕ Reminder ထည့်" if lang=="MM" else "➕ Add Reminder",
                                    callback_data="add_reminder_menu")]

    if not reminders:
        return await msg_obj.reply_text(
            "🔔 Reminder မရှိသေးပါ။" if lang == "MM" else "🔔 No reminders yet.",
            reply_markup=InlineKeyboardMarkup([[kb_add], back_row(lang)]))

    msg = "🔔 <b>သင့် Reminders:</b>\n\n" if lang == "MM" else "🔔 <b>Your Reminders:</b>\n\n"
    keyboard = []
    icons = {"battery": "🔋", "tire": "🔧", "insurance": "📋", "service": "🔧"}
    for r in reminders:
        icon = icons.get(r[2], "🔔")
        msg += f"{icon} <b>{r[2].title()}</b>: {r[3]}\n"
        if r[4]: msg += f"   📝 {r[4]}\n"
        keyboard.append([InlineKeyboardButton(f"🗑️ {r[2].title()}", callback_data=f"del_reminder_{r[0]}")])
    keyboard.append([kb_add])
    keyboard.append(back_row(lang))
    await msg_obj.reply_html(msg, reply_markup=InlineKeyboardMarkup(keyboard))

async def add_reminder_menu(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    if u.callback_query:
        await u.callback_query.answer()
        msg_obj = u.callback_query.message
    else:
        msg_obj = u.message
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔋 Battery Warning", callback_data="add_reminder_battery"),
         InlineKeyboardButton("🔧 Tire Rotation", callback_data="add_reminder_tire")],
        [InlineKeyboardButton("📋 Insurance", callback_data="add_reminder_insurance"),
         InlineKeyboardButton("🔧 Service", callback_data="add_reminder_service")],
        back_row(lang)
    ])
    await msg_obj.reply_text(
        "🔔 Reminder အမျိုးအစား ရွေးပါ:" if lang == "MM" else "🔔 Select reminder type:",
        reply_markup=kb)

async def do_add_reminder(u: Update, c: ContextTypes.DEFAULT_TYPE, rtype: str):
    uid = u.effective_user.id
    lang = get_lang(uid)
    if u.callback_query:
        await u.callback_query.answer()
        msg_obj = u.callback_query.message
    else:
        msg_obj = u.message

    defaults = {
        "battery": ("Battery 20% အောက်ဆင်းရင် သတိပေး", "Low battery warning active"),
        "tire":    ("5,000 km တိုင်း တာယာ rotate လုပ်ပါ", "Rotate tires every 5,000 km"),
        "insurance": ("Insurance ကုန်ဆုံးမည့် ၃၀ ရက်မတိုင်ခင် သတိပေး", "Alert 30 days before insurance expires"),
        "service": ("10,000 km တိုင်း service လုပ်ပါ", "Service due every 10,000 km"),
    }
    mm_val, en_val = defaults.get(rtype, ("Reminder", "Reminder"))
    value = mm_val if lang == "MM" else en_val
    db.add_reminder(uid, rtype, value)

    icons = {"battery": "🔋", "tire": "🔧", "insurance": "📋", "service": "🔧"}
    icon = icons.get(rtype, "🔔")
    await msg_obj.reply_html(
        f"✅ {icon} <b>{rtype.title()} Reminder</b> သိမ်းပြီးပါပြီ!\n{value}"
        if lang == "MM" else
        f"✅ {icon} <b>{rtype.title()} Reminder</b> saved!\n{value}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Reminders ကြည့်" if lang=="MM" else "📋 View Reminders", callback_data="reminders")],
            back_row(lang)
        ]))

# ================================================================
# AI CHAT (Premium)
# ================================================================
async def ai_chat_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    msg_obj = u.callback_query.message if u.callback_query else u.message
    if u.callback_query: await u.callback_query.answer()

    if not db.is_premium(uid):
        ok, data = check_premium(uid, lang)
        await msg_obj.reply_html(data[0], reply_markup=data[1])
        return ConversationHandler.END

    if not GEMINI_API_KEY:
        await msg_obj.reply_text("❌ AI Chat မရနိုင်သေးပါ။" if lang == "MM" else "❌ AI Chat unavailable.")
        return ConversationHandler.END

    c.user_data["ai_history"] = []
    await msg_obj.reply_html(
        "🤖 <b>EV AI Assistant</b>\n\nEV နဲ့ပတ်သက်တာ မေးနိုင်ပါတယ်။\n/done နှိပ်ရင် ထွက်မည်။"
        if lang == "MM" else
        "🤖 <b>EV AI Assistant</b>\n\nAsk me anything about EVs.\nType /done to exit.")
    return S_AI_CHAT

async def ai_chat_respond(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    question = u.message.text.strip()

    if question.lower() in ("/done", "/start", "done", "/cancel"):
        await u.message.reply_text("✅ AI Chat ပြီးပါပြီ။" if lang == "MM" else "✅ Chat ended.",
                                    reply_markup=get_main_menu(lang))
        return ConversationHandler.END

    loading = await u.message.reply_text("🤔 တွေးနေပါသည်..." if lang == "MM" else "🤔 Thinking...")

    try:
        from groq import Groq
        import os

        # Railway Variables ထဲက Key ကို ဖတ်ခြင်း
        GROQ_API_KEY = os.getenv("GROQ_API_KEY")
        client = Groq(api_key=GROQ_API_KEY)

        car = db.get_active_car(uid)
        car_ctx = f"User's car: {car[3]}, {car[4]}kWh" if car else "No car registered"
        
        # မြန်မာလို အမှန်ကန်ဆုံး ပြန်ဖြေပေးဖို့ စည်းကမ်းချက်များ သတ်မှတ်ခြင်း
        system_prompt = (
            f"You are an EV expert assistant. Context: {car_ctx}. "
            "Important Rules:\n"
            "1. Answer ONLY in natural, fluent Myanmar language (Burmese).\n"
            "2. Never translate 'EV' into strange words like 'အီးဗီး' or 'ကိရိယာ'. Just use 'EV' or 'လျှပ်စစ်ကား'.\n"
            "3. Keep the tips realistic, helpful, and professional regarding Electric Vehicles (EV charging, battery care, maintenance)."
        )

        # History Formatting for Groq
        history = c.user_data.get("ai_history", [])
        groq_messages = [{"role": "system", "content": system_prompt}]
        
        for h in history[-6:]:
            role = "user" if h["role"] == "user" else "assistant"
            groq_messages.append({"role": role, "content": h["content"]})
            
        groq_messages.append({"role": "user", "content": question})

        # Groq API (Llama 3.3 70B - မြန်မာလို အကောင်းဆုံးမော်ဒယ်) ကို သုံးပြီး စာပြန်ခိုင်းခြင်း
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=groq_messages,
            temperature=0.5
        )
        
        answer = completion.choices[0].message.content
        
        # Chat History ထဲမှာ အမေးအဖြေ ပြန်သိမ်းခြင်း
        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": answer})
        c.user_data["ai_history"] = history[-10:]
        
        # Telegram Bot ထဲသို့ စာပြန်ပို့ခြင်း
        await loading.delete()
        await u.message.reply_text(
            f"🤖 {answer}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ ထွက်" if lang=="MM" else "❌ Exit", callback_data="back_menu")]])
        )

    except Exception as e:
        logger.error(f"AI error: {e}")
        if 'loading' in locals() or 'loading' in globals():
            try:
                await loading.delete()
            except:
                pass
        await u.message.reply_text(f"❌ AI Error: {e}", reply_markup=get_main_menu(lang))
        return ConversationHandler.END

    return S_AI_CHAT



# ================================================================
# CARS / FAVORITES / TIPS / LANG / PREMIUM
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
        msg += f"{active}<b>{car[2]}</b> — {car[3]} | {car[7]}%\n"
        row = []
        if car[8] != 1:
            row.append(InlineKeyboardButton(f"✅ {car[2]}", callback_data=f"switch_car_{car[0]}"))
        row.append(InlineKeyboardButton(f"🗑️ {car[2]}", callback_data=f"del_car_{car[0]}"))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("➕ ကားထပ်ထည့်" if lang=="MM" else "➕ Add Car", callback_data="reg_start")])
    keyboard.append(back_row(lang))
    await msg_obj.reply_html(msg, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_favorites(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    msg_obj = u.callback_query.message
    if not db.is_premium(uid):
        ok, data = check_premium(uid, lang)
        return await msg_obj.reply_html(data[0], reply_markup=data[1])
    favs = db.get_favorites(uid)
    if not favs:
        return await msg_obj.reply_text(utils.t(lang, "no_favorites"), reply_markup=back_button(lang))
    msg = "📍 <b>Favorite Stations:</b>\n\n"
    keyboard = []
    for fav in favs:
        maps_link = f"https://www.google.com/maps/dir/?api=1&destination={fav[4]},{fav[5]}"
        name_safe = str(fav[2]).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
        msg += f"⭐ <b>{name_safe}</b>\n   <a href=\"{maps_link}\">🗺️ Navigate</a>\n\n"
        keyboard.append([InlineKeyboardButton(f"🗑️ {name_safe[:25]}", callback_data=f"del_fav_{fav[0]}")])
    keyboard.append(back_row(lang))
    await msg_obj.reply_html(msg, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(keyboard))

async def tips(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    if u.callback_query: await u.callback_query.answer()
    msg_obj = u.callback_query.message if u.callback_query else u.message
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📚 Knowledge Base", callback_data="knowledge_base"),
         InlineKeyboardButton("📤 Export History ⭐", callback_data="export_history")],
        back_row(lang)
    ])
    msg = ("💡 <b>EV Tips:</b>\n\n"
           "• 🟢 Battery 20%-80% ကြားထားပါ\n"
           "• 🌙 Off-peak မှာ အားသွင်းပါ\n"
           "• ❄️ အအေးမှာ range ကျနိုင်တယ်\n"
           "• ⚡ DC Fast Charge မကြာမကြာ မသုံးပါနဲ့\n"
           "• 🛣️ Eco mode သုံးရင် range တိုးတယ်\n\n"
           "📚 ပိုသိချင်ရင် Knowledge Base ကြည့်ပါ!"
           if lang == "MM" else
           "💡 <b>EV Tips:</b>\n\n"
           "• 🟢 Keep battery 20%-80%\n"
           "• 🌙 Charge during off-peak hours\n"
           "• ❄️ Cold weather reduces range\n"
           "• ⚡ Avoid frequent DC Fast Charging\n"
           "• 🛣️ Eco mode increases range\n\n"
           "📚 Learn more in the Knowledge Base!")
    await msg_obj.reply_html(msg, reply_markup=kb)

async def lang_menu(u: Update, c: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(u.effective_user.id)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🇲🇲 မြန်မာ", callback_data="lang_mm"),
         InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
        back_row(lang)])
    await u.callback_query.message.reply_text("🌐 ဘာသာစကား ရွေးပါ:", reply_markup=kb)

async def upgrade_menu(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    msg_obj = u.callback_query.message
    if db.is_premium(uid):
        expire = db.get_expire_date(uid)
        expire_str = datetime.fromisoformat(expire).strftime("%Y-%m-%d") if expire else "N/A"
        return await msg_obj.reply_html(
            f"⭐ <b>Premium!</b>\n📅 {'သက်တမ်း' if lang=='MM' else 'Expires'}: <b>{expire_str}</b>",
            reply_markup=back_button(lang))
    msg = ("⭐ <b>Premium Plan</b>\n\n🆓 Free:\n• ကား ၁ စီး | History ၇ ရက်\n\n"
           "⭐ Premium:\n• ကား အကန့်အသတ်မဲ့ ✅\n• Route Planner ✅\n• AI Chat ✅\n• Favorites ✅\n• Weather Range ✅\n\nPlan ရွေးပါ:"
           if lang == "MM" else
           "⭐ <b>Premium Plan</b>\n\n🆓 Free:\n• 1 car | 7-day history\n\n"
           "⭐ Premium:\n• Unlimited cars ✅\n• Route Planner ✅\n• AI Chat ✅\n• Favorites ✅\n• Weather Range ✅\n\nSelect plan:")
    kb = [[InlineKeyboardButton(f"⭐ {p['label']}", callback_data=f"buy_plan_{k}")] for k,p in PLANS.items()]
    kb.append(back_row(lang))
    await msg_obj.reply_html(msg, reply_markup=InlineKeyboardMarkup(kb))

async def buy_plan(u: Update, c: ContextTypes.DEFAULT_TYPE):
    query = u.callback_query
    await query.answer()
    uid = u.effective_user.id
    lang = get_lang(uid)
    plan_key = query.data.replace("buy_plan_", "")
    plan = PLANS.get(plan_key)
    if not plan: return ConversationHandler.END
    c.user_data["selected_plan"] = plan_key
    await query.message.reply_html(
        f"💰 <b>{'ငွေလွှဲနည်း' if lang=='MM' else 'Payment Instructions'}</b>\n\n"
        f"Plan: {plan['label']}\n\n"
        f"📱 <b>KPay:</b> <code>{KPAY_NUMBER}</code>\n"
        f"📱 <b>Wave:</b> <code>{WAVE_NUMBER}</code>\n\n"
        f"Amount: <b>MMK {plan['price']:,}</b>\n\n"
        f"{'ငွေလွှဲပြီး screenshot ပို့ပါ။' if lang=='MM' else 'Send screenshot after payment.'}",
        reply_markup=back_button(lang))
    return S_PAYMENT

async def payment_screenshot_received(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    if not u.message.photo:
        await u.message.reply_text("❌ Screenshot ဓါတ်ပုံ ပို့ပေးပါ။" if lang=="MM" else "❌ Send a photo screenshot.")
        return S_PAYMENT
    plan_key = c.user_data.get("selected_plan", "1")
    plan = PLANS.get(plan_key, PLANS["1"])
    file_id = u.message.photo[-1].file_id
    payment_id = db.add_pending_payment(uid, plan["price"], plan["months"], file_id)
    await send_payment_to_admin(c, payment_id, uid, plan["months"], plan["price"], file_id)
    await u.message.reply_html(
        f"✅ <b>{'Screenshot လက်ခံပြီး!' if lang=='MM' else 'Screenshot received!'}</b>\n\n"
        f"Payment ID: <code>#{payment_id}</code>\n"
        f"{'မိနစ် ၃၀ အတွင်း Premium activate ဖြစ်မည်။' if lang=='MM' else 'Premium will activate within 30 minutes.'}",
        reply_markup=get_main_menu(lang))
    return ConversationHandler.END

# ================================================================
# OFF-PEAK REMINDER / CANCEL
# ================================================================

# ================================================================
# PHASE 2: BATTERY HEALTH TRACKER
# ================================================================
async def bhealth_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    msg_obj = u.callback_query.message if u.callback_query else u.message
    if u.callback_query: await u.callback_query.answer()
    await msg_obj.reply_text(
        "🔋 Battery SOH % ရိုက်ပါ။ (ဥပမာ: 92)\n\nSOH = State of Health, ကားနဲ့ပါလာတဲ့ app မှာ ကြည့်နိုင်ပါတယ်။"
        if lang == "MM" else
        "🔋 Enter Battery SOH % (e.g. 92)\nSOH = State of Health, check in your car app.")
    return S_BH_SOH

async def bhealth_get_soh(u: Update, c: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(u.effective_user.id)
    try:
        soh = float(u.message.text.strip())
        if not (0 <= soh <= 100): raise ValueError
        c.user_data["bh_soh"] = soh
        await u.message.reply_text(
            "🛣️ လက်ရှိ Mileage (km) ရိုက်ပါ။ (ဥပမာ: 15000)"
            if lang == "MM" else
            "🛣️ Enter current mileage in km (e.g. 15000)")
        return S_BH_MILEAGE
    except ValueError:
        await u.message.reply_text("❌ 0-100 ဂဏန်းဖြင့်သာ ရိုက်ပါ။")
        return S_BH_SOH

async def bhealth_get_mileage(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    try:
        mileage = int(u.message.text.strip().replace(",", ""))
        soh = c.user_data["bh_soh"]
        db.save_battery_health(uid, soh, mileage)
        if soh >= 90:
            status = "🟢 အလွန်ကောင်း" if lang == "MM" else "🟢 Excellent"
            tip = "Battery အခြေအနေ အကောင်းဆုံးပဲ။ 20-80% ကြားသိမ်းပါ။" if lang == "MM" else "Battery in great condition. Keep charging 20-80%."
        elif soh >= 80:
            status = "🟡 ကောင်း" if lang == "MM" else "🟡 Good"
            tip = "Battery ကောင်းနေသေးတယ်။ DC Fast Charge လျှော့သုံးပါ။" if lang == "MM" else "Battery good. Reduce DC Fast Charging."
        elif soh >= 70:
            status = "🟠 သတိထားပါ" if lang == "MM" else "🟠 Fair"
            tip = "Battery နည်းနည်း ကျဆင်းနေပြီ။ ဆိုင်မှာ စစ်ဆေးပါ။" if lang == "MM" else "Battery degrading. Check with dealer."
        else:
            status = "🔴 အစားထိုးရန် လိုသည်" if lang == "MM" else "🔴 Poor"
            tip = "Battery အစားထိုးရန် ဆိုင်သို့ သွားပါ။" if lang == "MM" else "Visit dealer for battery replacement."
        yearly_deg = max(0.5, (100 - soh) / max(1, mileage / 20000)) * 0.8
        pred_1yr = max(0, soh - yearly_deg)
        pred_3yr = max(0, soh - yearly_deg * 3)
        soh_bar = utils.format_battery_bar(int(soh), 15)
        msg = (f"🔋 <b>Battery Health Report</b>\n\n"
               f"📊 SOH: <b>{soh}%</b>\n"
               f"<code>[{soh_bar}]</code> {status}\n"
               f"🛣️ Mileage: <b>{mileage:,} km</b>\n"
               f"{'─' * 22}\n"
               f"💡 {tip}\n"
               f"{'─' * 22}\n"
               f"📈 <b>{'ခန့်မှန်းချက်' if lang=='MM' else 'Predictions'}:</b>\n"
               f"• {'၁ နှစ်နောက်' if lang=='MM' else '1 yr'}: <b>~{pred_1yr:.1f}%</b>\n"
               f"• {'၃ နှစ်နောက်' if lang=='MM' else '3 yrs'}: <b>~{pred_3yr:.1f}%</b>")
        await u.message.reply_html(msg, reply_markup=InlineKeyboardMarkup([back_row(lang)]))
        return ConversationHandler.END
    except ValueError:
        await u.message.reply_text("❌ ဂဏန်းသာ ရိုက်ပါ။")
        return S_BH_MILEAGE

# ================================================================
# PHASE 2: BATTERY DEGRADATION (Premium)
# ================================================================
async def degrade_show(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    msg_obj = u.callback_query.message if u.callback_query else u.message
    if u.callback_query: await u.callback_query.answer()
    ok, data = check_premium(uid, lang)
    if not ok:
        return await msg_obj.reply_html(data[0], reply_markup=data[1])
    history = db.get_battery_health_history(uid)
    if not history:
        return await msg_obj.reply_html(
            "📊 Battery Health data မရှိသေးပါ။\n🔋 Battery Health Tracker ကို အရင်သုံးပါ။"
            if lang == "MM" else
            "📊 No Battery Health data yet.\nUse Battery Health Tracker first.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔋 Battery Health", callback_data="bhealth_start")],
                back_row(lang)]))
    latest = history[0]
    soh = float(latest[2])
    mileage = int(latest[3])
    if len(history) >= 2:
        oldest = history[-1]
        soh_diff = float(oldest[2]) - soh
        mile_diff = max(1, mileage - int(oldest[3]))
        deg_per_10k = (soh_diff / mile_diff) * 10000
    else:
        deg_per_10k = 1.5
    msg = (f"💀 <b>Battery Degradation Prediction</b>\n\n"
           f"📊 SOH: <b>{soh}%</b> @ {mileage:,} km\n"
           f"📉 ~{deg_per_10k:.1f}% per 10,000 km\n\n"
           f"<b>{'ခန့်မှန်းချက်' if lang=='MM' else 'Predictions'}:</b>\n")
    for km in [10000, 30000, 50000, 100000]:
        extra = max(0, km - mileage)
        pred = max(0, soh - (deg_per_10k * extra / 10000))
        bar = "█" * int(pred/5) + "░" * (20 - int(pred/5))
        msg += f"• {km//1000}k km: <code>{bar}</code> {pred:.1f}%\n"
    await msg_obj.reply_html(msg, reply_markup=InlineKeyboardMarkup([back_row(lang)]))

# ================================================================
# PHASE 2: EXPENSE TRACKER
# ================================================================
EXPENSE_CATS = {
    "charging":  ("⚡ Charging",  "⚡ Charging"),
    "service":   ("🔧 Service",   "🔧 Service"),
    "insurance": ("📋 Insurance", "📋 Insurance"),
    "tire":      ("🔄 Tire",      "🔄 Tire"),
    "other":     ("📦 Other",     "📦 Other"),
}

async def expense_menu(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    msg_obj = u.callback_query.message if u.callback_query else u.message
    if u.callback_query: await u.callback_query.answer()
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ Charging", callback_data="exp_cat_charging"),
         InlineKeyboardButton("🔧 Service", callback_data="exp_cat_service")],
        [InlineKeyboardButton("📋 Insurance", callback_data="exp_cat_insurance"),
         InlineKeyboardButton("🔄 Tire", callback_data="exp_cat_tire")],
        [InlineKeyboardButton("📦 Other", callback_data="exp_cat_other")],
        [InlineKeyboardButton("📊 Monthly Report", callback_data="monthly_report")],
        back_row(lang)
    ])
    await msg_obj.reply_text(
        "💰 ကုန်ကျစရိတ် category ရွေးပါ:" if lang == "MM" else "💰 Select expense category:",
        reply_markup=kb)

async def expense_set_cat(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    if u.callback_query: await u.callback_query.answer()
    cat = u.callback_query.data.replace("exp_cat_", "")
    c.user_data["exp_cat"] = cat
    mm_label, en_label = EXPENSE_CATS.get(cat, ("Other", "Other"))
    label = mm_label if lang == "MM" else en_label
    await u.callback_query.message.reply_text(
        f"{label} — ငွေပမာဏ (MMK) ရိုက်ပါ။ (ဥပမာ: 5000)"
        if lang == "MM" else
        f"{label} — Enter amount in MMK (e.g. 5000)")
    return S_EXP_AMT

async def expense_get_amt(u: Update, c: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(u.effective_user.id)
    try:
        amt = int(u.message.text.strip().replace(",", "").replace(" ", ""))
        if amt <= 0: raise ValueError
        c.user_data["exp_amt"] = amt
        await u.message.reply_text(
            "📝 မှတ်ချက် ရိုက်ပါ (မထည့်ချင်ရင် - ရိုက်ပါ)"
            if lang == "MM" else
            "📝 Add a note or type - to skip")
        return S_EXP_NOTE
    except (ValueError, TypeError):
        await u.message.reply_text(
            "❌ ငွေပမာဏ ဂဏန်းဖြင့်သာ ရိုက်ပါ။ (ဥပမာ: 5000)"
            if lang == "MM" else
            "❌ Enter amount in numbers only. (e.g. 5000)")
        return S_EXP_AMT

async def expense_save(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    note = u.message.text.strip()
    if note == "-": note = ""
    cat = c.user_data.get("exp_cat", "other")
    amt = c.user_data.get("exp_amt", 0)
    mm_label, en_label = EXPENSE_CATS.get(cat, ("Other", "Other"))
    label = mm_label if lang == "MM" else en_label
    db.add_expense(uid, cat, amt, note)
    await u.message.reply_html(
        f"✅ <b>မှတ်သားပြီး!</b>\n{label}: <b>MMK {amt:,}</b>" + (f"\n📝 {note}" if note else ""),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Monthly Report", callback_data="monthly_report")],
            back_row(lang)]))
    return ConversationHandler.END

# ================================================================
# PHASE 2: MONTHLY REPORT
# ================================================================
async def monthly_report(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    msg_obj = u.callback_query.message if u.callback_query else u.message
    if u.callback_query: await u.callback_query.answer()
    now = datetime.now()
    expenses = db.get_monthly_expenses(uid, now.year, now.month)
    if not expenses:
        return await msg_obj.reply_html(
            f"📊 {now.strftime('%B %Y')} — ကုန်ကျစရိတ် မရှိသေးပါ။"
            if lang == "MM" else
            f"📊 {now.strftime('%B %Y')} — No expenses yet.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💰 Add Expense", callback_data="expense_start")],
                back_row(lang)]))
    totals = {}
    for e in expenses:
        cat, amt = e[2], int(e[3])
        totals[cat] = totals.get(cat, 0) + amt
    grand_total = sum(totals.values())
    msg = f"📊 <b>{now.strftime('%B %Y')} Report</b>\n\n"
    icons = {"charging":"⚡","service":"🔧","insurance":"📋","tire":"🔄","other":"📦"}
    for cat, amt in sorted(totals.items(), key=lambda x: x[1], reverse=True):
        icon = icons.get(cat, "📦")
        pct = int(amt / grand_total * 100)
        bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
        msg += f"{icon} {cat.title()}: <b>MMK {amt:,}</b> ({pct}%)\n<code>{bar}</code>\n\n"
    msg += f"💰 <b>Total: MMK {grand_total:,}</b>"
    await msg_obj.reply_html(msg, reply_markup=InlineKeyboardMarkup([back_row(lang)]))


# ================================================================
# COMMUNITY STATION REPORTING
# ================================================================
async def report_station_menu(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    if u.callback_query: await u.callback_query.answer()
    # Parse: report_station_{lat}_{lon}_{name}
    raw = u.callback_query.data.replace("report_station_", "")
    chunks = raw.split("_")
    s_id = f"{chunks[0]}_{chunks[1]}"
    # Clean station name for callback data (no underscores to avoid split issues)
    s_name_raw = "_".join(chunks[2:]) if len(chunks) > 2 else "Station"
    s_name_cb = s_name_raw.replace("_", " ")
    s_name = s_name_raw.replace("_", " ")

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 အလုပ်လုပ်နေတယ်", callback_data=f"do_report_{s_id}_online_{s_name_cb}"),
         InlineKeyboardButton("🟠 လူကျနေတယ်", callback_data=f"do_report_{s_id}_busy_{s_name_cb}")],
        [InlineKeyboardButton("🔴 စက်ပျက်နေတယ်", callback_data=f"do_report_{s_id}_broken_{s_name_cb}"),
         InlineKeyboardButton("🟡 မီးပျက်နေတယ်", callback_data=f"do_report_{s_id}_no_power_{s_name_cb}")],
        back_row(lang)
    ])
    await u.callback_query.message.reply_text(
        f"📢 Station အခြေအနေ Report လုပ်ပါ:\n<b>{s_name}</b>"
        if lang == "MM" else
        f"📢 Report station status:\n<b>{s_name}</b>",
        reply_markup=kb, parse_mode="HTML")

async def do_station_report(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    if u.callback_query: await u.callback_query.answer()
    raw = u.callback_query.data.replace("do_report_", "")
    chunks = raw.split("_")
    # s_id is {lat}_{lon}
    s_id = f"{chunks[0]}_{chunks[1]}"
    status = chunks[2] if len(chunks) > 2 else "online"
    s_name = " ".join(chunks[3:]) if len(chunks) > 3 else "Station"

    db.add_station_report(s_id, s_name, status, uid)
    db.add_points(uid, 10) # Award points
    
    status_labels = {"online": "🟢 အလုပ်လုပ်နေတယ်", "broken": "🔴 စက်ပျက်နေတယ်",
                     "no_power": "🟡 မီးပျက်နေတယ်", "busy": "🟠 လူကျနေတယ်"}
    label = status_labels.get(status, status)
    await u.callback_query.message.reply_html(
        f"✅ <b>Report တင်ပြီးပါပြီ!</b>\n{s_name}: {label}\n\n"
        f"🏆 သင် <b>10 Points</b> ရရှိပါပြီ! \n<i>မင်းရဲ့ report ကြောင့် EV community အားလုံး အကျိုးရှိပါတယ်! 🙏</i>"
        if lang == "MM" else
        f"✅ <b>Report submitted!</b>\n{s_name}: {label}\n\n"
        f"🏆 You earned <b>10 Points</b>! \n<i>Thank you for helping the EV community! 🙏</i>",
        reply_markup=InlineKeyboardMarkup([back_row(lang)]))

async def visual_charts_menu(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    if u.callback_query: await u.callback_query.answer()
    
    # Use reply_html if edit_text fails (common with message consistency)
    try:
        ok, data = check_premium(uid, lang)
        if not ok:
            return await u.callback_query.message.reply_html(data[0], reply_markup=data[1])
            
        msg = ("📊 <b>Visual Charts</b>\n\nသင့်ရဲ့ EV အသုံးပြုမှု မှတ်တမ်းတွေကို ဇယားများဖြင့် ကြည့်ရှုနိုင်ပါတယ်" 
               if lang == "MM" else 
               "📊 <b>Visual Charts</b>\n\nView your EV usage history with charts")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔋 Battery History Chart", callback_data="chart_battery")],
            [InlineKeyboardButton("💰 Expense Pie Chart", callback_data="chart_expense")],
            back_row(lang)
        ])
        await u.callback_query.message.edit_text(msg, reply_markup=kb, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Visual menu error: {e}")
        # Fallback to a new message if editing fails
        await u.callback_query.message.reply_html("📊 Visual Charts Menu", reply_markup=kb)

async def send_battery_chart(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    if u.callback_query: await u.callback_query.answer()
    logs = db.get_logs(uid)
    if not logs:
        return await u.callback_query.message.reply_text("No history found", reply_markup=back_button(lang))
    
    try:
        path = visuals.generate_battery_history_chart(uid, logs)
        if path and os.path.exists(path):
            with open(path, 'rb') as photo:
                await u.callback_query.message.reply_photo(photo=photo, caption="📊 Battery Level History")
            os.remove(path)
        else:
            await u.callback_query.message.reply_text("Error generating chart image", reply_markup=back_button(lang))
    except Exception as e:
        logger.error(f"Chart error: {e}")
        await u.callback_query.message.reply_text("Error processing chart", reply_markup=back_button(lang))

async def send_expense_chart(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    if u.callback_query: await u.callback_query.answer()
    now = datetime.now()
    expenses = db.get_monthly_expenses(uid, now.year, now.month)
    if not expenses:
        return await u.callback_query.message.reply_text("No expenses this month", reply_markup=back_button(lang))
    
    try:
        path = visuals.generate_expense_chart(uid, expenses)
        if path and os.path.exists(path):
            with open(path, 'rb') as photo:
                await u.callback_query.message.reply_photo(photo=photo, caption="📊 Monthly Expense Summary")
            os.remove(path)
        else:
            await u.callback_query.message.reply_text("Error generating chart image", reply_markup=back_button(lang))
    except Exception as e:
        logger.error(f"Chart error: {e}")
        await u.callback_query.message.reply_text("Error processing chart", reply_markup=back_button(lang))

# ================================================================
# TRIP LOG EXPORT (Premium) — CSV
# ================================================================
async def export_history(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    if u.callback_query: await u.callback_query.answer()
    msg_obj = u.callback_query.message if u.callback_query else u.message

    ok, data = check_premium(uid, lang)
    if not ok:
        return await msg_obj.reply_html(data[0], reply_markup=data[1])

    logs = db.get_logs(uid)
    expenses = db.get_monthly_expenses(uid, datetime.now().year, datetime.now().month)

    if not logs and not expenses:
        return await msg_obj.reply_text(
            "📊 Export လုပ်ရန် data မရှိသေးပါ။" if lang == "MM" else "📊 No data to export yet.",
            reply_markup=back_button(lang))

    # Build CSV
    import io
    output = io.StringIO()
    output.write("Type,Date,Category,Value,Note\n")

    for log in logs:
        date = str(log[5])[:10]
        output.write(f"Battery Update,{date},Battery %,{log[4]},\n")

    for exp in expenses:
        date = str(exp[5])[:10]
        output.write(f"Expense,{date},{exp[2]},{exp[3]},{exp[4]}\n")

    csv_bytes = output.getvalue().encode("utf-8-sig")
    import io as bio
    buf = bio.BytesIO(csv_bytes)
    buf.name = f"ev_history_{datetime.now().strftime('%Y%m')}.csv"

    await msg_obj.reply_document(
        document=buf,
        filename=buf.name,
        caption="📊 EV History Export\n✅ Excel မှာ ဖွင့်နိုင်ပါတယ်။" if lang == "MM"
                else "📊 EV History Export\n✅ Open with Excel or Google Sheets.")

# ================================================================
# EV KNOWLEDGE BASE
# ================================================================
KB_ARTICLES = {
    "charge_basics": {
        "MM": ("🔋 အားသွင်းနည်း အခြေခံ",
               "• AC Charging (Level 2): ညဘက် အိမ်မှာ အားသွင်းဖို့ အသင့်တော်ဆုံး\n"
               "• DC Fast Charging: ခရီးရှည်မောင်းရင် အသုံးပြုပါ\n"
               "• Battery 20-80% ကြားထားပါ — lifetime တိုးပါတယ်\n"
               "• Full charge (100%) ကို နေ့တိုင်း မလုပ်ပါနဲ့"),
        "EN": ("🔋 Charging Basics",
               "• AC Charging (Level 2): Best for home overnight charging\n"
               "• DC Fast Charging: Use for long trips only\n"
               "• Keep battery 20-80% — extends battery life\n"
               "• Avoid daily 100% charges")
    },
    "battery_life": {
        "MM": ("🔋 Battery သက်တမ်း တိုးနည်း",
               "• 20-80% ကြားသာ အားသွင်းပါ\n"
               "• DC Fast Charge မကြာမကြာ မသုံးပါနဲ့\n"
               "• အပူချိန်မြင့်သော နေရာမှာ ကားရပ်ထားတာ ရှောင်ပါ\n"
               "• တစ်လတစ်ကြိမ် 100% အထိ calibrate လုပ်ပါ\n"
               "• ချမ်းသောနေရာမှာ ကားသိမ်းရင် battery ကျနိုင်တယ်"),
        "EN": ("🔋 Extending Battery Life",
               "• Charge between 20-80%\n"
               "• Minimize DC Fast Charging\n"
               "• Avoid parking in extreme heat\n"
               "• Calibrate monthly with full charge\n"
               "• Cold storage can reduce capacity")
    },
    "myanmar_ev": {
        "MM": ("🇲🇲 မြန်မာ EV အချက်အလက်",
               "• Toyota bZ3X, bZ4X — Myanmar မှာ အရောင်းရဆုံး\n"
               "• Yangon မှာ Charging Station တွေ ပိုရှိတယ်\n"
               "• KPay/Wave နဲ့ charge ငွေပေးနိုင်တဲ့ Station တချို့ ရှိတယ်\n"
               "• ညဘက် off-peak မှာ အားသွင်းရင် လျှပ်စစ်ဓာတ်အားခ သက်သာတယ်\n"
               "• Myanmar ရဲ့ EV incentives — import tax လျှော့ချပေးတယ်"),
        "EN": ("🇲🇲 Myanmar EV Info",
               "• Toyota bZ3X, bZ4X — Most popular in Myanmar\n"
               "• More charging stations available in Yangon\n"
               "• Some stations accept KPay/Wave payment\n"
               "• Charge during off-peak for lower electricity cost\n"
               "• Myanmar EV incentives include reduced import tax")
    },
    "range_tips": {
        "MM": ("🛣️ Range တိုးနည်း Tips",
               "• Speed 80-100 km/h မှာ range အကောင်းဆုံး\n"
               "• AC မသုံးရင် range 10-15% တိုးတယ်\n"
               "• Eco mode သုံးပါ\n"
               "• တောင်ကြီးဆင်းရင် regenerative braking သုံးပါ\n"
               "• တာယာဖိအား မှန်ကန်အောင် ထိန်းပါ"),
        "EN": ("🛣️ Range Optimization Tips",
               "• Optimal speed: 80-100 km/h\n"
               "• Reducing AC use adds 10-15% range\n"
               "• Use Eco mode whenever possible\n"
               "• Use regenerative braking on downhill\n"
               "• Maintain correct tire pressure")
    },
}

async def knowledge_base(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    if u.callback_query: await u.callback_query.answer()
    msg_obj = u.callback_query.message if u.callback_query else u.message

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔋 အားသွင်းနည်း အခြေခံ" if lang=="MM" else "🔋 Charging Basics",
                               callback_data="kb_charge_basics")],
        [InlineKeyboardButton("🔋 Battery သက်တမ်း တိုးနည်း" if lang=="MM" else "🔋 Battery Life Tips",
                               callback_data="kb_battery_life")],
        [InlineKeyboardButton("🇲🇲 မြန်မာ EV အချက်အလက်" if lang=="MM" else "🇲🇲 Myanmar EV Info",
                               callback_data="kb_myanmar_ev")],
        [InlineKeyboardButton("🛣️ Range တိုးနည်း Tips" if lang=="MM" else "🛣️ Range Tips",
                               callback_data="kb_range_tips")],
        back_row(lang)
    ])
    await msg_obj.reply_html(
        "💡 <b>EV Knowledge Base</b>\n\nဘာကို သိချင်တာလဲ?"
        if lang == "MM" else
        "💡 <b>EV Knowledge Base</b>\n\nWhat would you like to learn?",
        reply_markup=kb)

async def knowledge_base_article(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    if u.callback_query: await u.callback_query.answer()
    key = u.callback_query.data.replace("kb_", "")
    article = KB_ARTICLES.get(key)
    if not article:
        return
    title, body = article.get(lang, article.get("MM"))
    await u.callback_query.message.reply_html(
        f"<b>{title}</b>\n\n{body}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Knowledge Base", callback_data="knowledge_base")],
            back_row(lang)
        ]))


async def send_weekly_summary(context: ContextTypes.DEFAULT_TYPE):
    for uid in db.get_all_user_ids():
        try:
            lang = db.get_language(uid)
            car = db.get_active_car(uid)
            if not car:
                continue
            logs = db.get_weekly_stats(uid)
            if not logs:
                continue
            now = datetime.now()
            expenses = db.get_monthly_expenses(uid, now.year, now.month)
            total_exp = sum(int(e[3]) for e in expenses)
            pcts = [int(l[4]) for l in logs]
            avg_pct = sum(pcts) / len(pcts)
            min_pct = min(pcts)
            max_pct = max(pcts)
            msg = (f"📊 <b>Weekly Summary</b>\n\n"
                   f"🚗 {car[2]} ({car[3]})\n"
                   f"🔋 Battery avg: <b>{avg_pct:.0f}%</b>\n"
                   f"📉 Min: {min_pct}% | 📈 Max: {max_pct}%\n"
                   f"💰 Month expenses: MMK {total_exp:,}\n\n"
                   f"{'ကောင်းသောပတ်တစ်ပတ် ဖြစ်ပါစေ! ⚡' if lang=='MM' else 'Have a great week! ⚡'}")
            await context.bot.send_message(chat_id=uid, text=msg, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Weekly summary failed {uid}: {e}")

async def send_off_peak_reminder(context: ContextTypes.DEFAULT_TYPE):
    for uid in db.get_all_user_ids():
        try:
            lang = db.get_language(uid)
            await context.bot.send_message(
                chat_id=uid,
                text="🌙 Off-Peak အားသွင်းချိန်! Battery 80% ထိသာ သွင်းပါ။" if lang=="MM"
                else "🌙 Off-peak time! Charge to 80% only.")
        except Exception as e:
            logger.error(f"Reminder failed {uid}: {e}")

async def cancel(u: Update, c: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(u.effective_user.id)
    await u.message.reply_text("ဖျက်သိမ်းပြီး။" if lang=="MM" else "Cancelled.",
                                reply_markup=get_main_menu(lang))
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
    # Weekly summary every Monday 8AM
    app.job_queue.run_daily(send_weekly_summary, time=dtime(hour=8, minute=0))

    # Shared fallbacks — cancel command + button_handler for all callbacks
    shared_fallbacks = [
        CommandHandler("cancel", cancel),
        CommandHandler("start", start),
        CallbackQueryHandler(button_handler),
    ]

    reg_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(reg_start, pattern="^reg_start$"), CommandHandler("register", reg_start)],
        states={S_CAR_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_car_name)],
                S_MODEL:    [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_model)],
                S_CAP:      [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_cap)],
                S_RANGE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_range)]},
        fallbacks=shared_fallbacks,
        allow_reentry=True)

    upd_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(update_start, pattern="^upd_start$"), CommandHandler("update", update_start)],
        states={S_PCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_done)]},
        fallbacks=shared_fallbacks,
        allow_reentry=True)

    ct_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(chargetime_start, pattern="^chargetime_start$"), CommandHandler("chargetime", chargetime_start)],
        states={S_CT_START: [MessageHandler(filters.TEXT & ~filters.COMMAND, chargetime_get_start)],
                S_CT_END:   [MessageHandler(filters.TEXT & ~filters.COMMAND, chargetime_calculate)]},
        fallbacks=shared_fallbacks,
        allow_reentry=True)

    route_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(route_start, pattern="^route_start$"), CommandHandler("route", route_start)],
        states={S_RT_FROM: [MessageHandler(filters.TEXT & ~filters.COMMAND, route_get_from)],
                S_RT_TO:   [MessageHandler(filters.TEXT & ~filters.COMMAND, route_get_to)],
                S_RT_PCT:  [MessageHandler(filters.TEXT & ~filters.COMMAND, route_calculate)]},
        fallbacks=shared_fallbacks,
        allow_reentry=True)

    cost_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cost_start, pattern="^cost_start$"), CommandHandler("cost", cost_start)],
        states={S_COST_START: [MessageHandler(filters.TEXT & ~filters.COMMAND, cost_get_start)],
                S_COST_END:   [MessageHandler(filters.TEXT & ~filters.COMMAND, cost_calculate)]},
        fallbacks=shared_fallbacks,
        allow_reentry=True)

    payment_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(buy_plan, pattern="^buy_plan_")],
        states={S_PAYMENT: [MessageHandler(filters.PHOTO, payment_screenshot_received)]},
        fallbacks=shared_fallbacks,
        allow_reentry=True)

    ai_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(ai_chat_start, pattern="^ai_chat_start$"), CommandHandler("ai", ai_chat_start)],
        states={S_AI_CHAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ai_chat_respond)]},
        fallbacks=shared_fallbacks,
        allow_reentry=True)

    bhealth_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(bhealth_start, pattern="^bhealth_start$")],
        states={S_BH_SOH:     [MessageHandler(filters.TEXT & ~filters.COMMAND, bhealth_get_soh)],
                S_BH_MILEAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, bhealth_get_mileage)]},
        fallbacks=shared_fallbacks,
        allow_reentry=True)

    expense_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(expense_set_cat, pattern="^exp_cat_")],
        states={S_EXP_AMT:  [MessageHandler(filters.TEXT & ~filters.COMMAND, expense_get_amt)],
                S_EXP_NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, expense_save)]},
        fallbacks=shared_fallbacks,
        allow_reentry=True)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(reg_conv)
    app.add_handler(upd_conv)
    app.add_handler(ct_conv)
    app.add_handler(route_conv)
    app.add_handler(cost_conv)
    app.add_handler(payment_conv)
    app.add_handler(ai_conv)
    app.add_handler(bhealth_conv)
    app.add_handler(expense_conv)
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.LOCATION, location_handler))

    print("✅ EV Helper Bot running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
