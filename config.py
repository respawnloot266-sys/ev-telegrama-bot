import os

# Telegram Bot Token (အရေးကြီးဆုံး)
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8614528420:AAHSmddJFNh91T1hsbK8ryVgqK49RqHWIiU')

# Open Charge Map API Key (Charge Station တွေ ရှာဖို့)
# https://openchargemap.org/site/develop/api
OPEN_CHARGE_MAP_API_KEY = os.getenv('OPEN_CHARGE_MAP_API_KEY', 'YOUR_OPEN_CHARGE_MAP_API_KEY_HERE')

# Database File Name
DATABASE_NAME = 'ev_bot.db'

# Default Low Battery Threshold (ရာခိုင်နှုန်း)
DEFAULT_LOW_BATTERY_THRESHOLD = 20

# Default Max Charge Rate (kW) for calculations if not specified by car model
DEFAULT_MAX_CHARGE_RATE_KW = 50 # e.g., for a typical DC fast charger

# Charger Types (အကြံပြုချက်အတွက်)
CHARGER_TYPES = ['CCS2', 'Type1', 'CHAdeMO', 'Type2']

# Railway Environment Variables (Deployment အတွက်)
# Railway မှာ deploy လုပ်တဲ့အခါ ဒီ variable တွေကို Railway dashboard ကနေ ထည့်သွင်းပေးရပါမယ်။
# Local မှာ run ရင်တော့ .env file ထဲမှာ ထည့်သွင်းနိုင်ပါတယ်။