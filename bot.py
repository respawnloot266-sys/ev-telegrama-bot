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
        "📍 Location ပို့ပေးပါ (သို့) Lat,Lon ရိုက်ထည့်ပါ",
        reply_markup=reply_markup
    )

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.location:
        lat = update.message.location.latitude
        lon = update.message.location.longitude
    else:
        try:
            lat, lon = map(float, update.message.text.split(','))
        except:
            await update.message.reply_text("❌ Format မှားနေပါတယ်")
            return
    
    await update.message.reply_text("🔍 ရှာဖွေနေပါတယ်...")
    stations = charge_api.find_nearest_stations(lat, lon, limit=5)
    
    if not stations:
        await update.message.reply_text("❌ Station မတွေ့ပါ — config.py မှာ radius ချဲ့ကြည့်ပါ")
        return
    
    msg = "🔌 **အနီးဆုံး Charge Stations:**\n\n"
    for i, s in enumerate(stations, 1):
        name = s.get('AddressInfo', {}).get('Title', 'Unknown')
        addr = s.get('AddressInfo', {}).get('AddressLine1', 'N/A')
        s_lat = s.get('AddressInfo', {}).get('Latitude', lat)
        s_lon = s.get('AddressInfo', {}).get('Longitude', lon)
        dist = charge_api.calculate_distance(lat, lon, s_lat, s_lon)
        connections = s.get('Connections', [])
        conn_types = ', '.join(set(c.get('ConnectionType', {}).get('Title', 'N/A') 
                                    for c in connections)) or 'N/A'
        power = connections[0].get('PowerKW', '?') if connections else '?'
        msg += f"**{i}. {name}**\n"
        msg += f"   📍 {addr}\n"
        msg += f"   📏 {dist:.1f} km\n"
        msg += f"   ⚡ {power} kW ({conn_types})\n\n"
    
    await update.message.reply_text(msg)

async def cheapest_station(update: Update, context: ContextTypes.DEFAULT_TYPE):
    location_btn = KeyboardButton("📍 Location ပို့ပါ", request_location=True)
    reply_markup = ReplyKeyboardMarkup([[location_btn]], one_time_keyboard=True)
    await update.message.reply_text(
        "📍 Location ပို့ပေးပါ — ဈေးနှုန်း နှိုင်းယှဉ်ပေးပါမယ်",
        reply_markup=reply_markup
    )

async def handle_cheapest_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.location:
        lat = update.message.location.latitude
        lon = update.message.location.longitude
    else:
        try:
            lat, lon = map(float, update.message.text.split(','))
        except:
            return
    
    await update.message.reply_text("💰 ဈေးနှုန်း ရှာဖွေနေပါတယ်...")
    stations = charge_api.find_cheapest_station(lat, lon)
    
    if not stations:
        await update.message.reply_text("❌ Station မတွေ့ပါ")
        return
    
    msg = "💰 **ဈေးနှုန်း နှိုင်းယှဉ်ချက်:**\n\n"
    station_data = []
    for s in stations:
        name = s.get('AddressInfo', {}).get('Title', 'Unknown')
        connections = s.get('Connections', [])
        prices = [c.get('UsageCost', 0) for c in connections if c.get('UsageCost')]
        avg_price = sum(prices) / len(prices) if prices else 0
        power = connections[0].get('PowerKW', '?') if connections else '?'
        s_lat = s.get('AddressInfo', {}).get('Latitude', lat)
        s_lon = s.get('AddressInfo', {}).get('Longitude', lon)
        dist = charge_api.calculate_distance(lat, lon, s_lat, s_lon)
        if avg_price > 0:
            station_data.append((name, avg_price, power, dist, s_lat, s_lon))
    
    station_data.sort(key=lambda x: x[1])
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    
    for i, (name, price, power, dist, s_lat, s_lon) in enumerate(station_data[:5], 1):
        medal = medals[i-1] if i <= 5 else "•"
        msg += f"{medal} **{name}**\n"
        msg += f"   💵 {price:.0f} Ks/kWh\n"
        msg += f"   ⚡ {power} kW\n"
        msg += f"   📏 {dist:.1f} km\n"
        msg += f"   🗺️ [Map](https://maps.google.com/?q={s_lat},{s_lon})\n\n"
    
    if not station_data:
        msg = "❌ ဈေးနှုန်း data မရှိသေးပါ"
    
    await update.message.reply_text(msg, parse_mode='Markdown', disable_web_page_preview=True)

async def calc_time_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = database.get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("❌ /register ကို အရင်လုပ်ပါ")
        return ConversationHandler.END
    context.user_data['battery_capacity'] = user[3]
    await update.message.reply_text(
        f"🔋 **Charge Time တွက်ရန်**\n\n"
        f"ကား: {user[2]}\nBattery: {user[3]} kWh\n\n"
        f"⚡ Charger Power (kW) ရိုက်ထည့်ပါ\nဥပမာ: 50 (DC) / 7 (AC)"
    )
    return TIME_POWER

async def calc_time_get_power(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        power = float(update.message.text)
        context.user_data['charger_power'] = power
        await update.message.reply_text("🔋 **လက်ရှိ Battery % ရိုက်ထည့်ပါ**\n\nဥပမာ: 20")
        return TIME_PERCENT
    except ValueError:
        await update.message.reply_text("❌ နံပါတ် ရိုက်ထည့်ပါ")
        return TIME_POWER

async def calc_time_get_percent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        current = float(update.message.text)
        target = 80
        time_hours = charge_api.calculate_charge_time(
            context.user_data['battery_capacity'],
            current, target,
            context.user_data['charger_power']
        )
        hours = int(time_hours)
        minutes = int((time_hours - hours) * 60)
        kwh_needed = context.user_data['battery_capacity'] * (target - current) / 100
        total_cost = kwh_needed * COST_PER_KWH
        await update.message.reply_text(
            f"⏱️ **Charge Time ခန့်မှန်း**\n\n"
            f"🔋 {current}% → {target}%\n"
            f"⚡ Charger: {context.user_data['charger_power']} kW\n"
            f"🔌 လိုအပ်တဲ့ ပမာဏ: {kwh_needed:.1f} kWh\n"
            f"⏰ ကြာချိန်: {hours} နာရီ {minutes} မိနစ်\n"
            f"💰 ကုန်ကျစရိတ်: {total_cost:,.0f} Ks"
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ နံပါတ် ရိုက်ထည့်ပါ")
        return TIME_PERCENT

async def start_charge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = database.get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("❌ /register ကို အရင်လုပ်ပါ")
        return
    current_battery = user[4]
    session_id = database.start_session(update.effective_user.id, current_battery)
    context.user_data['session_id'] = session_id
    context.user_data['session_start'] = current_battery
    await update.message.reply_text(
        f"🔌 **Charge စတင်ပါပြီ**\n\n"
        f"📊 Session: #{session_id}\n"
        f"🔋 Start Battery: {current_battery}%\n"
        f"⏰ {datetime.now().strftime('%H:%M')}\n\n"
        f"Charge ပြည့်ရင် /finishcharge ရိုက်ပါ"
    )

async def finish_charge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session_id = context.user_data.get('session_id')
    if not session_id:
        await update.message.reply_text("❌ /startcharge ကို အရင်နှိပ်ပါ")
        return
    user = database.get_user(update.effective_user.id)
    context.user_data['user_capacity'] = user[3]
    await update.message.reply_text(
        f"🔋 **Charge ပြီးပါပြီ — Battery % ရိုက်ထည့်ပါ**\n\n"
        f"ဥပမာ: 100"
    )
    return WAITING_END_PERCENT

async def save_finished_charge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        end_percent = float(update.message.text)
        if end_percent < 0 or end_percent > 100:
            raise ValueError
        session_id = context.user_data['session_id']
        capacity = context.user_data['user_capacity']
        start_percent = context.user_data['session_start']
        user_id = update.effective_user.id
        
        kwh_used = capacity * (end_percent - start_percent) / 100
        cost = kwh_used * COST_PER_KWH
        
        database.finish_session(session_id, end_percent, kwh_used, cost)
        database.update_battery(user_id, end_percent)
        database.log_charge_session(
            user_id, start_percent, end_percent, kwh_used, cost, "User reported"
        )
        
        congrats = "\n\n🎉 **၁၀၀% ပြည့်ပါပြီ!** Charge log ထဲ save ပြီးပါပြီ ✓" if end_percent >= 100 else ""
        
        await update.message.reply_text(
            f"✅ **Charge Log သိမ်းပြီးပါပြီ**\n\n"
            f"🔋 {start_percent}% → {end_percent}%\n"
            f"⚡ {kwh_used:.1f} kWh\n"
            f"💰 {cost:,.0f} Ks{congrats}\n\n"
            f"📜 /history နှိပ်ရင် စရင်းကြည့်လို့ရပါတယ်"
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ 0-100 ကြား နံပါတ် ရိုက်ထည့်ပါ")
        return WAITING_END_PERCENT

async def view_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    history = database.get_charge_history(update.effective_user.id, limit=10)
    if not history:
        await update.message.reply_text("📜 Charge history မရှိသေးပါ")
        return
    msg = "📜 **Charge History (နောက်ဆုံး ၁၀ ခု)**\n\n"
    total_kwh = 0
    total_cost = 0
    for h in history:
        msg += f"🔋 {h[2]}% → {h[3]}% | {h[4]:.1f} kWh | {h[5]:,.0f} Ks\n"
        msg += f"   📅 {h[7][:16]}\n\n"
        total_kwh += h[4]
        total_cost += h[5]
    msg += f"━━━━━━━━━━━━━━━━\n📊 စုစုပေါင်း: {total_kwh:.1f} kWh / {total_cost:,.0f} Ks"
    await update.message.reply_text(msg)

async def low_battery_alert(context: ContextTypes.DEFAULT_TYPE):
    users = database.get_low_battery_users()
    for user_id, username, percent, threshold in users:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    f"⚠️ **Battery Alert** ⚠️\n\n"
                    f"🔋 {username} — Battery {percent}%\n"
                    f"🎯 Threshold: {threshold}%\n\n"
                    f"Charge ဖြည့်ဖို့ အချိန်ကောင်းပါပြီ! /findstation 🚗"
                )
            )
        except Exception as e:
            logger.error(f"Alert failed: {e}")

def main():
    database.init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    
    reg_handler = ConversationHandler(
        entry_points=[CommandHandler('register', register_start)],
        states={
            CAR_MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_car_model)],
            BATTERY_CAPACITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_battery)],
            FULL_RANGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_range)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    batt_handler = ConversationHandler(
        entry_points=[CommandHandler('battery', battery_start)],
        states={UPDATE_BATTERY: [MessageHandler(filters.TEXT & ~filters.COMMAND, battery_save)]},
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    time_handler = ConversationHandler(
        entry_points=[CommandHandler('calctime', calc_time_start)],
        states={
            TIME_POWER: [MessageHandler(filters.TEXT & ~filters.COMMAND, calc_time_get_power)],
            TIME_PERCENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, calc_time_get_percent)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    finish_handler = ConversationHandler(
        entry_points=[CommandHandler('finishcharge', finish_charge)],
        states={WAITING_END_PERCENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_finished_charge)]},
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    app.add_handler(CommandHandler('start', start))
    app.add_handler(reg_handler)
    app.add_handler(batt_handler)
    app.add_handler(time_handler)
    app.add_handler(finish_handler)
    app.add_handler(CommandHandler('findstation', find_station))
    app.add_handler(CommandHandler('cheapest', cheapest_station))
    app.add_handler(CommandHandler('startcharge', start_charge))
    app.add_handler(CommandHandler('history', view_history))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_handler(MessageHandler(filters.LOCATION, handle_cheapest_location))
    
    try:
        app.job_queue.run_daily(low_battery_alert, time=time(hour=8, minute=0, tzinfo='UTC'))
    except:
        pass
    
    print("✅ EV Bot စတင်နေပါပြီ...")
    app.run_polling()

if __name__ == "__main__":
    main()