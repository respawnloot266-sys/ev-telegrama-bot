import os
import requests

OPEN_CHARGE_MAP_API_KEY = os.getenv("OPEN_CHARGE_MAP_API_KEY")
OPEN_CHARGE_MAP_BASE_URL = "https://api.openchargemap.io/v3/poi/"

def get_nearby_charging_stations(latitude, longitude, distance=10, units="KM", max_results=5, charger_type_id=None):
    if not OPEN_CHARGE_MAP_API_KEY:
        print("OPEN_CHARGE_MAP_API_KEY မရှိပါ။")
        return []

    params = {
        "key": OPEN_CHARGE_MAP_API_KEY,
        "output": "json",
        "latitude": latitude,
        "longitude": longitude,
        "distance": distance,
        "distanceunit": units,
        "maxresults": max_results,
        "camelcase": True,
        "verbose": False,
        "includecomments": False,
    }

    if charger_type_id:
        params["connectiontypeid"] = charger_type_id

    try:
        response = requests.get(OPEN_CHARGE_MAP_BASE_URL, params=params, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        print("API timeout ဖြစ်သွားပါသည်။")
        return []
    except requests.exceptions.RequestException as e:
        print(f"Station ရှာမရပါ: {e}")
        return []


def geocode_city(city_name):
    """
    မြို့နာမည်ကနေ lat/lon ရယူတယ် — Nominatim (free, no key needed)
    Myanmar မြို့တွေ အတွက် "city_name, Myanmar" ဆိုပြီး ရှာတယ်
    """
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": f"{city_name}, Myanmar",
            "format": "json",
            "limit": 1,
            "accept-language": "en",
        }
        headers = {"User-Agent": "EVHelperBot/1.0"}
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        results = response.json()
        if results:
            return float(results[0]["lat"]), float(results[0]["lon"]), results[0].get("display_name", city_name)
        return None, None, None
    except Exception as e:
        print(f"Geocode error: {e}")
        return None, None, None
