import requests
from config import OCM_API_KEY

def find_nearest(lat, lon, radius=10):
    if not OCM_API_KEY:
        return [
            {"name": "Yangon EV Station 1", "address": "Sule Pagoda Rd", "power": 50, "cost": 350},
            {"name": "Yangon EV Station 2", "address": "Bahan", "power": 22, "cost": 300},
            {"name": "EV Charge Myanmar", "address": "Kamaryut", "power": 150, "cost": 400},
        ]
    try:
        url = "https://api.openchargemap.io/v3/poi/"
        params = {
            "output": "json",
            "latitude": lat,
            "longitude": lon,
            "distance": radius,
            "distanceunit": "KM",
            "maxresults": 5,
            "key": OCM_API_KEY
        }
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        stations = []
        for item in data:
            stations.append({
                "name": item.get("AddressInfo", {}).get("Title", "Unknown"),
                "address": item.get("AddressInfo", {}).get("AddressLine1", ""),
                "power": item.get("Connections", [{}])[0].get("PowerKW", 0) if item.get("Connections") else 0,
                "cost": "N/A"
            })
        return stations
    except:
        return []