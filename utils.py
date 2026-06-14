import math
import os
import requests

DEFAULT_MAX_CHARGE_RATE_KW = 50
WEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

# --- Texts (MM/EN) ---
TEXTS = {
    "MM": {
        "no_car": "🚗 ကား မှတ်ပုံတင်ထားခြင်း မရှိသေးပါ။\nကျေးဇူးပြု၍ ကားအရင် Register လုပ်ပေးပါဦးခင်ဗျာ။",
        "battery_low": "⚠️ Battery နည်းနေပါပြီ! \nခရီးစဉ် အဆင်ပြေဖို့ အနီးဆုံး Station မှာ အားသွင်းဖို့ အကြံပြုပါရစေ။",
        "battery_high": "💡 Battery 80% ပြည့်သွားပါပြီ။ \nBattery သက်တမ်း ပိုရှည်စေဖို့ ဒီအဆင့်မှာ အားသွင်းရပ်တာ အကောင်းဆုံးပါပဲ။",
        "no_history": "📊 မှတ်တမ်း မရှိသေးပါဘူး။ \nစတင် အသုံးပြုကြည့်ဖို့ တိုက်တွန်းပါရစေ။",
        "no_favorites": "⭐ Favorite Station မရှိသေးပါ။ \nကိုယ်နှစ်သက်တဲ့ Station တွေကို အလွယ်တကူ သိမ်းထားနိုင်ပါတယ်ခင်ဗျာ။",
        "saved": "✅ အောင်မြင်စွာ သိမ်းဆည်းပြီးပါပြီ။",
        "deleted": "🗑️ အောင်မြင်စွာ ဖျက်သိမ်းပြီးပါပြီ။",
        "select_car": "🚗 ကျေးဇူးပြု၍ အသုံးပြုမည့်ကားကို ရွေးချယ်ပေးပါ:",
        "lang_set": "🌐 ဘာသာစကားကို မြန်မာဘာသာသို့ ပြောင်းလဲပြီးပါပြီ။",
    },
    "EN": {
        "no_car": "No car registered. Please register first.",
        "battery_low": "⚠️ Battery is low! Please charge now.",
        "battery_high": "💡 It's best to stop charging above 80%.",
        "no_history": "No history found.",
        "no_favorites": "No favorite stations yet.",
        "saved": "✅ Saved successfully.",
        "deleted": "🗑️ Deleted successfully.",
        "select_car": "🚗 Select a car:",
        "lang_set": "🌐 Language set to English.",
    }
}

def t(lang, key):
    return TEXTS.get(lang, TEXTS["MM"]).get(key, key)

# --- Distance ---
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon/2)**2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

# --- Charge Time ---
def calculate_charge_time(start_pct, end_pct, cap_kwh, rate_kw=DEFAULT_MAX_CHARGE_RATE_KW):
    if start_pct >= end_pct:
        return 0
    kwh = cap_kwh * (end_pct - start_pct) / 100
    return round(kwh / rate_kw * 60)

def format_charge_time(minutes):
    if minutes <= 0:
        return "0 မိနစ်" 
    h, m = divmod(minutes, 60)
    if h and m:
        return f"{h} နာရီ {m} မိနစ်"
    return f"{h} နာရီ" if h else f"{m} မိနစ်"

# --- Battery UI ---
def format_battery_bar(pct, width=20):
    filled = round(pct / 100 * width)
    return "█" * filled + "░" * (width - filled)

def get_battery_icon(pct):
    if pct <= 20: return "🔴"
    if pct <= 50: return "🟡"
    return "🟢"

def format_logs_chart(logs):
    if not logs:
        return "မှတ်တမ်း မရှိပါ။"
    msg = "<code>"
    for log in logs:
        date_str = str(log[5])[:10]
        pct_val = int(log[4])
        bar = format_battery_bar(pct_val)
        icon = get_battery_icon(pct_val)
        msg += f"{date_str} |{bar}| {icon}{pct_val}%\n"
    return msg + "</code>"

# --- Weather + Range Impact ---
def get_weather_and_range(lat, lon, full_range, current_pct):
    """မိုးလေဝသပေါ်မူတည်ပြီး actual range တွက်တယ်။"""
    if not WEATHER_API_KEY:
        return None

    try:
        url = "https://api.openweathermap.org/data/2.5/weather"
        res = requests.get(url, params={
            "lat": lat, "lon": lon,
            "appid": WEATHER_API_KEY,
            "units": "metric"
        }, timeout=10)
        res.raise_for_status()
        data = res.json()

        temp = data["main"]["temp"]
        weather_desc = data["weather"][0]["description"]
        city = data.get("name", "")

        # Temperature-based range impact
        if temp < 0:
            factor = 0.70      # အလွန်အအေး — 30% ကျ
        elif temp < 10:
            factor = 0.85      # အအေး — 15% ကျ
        elif temp > 35:
            factor = 0.90      # အပူ — 10% ကျ
        else:
            factor = 1.0       # ပုံမှန်

        base_range = full_range * (current_pct / 100)
        adjusted_range = base_range * factor
        impact_pct = round((1 - factor) * 100)

        return {
            "city": city,
            "temp": temp,
            "desc": weather_desc,
            "base_range": round(base_range, 1),
            "adjusted_range": round(adjusted_range, 1),
            "impact_pct": impact_pct,
            "factor": factor
        }
    except Exception as e:
        print(f"Weather error: {e}")
        return None

def format_weather_range(data, lang="MM"):
    if not data:
        return ""
    if lang == "MM":
        impact = f"({data['impact_pct']}% ကျ)" if data['impact_pct'] > 0 else "(ပုံမှန်)"
        return (
            f"\n\n🌦️ <b>မိုးလေဝသ အခြေအနေ</b> — {data['city']}\n"
            f"🌡️ အပူချိန်: {data['temp']}°C ({data['desc']})\n"
            f"🛣️ ခန့်မှန်း Range: <b>{data['adjusted_range']} km</b> {impact}"
        )
    else:
        impact = f"({data['impact_pct']}% reduction)" if data['impact_pct'] > 0 else "(normal)"
        return (
            f"\n\n🌦️ <b>Weather</b> — {data['city']}\n"
            f"🌡️ Temp: {data['temp']}°C ({data['desc']})\n"
            f"🛣️ Est. Range: <b>{data['adjusted_range']} km</b> {impact}"
        )
