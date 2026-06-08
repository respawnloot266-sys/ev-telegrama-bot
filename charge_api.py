import os
import requests

OPEN_CHARGE_MAP_API_KEY = os.getenv("OPEN_CHARGE_MAP_API_KEY")
OPEN_CHARGE_MAP_BASE_URL = "https://api.openchargemap.io/v3/poi/"

def get_nearby_charging_stations(latitude, longitude, distance=5, units="KM", max_results=5, charger_type_id=None):
    """နီးဆုံး Charging Station များ ရှာဖွေတယ်။"""
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
    }

    if charger_type_id:
        params["connectiontypeid"] = charger_type_id

    try:
        response = requests.get(OPEN_CHARGE_MAP_BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        print("API request timeout ဖြစ်သွားပါသည်။")
        return []
    except requests.exceptions.RequestException as e:
        print(f"Charging station ရှာမရပါ: {e}")
        return []

def get_charger_types():
    """ရရှိနိုင်သော Charger Type များ ရယူတယ်။"""
    if not OPEN_CHARGE_MAP_API_KEY:
        return {}

    params = {
        "key": OPEN_CHARGE_MAP_API_KEY,
        "output": "json",
        "action": "GetConnectionTypes",
        "camelcase": True,
    }

    try:
        response = requests.get(OPEN_CHARGE_MAP_BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        connection_types = response.json()
        return {ct["title"]: ct["id"] for ct in connection_types}
    except requests.exceptions.RequestException as e:
        print(f"Charger type ရယူမရပါ: {e}")
        return {}


# Testing
if __name__ == "__main__":
    test_lat = 16.8409
    test_lon = 96.1735
    print(f"Yangon အနီး Station ရှာနေပါသည်...")
    stations = get_nearby_charging_stations(test_lat, test_lon, distance=10, max_results=3)
    if stations:
        for station in stations:
            print(f"Station: {station.get('addressInfo', {}).get('title')}")
            print(f"  Distance: {station.get('addressInfo', {}).get('distance', 0):.2f} KM")
    else:
        print("Station မတွေ့ပါ သို့မဟုတ် Error ဖြစ်ပါသည်။")
