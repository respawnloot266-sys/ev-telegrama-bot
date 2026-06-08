import math
from datetime import datetime, timedelta

# Default charge rate (config.py မလိုတော့ဘဲ bot.py ရဲ့ CAR_CHARGE_RATES နဲ့ sync ဖြစ်နေတယ်)
DEFAULT_MAX_CHARGE_RATE_KW = 50

def calculate_distance(lat1, lon1, lat2, lon2):
    """GPS coordinates နှစ်ခုကြား ကီလိုမီတာ တွက်တယ်။"""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def calculate_charge_time(start_percent, end_percent, battery_capacity_kwh, max_charge_rate_kw=DEFAULT_MAX_CHARGE_RATE_KW):
    """အားသွင်းကြာချိန် မိနစ်ဖြင့် တွက်တယ်။"""
    if start_percent >= end_percent:
        return 0
    kwh_needed = battery_capacity_kwh * (end_percent - start_percent) / 100
    time_hours = kwh_needed / max_charge_rate_kw
    return round(time_hours * 60)

def format_charge_time(minutes: int) -> str:
    """မိနစ်ကို နာရီ + မိနစ် ပုံစံ ပြောင်းတယ်။ (ဥပမာ: 1 နာရီ 30 မိနစ်)"""
    if minutes <= 0:
        return "0 မိနစ်"
    hours = minutes // 60
    mins = minutes % 60
    if hours > 0 and mins > 0:
        return f"{hours} နာရီ {mins} မိနစ်"
    elif hours > 0:
        return f"{hours} နာရီ"
    else:
        return f"{mins} မိနစ်"

def format_battery_bar(pct: int, width: int = 20) -> str:
    """Battery % ကို ASCII bar ပုံစံပြောင်းတယ်။"""
    filled = round(pct / 100 * width)
    return "█" * filled + "░" * (width - filled)

def get_battery_status_icon(pct: int) -> str:
    """Battery % အပေါ် မူတည်ပြီး icon ပြတယ်။"""
    if pct <= 20:
        return "🔴"
    elif pct <= 50:
        return "🟡"
    else:
        return "🟢"

def format_logs_as_chart(logs: list) -> str:
    """Battery log များကို ASCII chart ပုံစံပြောင်းတယ်။"""
    if not logs:
        return "မှတ်တမ်း မရှိပါ။"
    msg = "<code>"
    for log in logs:
        date_str = str(log[4])[:10]
        pct_val = int(log[3])
        bar = format_battery_bar(pct_val)
        icon = get_battery_status_icon(pct_val)
        msg += f"{date_str} |{bar}| {icon}{pct_val}%\n"
    msg += "</code>"
    return msg

def get_battery_health_tips() -> str:
    """Battery Health Tips ပြတယ်။"""
    return (
        "💡 <b>EV Battery Tips:</b>\n\n"
        "1. 🟢 Battery <b>20%-80%</b> ကြားထားပါ — lifetime တိုးတယ်။\n"
        "2. 🌙 ညဘက် (Off-peak) အားသွင်းရင် စျေးသက်သာတယ်။\n"
        "3. ❄️ အအေးချိန်မှာ range ကျတတ်သည် — သတိထားပါ။\n"
        "4. ⚡ DC Fast Charge ကို မကြာမကြာ မသုံးပါနဲ့ — battery ထိခိုက်နိုင်တယ်။\n"
        "5. 🔄 တစ်လတစ်ကြိမ် 100% အထိ အားသွင်းပြီး calibrate လုပ်ပါ။\n"
        "6. 🌡️ အပူချိန်လွန်ကဲသော နေရာတွေမှာ ကားရပ်ထားတာ ရှောင်ပါ။"
    )

def get_off_peak_reminder() -> str:
    """Off-peak charging reminder ပြတယ်။"""
    return (
        "🌙 <b>Off-Peak Charging Reminder</b>\n\n"
        "ည ၁၀ နာရီမှ မနက် ၆ နာရီ အတွင်း အားသွင်းတာက "
        "လျှပ်စစ်ဓာတ်အားခ သက်သာစေနိုင်ပါတယ်။\n"
        "Battery ကို 80% ထိသာ အားသွင်းပါ။"
    )

def get_service_reminder() -> str:
    """Service reminder ပြတယ်။"""
    return (
        "🛠️ <b>Service Reminder</b>\n\n"
        "ထုတ်လုပ်သူ လမ်းညွှန်ချက်အတိုင်း ပုံမှန် Service လုပ်ဖို့ မမေ့ပါနဲ့။\n"
        "EV တွေမှာ Engine မပါပေမယ့် ဘရိတ်၊ တာယာ၊ Battery စနစ်တွေ စစ်ဆေးဖို့ လိုအပ်ပါတယ်။"
    )

def get_tyre_pressure_reminder() -> str:
    """Tyre pressure reminder ပြတယ်။"""
    return (
        "⚠️ <b>Tyre Pressure Reminder</b>\n\n"
        "လုံခြုံစိတ်ချရသော မောင်းနှင်မှုနှင့် စွမ်းအင်ချွေတာမှုအတွက် "
        "တာယာ လေဖိအားကို ပုံမှန်စစ်ဆေးပါ။"
    )
