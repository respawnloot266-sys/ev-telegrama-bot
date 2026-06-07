import math
from datetime import datetime, timedelta
from config import DEFAULT_MAX_CHARGE_RATE_KW

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculates distance between two GPS coordinates in kilometers."""
    R = 6371  # Radius of Earth in kilometers

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) * math.sin(dlat / 2) + \
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
        math.sin(dlon / 2) * math.sin(dlon / 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c
    return distance

def calculate_charge_time(start_percent, end_percent, battery_capacity_kwh, max_charge_rate_kw=DEFAULT_MAX_CHARGE_RATE_KW):
    """Calculates approximate charge time in minutes.
    Assumes linear charging for simplicity. Real-world charging is non-linear.
    """
    if start_percent >= end_percent:
        return 0

    # Usable capacity needed in kWh
    kwh_needed = battery_capacity_kwh * (end_percent - start_percent) / 100

    # Time in hours
    time_hours = kwh_needed / max_charge_rate_kw

    # Time in minutes
    time_minutes = time_hours * 60
    return round(time_minutes)

def format_charge_history(history_records):
    """Formats charge history records into a human-readable string."""
    if not history_records:
        return "အားသွင်းမှတ်တမ်း မရှိသေးပါဘူး။"

    message = "🔌 **အားသွင်းမှတ်တမ်းများ** 🔌\n\n"
    for record in history_records:
        # Assuming record is a tuple: (id, user_id, start_time, end_time, start_battery, end_battery, kwh_charged, cost, station_name, station_id, charger_type)
        start_time_dt = datetime.strptime(record[2], 
'%Y-%m-%d %H:%M:%S') if isinstance(record[2], str) else record[2]
        end_time_dt = datetime.strptime(record[3], 
'%Y-%m-%d %H:%M:%S') if isinstance(record[3], str) else record[3]
        duration = end_time_dt - start_time_dt
        duration_str = str(timedelta(seconds=round(duration.total_seconds())))

        message += f"🗓️ **ရက်စွဲ:** {start_time_dt.strftime('%Y-%m-%d %H:%M')}\n"
        message += f"🔋 **Battery:** {record[4]}% -> {record[5]}%\n"
        if record[6]:
            message += f"⚡ **ဖြည့်သွင်း:** {record[6]:.2f} kWh\n"
        if record[7]:
            message += f"💸 **ကုန်ကျစရိတ်:** {record[7]:.2f} ကျပ်\n"
        if record[8]:
            message += f"📍 **Station:** {record[8]} ({record[10] or 'N/A'})\n"
        message += f"⏱️ **ကြာချိန်:** {duration_str}\n"
        message += "--------------------\n"
    return message

def get_monthly_report(user_id, charge_history_records):
    """Generates a monthly report for charge history."""
    total_kwh = 0.0
    total_cost = 0.0
    current_month = datetime.now().month
    current_year = datetime.now().year

    for record in charge_history_records:
        end_time_dt = datetime.strptime(record[3], 
'%Y-%m-%d %H:%M:%S') if isinstance(record[3], str) else record[3]
        if end_time_dt.month == current_month and end_time_dt.year == current_year:
            if record[6]: # kwh_charged
                total_kwh += record[6]
            if record[7]: # cost
                total_cost += record[7]
    
    if total_kwh == 0 and total_cost == 0:
        return f"ဒီလ ({datetime.now().strftime('%B %Y')}) အတွက် အားသွင်းမှတ်တမ်း မရှိသေးပါဘူး။"

    message = f"📊 **{datetime.now().strftime('%B %Y')} လစဉ် အစီရင်ခံစာ** 📊\n\n"
    message += f"⚡ **စုစုပေါင်း ဖြည့်သွင်း:** {total_kwh:.2f} kWh\n"
    message += f"💸 **စုစုပေါင်း ကုန်ကျစရိတ်:** {total_cost:.2f} ကျပ်\n"
    message += "\n🔋 Battery သက်တမ်း ရှည်ဖို့ အကြံပြုချက်များ ကိုလည်း ဖတ်ရှုနိုင်ပါတယ်။"
    return message

def get_battery_health_tips():
    """Returns general battery health tips."""
    tips = [
        "🔋 **Battery Health Tips:**\n",
        "1. ကားကို ၁၀၀% အထိ အမြဲအားမသွင်းပါနဲ့။ ၈၀% - ၉၀% ကြားမှာ ရပ်တာက Battery သက်တမ်းကို ပိုရှည်စေပါတယ်။",
        "2. Battery ကို ၀% အထိ လုံးဝ မကျပါစေနဲ့။ ၂၀% အောက် မရောက်ခင် အားပြန်သွင်းပါ။",
        "3. အပူချိန်လွန်ကဲတဲ့ နေရာတွေမှာ ကားကို ရပ်တာ၊ အားသွင်းတာ ရှောင်ပါ။",
        "4. DC Fast Charging ကို မကြာခဏ အသုံးမပြုပါနဲ့။ AC Charging က Battery အတွက် ပိုကောင်းပါတယ်။",
        "5. ကားကို အကြာကြီး ရပ်ထားမယ်ဆိုရင် Battery ကို ၅၀% ဝန်းကျင်မှာ ထားပါ။"
    ]
    return "\n".join(tips)

def get_off_peak_reminder():
    """Returns off-peak charging reminder."""
    return "💡 **Off-peak Charging Reminder:**\nညဘက် (ဥပမာ - ည ၁၀ နာရီမှ မနက် ၆ နာရီ) မှာ အားသွင်းတာက လျှပ်စစ်ဓာတ်အားခ သက်သာစေနိုင်ပါတယ်။ သင့်ဒေသရဲ့ off-peak အချိန်တွေကို စစ်ဆေးပြီး အားသွင်းပါ။"

def get_service_reminder():
    """Returns a general service reminder."""
    return "🛠️ **Service Reminder:**\nသင့်ကားရဲ့ ထုတ်လုပ်သူ လမ်းညွှန်ချက်အတိုင်း ပုံမှန် Service လုပ်ဖို့ မမေ့ပါနဲ့။ EV တွေမှာ Engine မပါပေမယ့် ဘရိတ်၊ တာယာ၊ Battery စနစ်တွေကို စစ်ဆေးဖို့ လိုအပ်ပါတယ်။"

def get_tyre_pressure_reminder():
    """Returns a tyre pressure reminder."""
    return "⚠️ **Tyre Pressure Reminder:**\nလုံခြုံစိတ်ချရသော မောင်းနှင်မှုနှင့် စွမ်းအင်ချွေတာမှုအတွက် သင့်ကားတာယာ လေဖိအားကို ပုံမှန်စစ်ဆေးပါ။ ထုတ်လုပ်သူ သတ်မှတ်ထားသော လေဖိအားအတိုင်း ထားရှိပါ။"