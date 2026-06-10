import os
import logging
from datetime import datetime
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
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ELECTRICITY_RATE_MMK = 200  # MMK per kWh (Myanmar average)

# --- States ---
CAR_NAME, MODEL, CAP, RANGE = range(4)
PCT = range(1)
CHARGE_START_PCT, CHARGE_END_PCT = range(2)
PAYMENT_SCREENSHOT = range(1)
ROUTE_FROM, ROUTE_TO, ROUTE_PCT = range(3)
COST_START, COST_END = range(2)
REMINDER_TYPE, REMINDER_VALUE = range(2)
EXPENSE_CAT, EXPENSE_AMT, EXPENSE_NOTE = range(3)
AI_CHAT = range(1)

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

# Myanmar major cities with coordinates
MYANMAR_CITIES = {
    "yangon": (16.8409, 96.1735),
    "mandalay": (21.9588, 96.0891),
    "naypyidaw": (19.7475, 96.1297),
    "bago": (17.3364, 96.4817),
    "taungoo": (18.9500, 96.4333),
    "pyinmana": (19.7333, 96.2000),
    "meiktila": (20.8833, 95.8667),
    "thazi": (20.8500, 96.0833),
}

def get_charge_rate(model):
    return CAR_CHARGE_RATES.get(model.lower().strip(), 50)

def get_lang(uid):
    return db.get_language(uid)

# ================================================================
# HELPERS
# ================================================================
def check_premium(uid, lang):
    if db.is_premium(uid):
        return True, None
    if lang == "MM":
        msg = "⭐ <b>Premium Feature</b>\n\nဒီ feature ကို Premium plan နဲ့သာ သုံးနိုင်ပါတယ်။\nMMK 5,000/လ မှ စတင်နိုင်ပါတယ်။"
    else:
        msg = "⭐ <b>Premium Feature</b>\n\nThis feature requires a Premium plan.\nStarting from MMK 5,000/month."
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ Upgrade to Premium", callback_data="upgrade")],
        back_row(lang)
    ])
    return False, (msg, kb)

def back_row(lang="MM"):
    label = "🔙 Menu သို့ပြန်" if lang == "MM" else "🔙 Back to Menu"
    return [InlineKeyboardButton(label, callback_data="back_menu")]

def back_button(lang="MM"):
    return InlineKeyboardMarkup([back_row(lang)])

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
            [InlineKeyboardButton("🔔 Reminders", callback_data="reminders"),
             InlineKeyboardButton("🤖 AI Chat ⭐", callback_data="ai_chat_start")],
            [InlineKeyboardButton("🚗 ကားများ", callback_data="cars"),
             InlineKeyboardButton("📍 Favorites ⭐", callback_data="favs")],
            [InlineKeyboardButton("⭐ Premium", callback_data="upgrade"),
             InlineKeyboardButton("🌐 EN/MM", callback_data="lang")],
            [InlineKeyboardButton("💡 Tips", callback_data="tips")],
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
            [InlineKeyboardButton("🔔 Reminders", callback_data="reminders"),
             InlineKeyboardButton("🤖 AI Chat ⭐", callback_data="ai_chat_start")],
            [InlineKeyboardButton("🚗 My Cars", callback_data="cars"),
             InlineKeyboardButton("📍 Favorites ⭐", callback_data="favs")],
            [InlineKeyboardButton("⭐ Premium", callback_data="upgrade"),
             InlineKeyboardButton("🌐 EN/MM", callback_data="lang")],
            [InlineKeyboardButton("💡 Tips", callback_data="tips")],
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
    name = update.effective_user.first_name or ""
    plan = db.get_plan(uid)
    plan_badge = "⭐ Premium" if plan == "premium" else "🆓 Free"

    if car:
        pct = car[7]
        icon = utils.get_battery_icon(pct)
        msg = (f"👋 ပြန်လာတာ ကြိုဆိုပါတယ်, <b>{name}</b>! {plan_badge}\n\n"
               f"🚗 {car[2]} ({car[3]})\n{icon} Battery: <b>{pct}%</b>\n\nဘာကူညီရမလဲ?"
               if lang == "MM" else
               f"👋 Welcome back, <b>{name}</b>! {plan_badge}\n\n"
               f"🚗 {car[2]} ({car[3]})\n{icon} Battery: <b>{pct}%</b>\n\nHow can I help?")
    else:
        msg = (f"⚡ <b>EV Helper Smart Assistant</b>\n\nမင်္ဂလာပါ, <b>{name}</b>!\nကား မှတ်ပုံတင်ပြီး စတင်ပါ။"
               if lang == "MM" else
               f"⚡ <b>EV Helper Smart Assistant</b>\n\nHello, <b>{name}</b>!\nRegister your car to get started.")

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
    elif query.data == "stat": await status(update, context)
    elif query.data == "hist": await history(update, context)
    elif query.data == "find": await find_station(update, context)
    elif query.data == "tips": await tips(update, context)
    elif query.data == "cars": await show_cars(update, context)
    elif query.data == "favs": await show_favorites(update, context)
    elif query.data == "lang": await lang_menu(update, context)
    elif query.data == "upgrade": await upgrade_menu(update, context)
    elif query.data == "reminders": await show_reminders(update, context)
    elif query.data == "lang_mm":
        db.set_language(uid, "MM")
        await query.message.reply_html(utils.t("MM", "lang_set"), reply_markup=get_main_menu("MM"))
    elif query.data == "lang_en":
        db.set_language(uid, "EN")
        await query.message.reply_html(utils.t("EN", "lang_set"), reply_markup=get_main_menu("EN"))
    elif query.data.startswith("buy_plan_"): await buy_plan(update, context)
    elif query.data.startswith("switch_car_"):
        db.switch_car(uid, int(query.data.replace("switch_car_", "")))
        await query.answer("✅ ကား ပြောင်းပြီး!", show_alert=True)
        await show_cars(update, context)
    elif query.data.startswith("del_car_"):
        db.delete_car(uid, int(query.data.replace("del_car_", "")))
        await query.answer("🗑️ ဖျက်ပြီး!", show_alert=True)
        await show_cars(update, context)
    elif query.data.startswith("del_fav_"):
        db.delete_favorite(uid, int(query.data.replace("del_fav_", "")))
        await query.answer(utils.t(lang, "deleted"), show_alert=True)
        await show_favorites(update, context)
    elif query.data.startswith("save_fav_"):
        parts = query.data.split("|")
        db.add_favorite(uid, parts[1], parts[2], float(parts[3]), float(parts[4]))
        await query.answer(utils.t(lang, "saved"), show_alert=True)
    elif query.data.startswith("del_reminder_"):
        db.delete_reminder(uid, int(query.data.replace("del_reminder_", "")))
        await query.answer("🗑️ ဖျက်ပြီး!", show_alert=True)
        await show_reminders(update, context)
    elif query.data.startswith("admin_"):
        await admin_callback_handler(update, context)

# ================================================================
# 1. ROUTE PLANNER (Premium)
# ================================================================
async def route_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    msg_obj = u.callback_query.message if u.callback_query else u.message
    if u.callback_query: await u.callback_query.answer()

    ok, data = check_premium(uid, lang)
    if not ok:
        return await msg_obj.reply_html(data[0], reply_markup=data[1])

    car = db.get_active_car(uid)
    if not car:
        return await msg_obj.reply_text(utils.t(lang, "no_car"), reply_markup=get_main_menu(lang))

    cities_list = ", ".join([c.title() for c in MYANMAR_CITIES.keys()])
    await msg_obj.reply_text(
        f"🗺️ ထွက်ခွာရာ မြို့ ရိုက်ပါ။\n\nရနိုင်သော မြို့တွေ:\n{cities_list}"
        if lang == "MM" else
        f"🗺️ Enter your origin city.\n\nAvailable cities:\n{cities_list}"
    )
    return ROUTE_FROM

async def route_get_from(u: Update, c: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(u.effective_user.id)
    city = u.message.text.strip().lower()
    if city not in MYANMAR_CITIES:
        await u.message.reply_text(
            f"❌ မြို့ မတွေ့ပါ။ ဒီမြို့တွေထဲမှ ရွေးပါ:\n{', '.join(MYANMAR_CITIES.keys())}"
            if lang == "MM" else
            f"❌ City not found. Choose from:\n{', '.join(MYANMAR_CITIES.keys())}"
        )
        return ROUTE_FROM
    c.user_data["route_from"] = city
    await u.message.reply_text(
        "🏁 ဆုံးမှတ် မြို့ ရိုက်ပါ။" if lang == "MM" else "🏁 Enter destination city."
    )
    return ROUTE_TO

async def route_get_to(u: Update, c: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(u.effective_user.id)
    city = u.message.text.strip().lower()
    if city not in MYANMAR_CITIES:
        await u.message.reply_text(
            f"❌ မြို့ မတွေ့ပါ။ ဒီမြို့တွေထဲမှ ရွေးပါ:\n{', '.join(MYANMAR_CITIES.keys())}"
        )
        return ROUTE_TO
    if city == c.user_data.get("route_from"):
        await u.message.reply_text("❌ ထွက်ခွာမြို့နဲ့ ဆုံးမှတ်မြို့ မတူညီရပါ။")
        return ROUTE_TO
    c.user_data["route_to"] = city
    await u.message.reply_text(
        "🔋 လက်ရှိ Battery % ရိုက်ပါ။" if lang == "MM" else "🔋 Enter current battery %"
    )
    return ROUTE_PCT

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

        from_city = c.user_data["route_from"]
        to_city = c.user_data["route_to"]
        from_coords = MYANMAR_CITIES[from_city]
        to_coords = MYANMAR_CITIES[to_city]

        total_distance = utils.calculate_distance(
            from_coords[0], from_coords[1], to_coords[0], to_coords[1]
        )
        current_range = full_range * (current_pct / 100)
        safe_range = full_range * 0.80  # 80% safe buffer

        if current_range >= total_distance * 1.1:
            # တစ်ကြိမ်တည်း ရောက်နိုင်တယ်
            if lang == "MM":
                msg = (f"🗺️ <b>Route Plan</b>\n\n"
                       f"📍 {from_city.title()} → {to_city.title()}\n"
                       f"📏 ခရီးဝေး: <b>{total_distance:.0f} km</b>\n"
                       f"🔋 လက်ရှိ Range: <b>{current_range:.0f} km</b>\n\n"
                       f"✅ <b>တစ်ကြိမ်တည်း မောင်းနိုင်သည်!</b>\n"
                       f"ဆုံးမှတ်ရောက်ရင် Battery: ~{max(0, current_pct - int(total_distance/full_range*100))}% ကျန်မည်")
            else:
                msg = (f"🗺️ <b>Route Plan</b>\n\n"
                       f"📍 {from_city.title()} → {to_city.title()}\n"
                       f"📏 Distance: <b>{total_distance:.0f} km</b>\n"
                       f"🔋 Current Range: <b>{current_range:.0f} km</b>\n\n"
                       f"✅ <b>Can reach without charging!</b>\n"
                       f"Remaining at destination: ~{max(0, current_pct - int(total_distance/full_range*100))}%")
        else:
            # Station မှာ ရပ်ရမယ်
            stops_needed = max(1, int(total_distance / safe_range))
            stop_distance = total_distance / (stops_needed + 1)
            charge_needed_pct = min(90, int(stop_distance / full_range * 100) + 20)
            charge_time = utils.calculate_charge_time(20, charge_needed_pct, battery_cap, charge_rate)

            if lang == "MM":
                msg = (f"🗺️ <b>Route Plan</b>\n\n"
                       f"📍 {from_city.title()} → {to_city.title()}\n"
                       f"📏 ခရီးဝေး: <b>{total_distance:.0f} km</b>\n"
                       f"🔋 လက်ရှိ Range: <b>{current_range:.0f} km</b>\n\n"
                       f"⚡ <b>Charging Stop {stops_needed} ကြိမ် လိုသည်</b>\n\n")
                for i in range(stops_needed):
                    dist = stop_distance * (i + 1)
                    msg += f"🔌 Stop {i+1}: {from_city.title()} မှ <b>{dist:.0f} km</b> ကွာ\n"
                msg += (f"\n📋 <b>အကြံပြုချက်:</b>\n"
                        f"• {current_pct}% နဲ့ ထွက်ပါ\n"
                        f"• Stop တိုင်းမှာ {charge_needed_pct}% အထိ အားသွင်းပါ\n"
                        f"• တစ် Stop ကြာချိန်: ~{utils.format_charge_time(charge_time)}\n"
                        f"• ခရီးဆုံး Battery: ~20% ကျန်မည်")
            else:
                msg = (f"🗺️ <b>Route Plan</b>\n\n"
                       f"📍 {from_city.title()} → {to_city.title()}\n"
                       f"📏 Distance: <b>{total_distance:.0f} km</b>\n"
                       f"🔋 Current Range: <b>{current_range:.0f} km</b>\n\n"
                       f"⚡ <b>Need {stops_needed} charging stop(s)</b>\n\n")
                for i in range(stops_needed):
                    dist = stop_distance * (i + 1)
                    msg += f"🔌 Stop {i+1}: <b>{dist:.0f} km</b> from {from_city.title()}\n"
                msg += (f"\n📋 <b>Recommendations:</b>\n"
                        f"• Start with {current_pct}%\n"
                        f"• Charge to {charge_needed_pct}% at each stop\n"
                        f"• ~{utils.format_charge_time(charge_time)} per stop\n"
                        f"• Arrive with ~20% remaining")

        await u.message.reply_html(msg, reply_markup=InlineKeyboardMarkup([back_row(lang)]))
        return ConversationHandler.END
    except ValueError:
        await u.message.reply_text("❌ 0-100 ဂဏန်းဖြင့်သာ ရိုက်ပါ။")
        return ROUTE_PCT

# ================================================================
# 2. CHARGING COST CALCULATOR
# ================================================================
async def cost_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    msg_obj = u.callback_query.message if u.callback_query else u.message
    if u.callback_query: await u.callback_query.answer()
    lang = get_lang(u.effective_user.id)
    car = db.get_active_car(u.effective_user.id)
    if not car:
        return await msg_obj.reply_text(utils.t(lang, "no_car"), reply_markup=get_main_menu(lang))
    await msg_obj.reply_text(
        "🔋 လက်ရှိ Battery % ရိုက်ပါ။" if lang == "MM" else "🔋 Enter current battery %"
    )
    return COST_START

async def cost_get_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(u.effective_user.id)
    try:
        pct = int(u.message.text.strip())
        if not (0 <= pct <= 100): raise ValueError
        c.user_data["cost_start"] = pct
        await u.message.reply_text(
            "🎯 Target % ရိုက်ပါ။" if lang == "MM" else "🎯 Enter target %"
        )
        return COST_END
    except ValueError:
        await u.message.reply_text("❌ 0-100 ဂဏန်းဖြင့်သာ ရိုက်ပါ။")
        return COST_START

async def cost_calculate(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    try:
        end_pct = int(u.message.text.strip())
        if not (0 <= end_pct <= 100): raise ValueError
        start_pct = c.user_data["cost_start"]
        if end_pct <= start_pct:
            await u.message.reply_text(f"❌ Target {start_pct}% ထက် ကြီးရမည်။")
            return COST_END

        car = db.get_active_car(uid)
        cap = float(car[4])
        kwh_needed = cap * (end_pct - start_pct) / 100
        cost_mmk = int(kwh_needed * ELECTRICITY_RATE_MMK)
        charge_time = utils.calculate_charge_time(start_pct, end_pct, cap, get_charge_rate(car[3]))

        if lang == "MM":
            msg = (f"💰 <b>Charging Cost</b>\n\n"
                   f"🚗 {car[2]} ({car[3]})\n"
                   f"🔋 {start_pct}% → {end_pct}%\n"
                   f"⚡ kWh လိုအပ်: <b>{kwh_needed:.1f} kWh</b>\n"
                   f"💵 ခန့်မှန်း ကုန်ကျစရိတ်: <b>MMK {cost_mmk:,}</b>\n"
                   f"⏱️ ကြာချိန်: <b>{utils.format_charge_time(charge_time)}</b>\n\n"
                   f"<i>* MMK {ELECTRICITY_RATE_MMK}/kWh အပေါ်တွက်ချက်သည်</i>")
        else:
            msg = (f"💰 <b>Charging Cost</b>\n\n"
                   f"🚗 {car[2]} ({car[3]})\n"
                   f"🔋 {start_pct}% → {end_pct}%\n"
                   f"⚡ Energy needed: <b>{kwh_needed:.1f} kWh</b>\n"
                   f"💵 Est. Cost: <b>MMK {cost_mmk:,}</b>\n"
                   f"⏱️ Time: <b>{utils.format_charge_time(charge_time)}</b>\n\n"
                   f"<i>* Based on MMK {ELECTRICITY_RATE_MMK}/kWh</i>")

        await u.message.reply_html(msg, reply_markup=InlineKeyboardMarkup([back_row(lang)]))
        return ConversationHandler.END
    except ValueError:
        await u.message.reply_text("❌ 0-100 ဂဏန်းဖြင့်သာ ရိုက်ပါ။")
        return COST_END

# ================================================================
# 3. SMART REMINDERS
# ================================================================
async def reminders_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    msg_obj = u.callback_query.message if u.callback_query else u.message
    if u.callback_query: await u.callback_query.answer()
    lang = get_lang(u.effective_user.id)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔔 Low Battery Warning", callback_data="add_reminder_battery"),
         InlineKeyboardButton("🔧 Tire Rotation", callback_data="add_reminder_tire")],
        [InlineKeyboardButton("📋 Insurance Reminder", callback_data="add_reminder_insurance"),
         InlineKeyboardButton("🔧 Service Reminder", callback_data="add_reminder_service")],
        [InlineKeyboardButton("📋 ရှိပြီးသား Reminders", callback_data="reminders")],
        back_row(lang)
    ])
    await msg_obj.reply_text(
        "🔔 Reminder အမျိုးအစား ရွေးပါ:" if lang == "MM" else "🔔 Select reminder type:",
        reply_markup=kb
    )

async def show_reminders(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    msg_obj = u.callback_query.message if u.callback_query else u.message
    reminders = db.get_reminders(uid)

    if not reminders:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Reminder ထည့်", callback_data="add_reminder_menu")],
            back_row(lang)
        ])
        return await msg_obj.reply_text(
            "🔔 Reminder မရှိသေးပါ။" if lang == "MM" else "🔔 No reminders yet.",
            reply_markup=kb
        )

    msg = "🔔 <b>သင့် Reminders:</b>\n\n" if lang == "MM" else "🔔 <b>Your Reminders:</b>\n\n"
    keyboard = []
    icons = {"battery": "🔋", "tire": "🔧", "insurance": "📋", "service": "🔧"}
    for r in reminders:
        icon = icons.get(r[2], "🔔")
        msg += f"{icon} <b>{r[2].title()}</b>: {r[3]}\n"
        if r[4]: msg += f"   📝 {r[4]}\n"
        keyboard.append([InlineKeyboardButton(f"🗑️ {r[2].title()}", callback_data=f"del_reminder_{r[0]}")])

    keyboard.append([InlineKeyboardButton("➕ ထပ်ထည့်", callback_data="add_reminder_menu")])
    keyboard.append(back_row(lang))
    await msg_obj.reply_html(msg, reply_markup=InlineKeyboardMarkup(keyboard))

# ================================================================
# 4. EV AI CHAT (Premium)
# ================================================================
async def ai_chat_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    msg_obj = u.callback_query.message if u.callback_query else u.message
    if u.callback_query: await u.callback_query.answer()

    ok, data = check_premium(uid, lang)
    if not ok:
        return await msg_obj.reply_html(data[0], reply_markup=data[1])

    if not ANTHROPIC_API_KEY:
        return await msg_obj.reply_text(
            "❌ AI Chat မရနိုင်သေးပါ။ Admin ထံ ဆက်သွယ်ပါ။" if lang == "MM"
            else "❌ AI Chat unavailable. Contact admin."
        )

    c.user_data["ai_history"] = []
    if lang == "MM":
        msg = ("🤖 <b>EV AI Assistant</b>\n\n"
               "EV နဲ့ပတ်သက်တာ မေးနိုင်ပါတယ်:\n"
               "• Range, Battery, Charging\n"
               "• ကား မော်ဒယ် နှိုင်းယှဉ်\n"
               "• ပြဿနာ ဖြေရှင်းနည်း\n\n"
               "မေးချင်တာ ရိုက်ပါ။ /done နှိပ်ရင် ပြီးမည်။")
    else:
        msg = ("🤖 <b>EV AI Assistant</b>\n\n"
               "Ask me anything about EVs:\n"
               "• Range, Battery, Charging\n"
               "• Car model comparisons\n"
               "• Troubleshooting\n\n"
               "Type your question. /done to exit.")

    await msg_obj.reply_html(msg)
    return AI_CHAT

async def ai_chat_respond(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    question = u.message.text.strip()

    if question.lower() in ("/done", "/start", "done"):
        await u.message.reply_text(
            "✅ AI Chat ပြီးပါပြီ။" if lang == "MM" else "✅ AI Chat ended.",
            reply_markup=get_main_menu(lang)
        )
        return ConversationHandler.END

    loading = await u.message.reply_text(
        "🤔 တွေးနေပါသည်..." if lang == "MM" else "🤔 Thinking..."
    )

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        car = db.get_active_car(uid)
        car_context = f"User's car: {car[3]} with {car[4]}kWh battery, {car[5]}km range." if car else ""

        history = c.user_data.get("ai_history", [])
        history.append({"role": "user", "content": question})

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            system=f"""You are an EV (Electric Vehicle) expert assistant for Myanmar users.
Answer in {'Burmese (Myanmar)' if lang == 'MM' else 'English'} language.
Be concise and helpful. Focus on practical EV advice.
{car_context}
Keep answers under 200 words.""",
            messages=history[-6:]  # Last 6 messages for context
        )

        answer = response.content[0].text
        history.append({"role": "assistant", "content": answer})
        c.user_data["ai_history"] = history[-10:]

        await loading.delete()
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ ပြီးပါပြီ" if lang == "MM" else "❌ End Chat", callback_data="back_menu")]
        ])
        await u.message.reply_text(f"🤖 {answer}", reply_markup=kb)

    except Exception as e:
        logger.error(f"AI Chat error: {e}")
        await loading.delete()
        await u.message.reply_text(
            "❌ Error ဖြစ်သည်။ နောက်မှ ထပ်စမ်းပါ။" if lang == "MM"
            else "❌ Error occurred. Please try again.",
            reply_markup=get_main_menu(lang)
        )
        return ConversationHandler.END

    return AI_CHAT

# ================================================================
# EXISTING FEATURES (Status, History, Find Station, etc.)
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
    if lang == "MM":
        msg = (f"📊 <b>လက်ရှိအခြေအနေ</b>\n\n🚗 {car[2]} ({car[3]})\n"
               f"{icon} Battery: <b>{pct}%</b>{warning}\n"
               f"🛣️ ခရီး: <b>{current_range:.1f} km</b>\n⚡ {get_charge_rate(car[3])} kW{weather_text}")
    else:
        msg = (f"📊 <b>Current Status</b>\n\n🚗 {car[2]} ({car[3]})\n"
               f"{icon} Battery: <b>{pct}%</b>{warning}\n"
               f"🛣️ Range: <b>{current_range:.1f} km</b>\n⚡ {get_charge_rate(car[3])} kW{weather_text}")
    await msg_obj.reply_html(msg, reply_markup=InlineKeyboardMarkup([back_row(lang)]))

async def history(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    days = None if db.is_premium(uid) else 7
    logs = db.get_logs(uid, days=days)
    msg_obj = u.callback_query.message if u.callback_query else u.message
    if not logs:
        return await msg_obj.reply_text(utils.t(lang, "no_history"), reply_markup=back_button(lang))
    note = "" if db.is_premium(uid) else ("\n<i>⭐ Premium: မှတ်တမ်း အကန့်အသတ်မဲ့</i>" if lang == "MM" else "\n<i>⭐ Premium: Unlimited history</i>")
    title = "📜 <b>Battery မှတ်တမ်း</b>" if lang == "MM" else "📜 <b>Battery History</b>"
    await msg_obj.reply_html(title + note + "\n\n" + utils.format_logs_chart(logs), reply_markup=back_button(lang))

async def find_station(u: Update, c: ContextTypes.DEFAULT_TYPE):
    msg_obj = u.callback_query.message if u.callback_query else u.message
    lang = get_lang(u.effective_user.id)
    label = "📍 တည်နေရာပေးပို့" if lang == "MM" else "📍 Share Location"
    kb = [[KeyboardButton(label, request_location=True)]]
    await msg_obj.reply_text(
        "Station ရှာရန် တည်နေရာပေးပါ။" if lang == "MM" else "Share location to find stations.",
        reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True)
    )

async def location_handler(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    lat, lon = u.message.location.latitude, u.message.location.longitude
    c.user_data["last_lat"] = lat
    c.user_data["last_lon"] = lon
    loading = await u.message.reply_text("🔍 ရှာဖွေနေပါသည်..." if lang == "MM" else "🔍 Searching...", reply_markup=ReplyKeyboardRemove())
    try:
        stations = charge_api.get_nearby_charging_stations(lat, lon, distance=10, max_results=5)
    except Exception as e:
        logger.error(f"Station error: {e}")
        await loading.delete()
        return await u.message.reply_text("❌ Station ရှာမရပါ။" if lang == "MM" else "❌ Search failed.", reply_markup=get_main_menu(lang))
    await loading.delete()
    if not stations:
        return await u.message.reply_text("😔 Station မတွေ့ပါ။" if lang == "MM" else "😔 No stations found.", reply_markup=get_main_menu(lang))
    title = "🔌 <b>အနီးဆုံး Station များ:</b>\n\n" if lang == "MM" else "🔌 <b>Nearby Stations:</b>\n\n"
    msg = title
    keyboard = []
    is_prem = db.is_premium(uid)
    for i, station in enumerate(stations):
        info = station.get("addressInfo", {})
        name, address = info.get("title", "N/A"), info.get("addressLine1", "")
        dist = info.get("distance", 0)
        s_lat, s_lon = info.get("latitude"), info.get("longitude")
        maps_link = f"https://www.google.com/maps/dir/?api=1&destination={s_lat},{s_lon}"
        view_link = f"https://www.google.com/maps/search/?api=1&query={s_lat},{s_lon}"
        msg += f"{i+1}. <b>{name}</b> ({dist:.1f} km)\n"
        if address: msg += f"   📍 {address}\n"
        conns = station.get("connections", [])
        if conns:
            details = [f"{cn.get('connectionType',{}).get('title','?')} ({cn.get('powerKW','?')}kW)" for cn in conns]
            msg += f"   ⚡ {', '.join(details)}\n"
        msg += f"   <a href=\"{maps_link}\">🗺️ Navigate</a> | <a href=\"{view_link}\">📌 View</a>\n\n"
        if is_prem:
            keyboard.append([InlineKeyboardButton(f"⭐ {name[:25]}", callback_data=f"save_fav_|{name}|{address or 'N/A'}|{s_lat}|{s_lon}")])
    if not is_prem:
        keyboard.append([InlineKeyboardButton("⭐ Favorites သိမ်းဖို့ Premium လိုသည်", callback_data="upgrade")])
    keyboard.append(back_row(lang))
    await u.message.reply_html(msg, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(keyboard))

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

async def show_favorites(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    msg_obj = u.callback_query.message
    ok, data = check_premium(uid, lang)
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

async def tips(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    msg_obj = u.callback_query.message if u.callback_query else u.message
    msg = ("💡 <b>EV Battery Tips:</b>\n\n• 🟢 Battery 20%-80% ကြားထားပါ\n• 🌙 ညဘက် Off-peak မှာ အားသွင်းပါ\n• ❄️ အအေးမှာ range ကျနိုင်တယ်\n• ⚡ DC Fast Charge မကြာမကြာ မသုံးပါနဲ့"
           if lang == "MM" else
           "💡 <b>EV Battery Tips:</b>\n\n• 🟢 Keep battery 20%-80%\n• 🌙 Charge during off-peak hours\n• ❄️ Cold weather reduces range\n• ⚡ Avoid frequent DC Fast Charging")
    await msg_obj.reply_html(msg, reply_markup=back_button(lang))

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
    await msg_obj.reply_text("🚗 ကားအမည် ရိုက်ပါ။" if lang == "MM" else "🚗 Enter car name.")
    return CAR_NAME

async def reg_car_name(u: Update, c: ContextTypes.DEFAULT_TYPE):
    c.user_data["car_name"] = u.message.text.strip()
    lang = get_lang(u.effective_user.id)
    await u.message.reply_text("🚗 Model ရိုက်ပါ။ (ဥပမာ: Toyota bZ3X)" if lang == "MM" else "🚗 Enter model. (e.g. Tesla Model 3)")
    return MODEL

async def reg_model(u: Update, c: ContextTypes.DEFAULT_TYPE):
    model = u.message.text.strip()
    c.user_data["model"] = model
    rate = get_charge_rate(model)
    c.user_data["rate"] = rate
    lang = get_lang(u.effective_user.id)
    await u.message.reply_html(f"⚡ {rate} kW (Auto-detected)\n\n" + ("🔋 Battery Capacity (kWh):" if lang == "MM" else "🔋 Battery Capacity (kWh):"))
    return CAP

async def reg_cap(u: Update, c: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(u.effective_user.id)
    try:
        c.user_data["cap"] = float(u.message.text.strip())
        await u.message.reply_text("🛣️ Full Range (km):" if lang == "MM" else "🛣️ Full Range (km):")
        return RANGE
    except ValueError:
        await u.message.reply_text("❌ ဂဏန်းသာ ရိုက်ပါ။")
        return CAP

async def reg_range(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    try:
        full_range = float(u.message.text.strip())
        db.add_car(uid, c.user_data["car_name"], c.user_data["model"], c.user_data["cap"], full_range, c.user_data.get("rate", 50))
        await u.message.reply_html(
            f"✅ <b>မှတ်ပုံတင်ပြီး!</b>\n🚗 {c.user_data['car_name']} ({c.user_data['model']})\n🔋 {c.user_data['cap']}kWh | 🛣️ {full_range}km",
            reply_markup=get_main_menu(lang))
    except ValueError:
        await u.message.reply_text("❌ ဂဏန်းသာ ရိုက်ပါ။")
        return RANGE
    return ConversationHandler.END

# ================================================================
# BATTERY UPDATE
# ================================================================
async def update_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    msg_obj = u.callback_query.message if u.callback_query else u.message
    if u.callback_query: await u.callback_query.answer("🔋 Battery % ထည့်ပါ...")
    lang = get_lang(u.effective_user.id)
    await msg_obj.reply_text("🔋 လက်ရှိ Battery % (0-100)" if lang == "MM" else "🔋 Enter battery % (0-100)")
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
        await u.message.reply_html(
            (f"✅ Battery <b>{pct}%</b> မှတ်သားပြီး။" if lang == "MM" else f"✅ Battery updated to <b>{pct}%</b>.") + warning,
            reply_markup=get_main_menu(lang))
    except ValueError:
        await u.message.reply_text("❌ 0-100 ဂဏန်းဖြင့်သာ ရိုက်ပါ။")
        return PCT
    return ConversationHandler.END

# ================================================================
# CHARGE TIME
# ================================================================
async def chargetime_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    msg_obj = u.callback_query.message if u.callback_query else u.message
    if u.callback_query: await u.callback_query.answer()
    lang = get_lang(u.effective_user.id)
    await msg_obj.reply_text("🔋 လက်ရှိ Battery % :" if lang == "MM" else "🔋 Current battery %:")
    return CHARGE_START_PCT

async def chargetime_get_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(u.effective_user.id)
    try:
        pct = int(u.message.text.strip())
        if not (0 <= pct <= 100): raise ValueError
        c.user_data["charge_start"] = pct
        await u.message.reply_text("🎯 Target % :")
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
            await u.message.reply_text(f"❌ Target {start_pct}% ထက် ကြီးရမည်။")
            return CHARGE_END_PCT
        car = db.get_active_car(uid)
        if not car:
            await u.message.reply_text(utils.t(lang, "no_car"))
            return ConversationHandler.END
        cap, rate = float(car[4]), get_charge_rate(car[3])
        minutes = utils.calculate_charge_time(start_pct, end_pct, cap, rate)
        kwh = cap * (end_pct - start_pct) / 100
        await u.message.reply_html(
            f"⏱️ <b>{'အားသွင်းကြာချိန်' if lang == 'MM' else 'Charge Time'}</b>\n\n"
            f"🚗 {car[2]} | ⚡ {rate}kW\n"
            f"🔋 {start_pct}% → {end_pct}% ({kwh:.1f}kWh)\n"
            f"⏱️ <b>{utils.format_charge_time(minutes)}</b>",
            reply_markup=InlineKeyboardMarkup([back_row(lang)]))
        return ConversationHandler.END
    except ValueError:
        await u.message.reply_text("❌ 0-100 ဂဏန်းဖြင့်သာ ရိုက်ပါ။")
        return CHARGE_END_PCT

# ================================================================
# PREMIUM / PAYMENT
# ================================================================
async def upgrade_menu(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    msg_obj = u.callback_query.message
    if db.is_premium(uid):
        expire = db.get_expire_date(uid)
        expire_str = datetime.fromisoformat(expire).strftime("%Y-%m-%d") if expire else "N/A"
        return await msg_obj.reply_html(
            f"⭐ <b>Premium Plan!</b>\n📅 {'သက်တမ်း' if lang == 'MM' else 'Expires'}: <b>{expire_str}</b>",
            reply_markup=back_button(lang))
    if lang == "MM":
        msg = ("⭐ <b>Premium Plan</b>\n\n🆓 Free:\n• ကား ၁ စီး\n• History ၇ ရက်\n\n"
               "⭐ Premium:\n• ကား အကန့်အသတ်မဲ့ ✅\n• Route Planner ✅\n• AI Chat ✅\n"
               "• Favorites ✅\n• Weather Range ✅\n• History အကန့်အသတ်မဲ့ ✅\n\nPlan ရွေးပါ:")
    else:
        msg = ("⭐ <b>Premium Plan</b>\n\n🆓 Free:\n• 1 car\n• 7-day history\n\n"
               "⭐ Premium:\n• Unlimited cars ✅\n• Route Planner ✅\n• AI Chat ✅\n"
               "• Favorites ✅\n• Weather Range ✅\n• Full history ✅\n\nSelect plan:")
    kb = [[InlineKeyboardButton(f"⭐ {p['label']}", callback_data=f"buy_plan_{k}")] for k, p in PLANS.items()]
    kb.append(back_row(lang))
    await msg_obj.reply_html(msg, reply_markup=InlineKeyboardMarkup(kb))

async def buy_plan(u: Update, c: ContextTypes.DEFAULT_TYPE):
    query = u.callback_query
    await query.answer()
    uid = u.effective_user.id
    lang = get_lang(uid)
    plan_key = query.data.replace("buy_plan_", "")
    plan = PLANS.get(plan_key)
    if not plan: return
    c.user_data["selected_plan"] = plan_key
    await query.message.reply_html(
        f"💰 <b>{'ငွေလွှဲနည်း' if lang == 'MM' else 'Payment Instructions'}</b>\n\n"
        f"Plan: {plan['label']}\n\n"
        f"📱 <b>KPay:</b> <code>{KPAY_NUMBER}</code>\n"
        f"📱 <b>Wave:</b> <code>{WAVE_NUMBER}</code>\n\n"
        f"Amount: <b>MMK {plan['price']:,}</b>\n\n"
        f"{'ငွေလွှဲပြီး screenshot ပို့ပေးပါ။' if lang == 'MM' else 'Send screenshot after payment.'}",
        reply_markup=back_button(lang))
    return PAYMENT_SCREENSHOT

async def payment_screenshot_received(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    lang = get_lang(uid)
    if not u.message.photo:
        await u.message.reply_text("❌ Screenshot ဓါတ်ပုံ ပို့ပေးပါ။" if lang == "MM" else "❌ Send a photo screenshot.")
        return PAYMENT_SCREENSHOT
    plan_key = c.user_data.get("selected_plan", "1")
    plan = PLANS.get(plan_key, PLANS["1"])
    screenshot_file_id = u.message.photo[-1].file_id
    payment_id = db.add_pending_payment(uid, plan["price"], plan["months"], screenshot_file_id)
    await send_payment_to_admin(c, payment_id, uid, plan["months"], plan["price"], screenshot_file_id)
    await u.message.reply_html(
        f"✅ <b>{'Screenshot လက်ခံပြီး!' if lang == 'MM' else 'Screenshot received!'}</b>\n\n"
        f"Payment ID: <code>#{payment_id}</code>\n"
        f"{'မိနစ် ၃၀ အတွင်း Premium activate ဖြစ်မည်။' if lang == 'MM' else 'Premium will activate within 30 minutes.'}",
        reply_markup=get_main_menu(lang))
    return ConversationHandler.END

# ================================================================
# LANGUAGE / CANCEL
# ================================================================
async def lang_menu(u: Update, c: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(u.effective_user.id)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🇲🇲 မြန်မာ", callback_data="lang_mm"),
         InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
        back_row(lang)
    ])
    await u.callback_query.message.reply_text("🌐 ဘာသာစကား ရွေးပါ:", reply_markup=kb)

async def cancel(u: Update, c: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(u.effective_user.id)
    await u.message.reply_text("ဖျက်သိမ်းပြီး။" if lang == "MM" else "Cancelled.", reply_markup=get_main_menu(lang))
    return ConversationHandler.END

# ================================================================
# OFF-PEAK REMINDER
# ================================================================
async def send_off_peak_reminder(context: ContextTypes.DEFAULT_TYPE):
    for uid in db.get_all_user_ids():
        try:
            lang = db.get_language(uid)
            await context.bot.send_message(
                chat_id=uid,
                text="🌙 Off-Peak အားသွင်းချိန်! Battery 80% ထိသာ သွင်းပါ။" if lang == "MM"
                else "🌙 Off-peak time! Charge to 80% only."
            )
        except Exception as e:
            logger.error(f"Reminder failed {uid}: {e}")

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
        states={CAR_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_car_name)],
                MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_model)],
                CAP: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_cap)],
                RANGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_range)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    upd_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(update_start, pattern="^upd_start$"), CommandHandler("update", update_start)],
        states={PCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_done)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    chargetime_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(chargetime_start, pattern="^chargetime_start$"), CommandHandler("chargetime", chargetime_start)],
        states={CHARGE_START_PCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, chargetime_get_start)],
                CHARGE_END_PCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, chargetime_calculate)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    route_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(route_start, pattern="^route_start$"), CommandHandler("route", route_start)],
        states={ROUTE_FROM: [MessageHandler(filters.TEXT & ~filters.COMMAND, route_get_from)],
                ROUTE_TO: [MessageHandler(filters.TEXT & ~filters.COMMAND, route_get_to)],
                ROUTE_PCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, route_calculate)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    cost_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cost_start, pattern="^cost_start$"), CommandHandler("cost", cost_start)],
        states={COST_START: [MessageHandler(filters.TEXT & ~filters.COMMAND, cost_get_start)],
                COST_END: [MessageHandler(filters.TEXT & ~filters.COMMAND, cost_calculate)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    payment_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(buy_plan, pattern="^buy_plan_")],
        states={PAYMENT_SCREENSHOT: [MessageHandler(filters.PHOTO, payment_screenshot_received)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    ai_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(ai_chat_start, pattern="^ai_chat_start$"), CommandHandler("ai", ai_chat_start)],
        states={AI_CHAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ai_chat_respond)]},
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("done", cancel)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(CommandHandler("reminders", reminders_start))
    app.add_handler(reg_conv)
    app.add_handler(upd_conv)
    app.add_handler(chargetime_conv)
    app.add_handler(route_conv)
    app.add_handler(cost_conv)
    app.add_handler(payment_conv)
    app.add_handler(ai_conv)
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.LOCATION, location_handler))

    print("✅ EV Helper Bot running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
