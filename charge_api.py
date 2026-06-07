import requests
import math
from config import OCM_API_KEY, SEARCH_RADIUS_KM

def find_nearest_stations(lat, lon, limit=5, country="MM"):
    url = "https://api.openchargemap.io/v3/poi/"
    params = {
        "output": "json",
        "countrycode": country,
        "latitude": lat,
        "longitude": lon,
        "distance": SEARCH_RADIUS_KM,
        "distanceunit": "KM",
        "maxresults": limit,
        "key": OCM_API_KEY
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        return r.json()
    except Exception as e:
        print(f"API Error: {e}")
        return []

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2 + 
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * 
         math.sin(dlon/2)**2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def find_cheapest_station(lat, lon, country="MM"):
    return find_nearest_stations(lat, lon, limit=10, country=country)

def calculate_charge_time(battery_capacity_kwh, current_percent, target_percent, 
                          charger_power_kw=50):
    needed_kwh = battery_capacity_kwh * (target_percent - current_percent) / 100
    if needed_kwh <= 0:
        return 0
    hours = needed_kwh / charger_power_kw
    return round(hours, 2)