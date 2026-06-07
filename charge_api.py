
import requests
from config import OPEN_CHARGE_MAP_API_KEY

OPEN_CHARGE_MAP_BASE_URL = "https://api.openchargemap.io/v3/poi/"

def get_nearby_charging_stations(latitude, longitude, distance=5, units="KM", max_results=5, charger_type_id=None):
    """Fetches nearby charging stations from Open Charge Map API.

    Args:
        latitude (float): User's current latitude.
        longitude (float): User's current longitude.
        distance (int): Search radius in specified units (default: 5 KM).
        units (str): Units for distance (KM or Miles).
        max_results (int): Maximum number of results to return.
        charger_type_id (int, optional): Filter by charger type ID (e.g., 25 for CCS Combo 2).

    Returns:
        list: A list of dictionaries, each representing a charging station.
    """
    params = {
        "key": OPEN_CHARGE_MAP_API_KEY,
        "output": "json",
        "latitude": latitude,
        "longitude": longitude,
        "distance": distance,
        "distanceunit": units,
        "maxresults": max_results,
        "camelcase": True, # For easier Python dictionary access
    }
    if charger_type_id:
        params["connectiontypeid"] = charger_type_id

    try:
        response = requests.get(OPEN_CHARGE_MAP_BASE_URL, params=params)
        response.raise_for_status()  # Raise an exception for HTTP errors
        stations = response.json()
        return stations
    except requests.exceptions.RequestException as e:
        print(f"Error fetching charging stations: {e}")
        return []

def get_charger_types():
    """Fetches available charger types from Open Charge Map API.

    Returns:
        dict: A dictionary mapping charger type names to their IDs.
    """
    params = {
        "key": OPEN_CHARGE_MAP_API_KEY,
        "output": "json",
        "action": "GetConnectionTypes",
        "camelcase": True,
    }
    try:
        response = requests.get(OPEN_CHARGE_MAP_BASE_URL, params=params)
        response.raise_for_status()
        connection_types = response.json()
        return {ct["title"]: ct["id"] for ct in connection_types}
    except requests.exceptions.RequestException as e:
        print(f"Error fetching charger types: {e}")
        return {}

# Example Usage (for testing purposes)
if __name__ == "__main__":
    # Replace with actual coordinates for testing
    test_lat = 16.8409
    test_lon = 96.1735

    print(f"Searching for stations near {test_lat}, {test_lon}...")
    stations = get_nearby_charging_stations(test_lat, test_lon, distance=10, max_results=3)
    if stations:
        for station in stations:
            print(f"Station: {station.get("addressInfo", {}).get("title")}")
            print(f"  Address: {station.get("addressInfo", {}).get("addressLine1")}")
            print(f"  Distance: {station.get("addressInfo", {}).get("distance"):.2f} KM")
            connections = station.get("connections", [])
            if connections:
                print("  Connections:")
                for conn in connections:
                    print(f"    - {conn.get("connectionType", {}).get("title")} ({conn.get("powerKW")} kW)")
            print("---")
    else:
        print("No stations found or an error occurred.")

    print("\nFetching charger types...")
    charger_types = get_charger_types()
    if charger_types:
        print("Available Charger Types:")
        for name, id in list(charger_types.items())[:5]: # Print first 5 for brevity
            print(f"- {name} (ID: {id})")
    else:
        print("Could not fetch charger types.")