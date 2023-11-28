import requests

def get_ticketmaster_events(api_key, location, topic, date, max_results=20):
    endpoint = "https://app.ticketmaster.com/discovery/v2/events.json"
    params = {
        "apikey": api_key,
        "keyword": topic,
        "locale": "*",
        "startDateTime": date + "T00:00:00Z",
        "city": location,
        "size": max_results
    }

    try:
        response = requests.get(endpoint, params=params)
        response.raise_for_status()  # Will raise an HTTPError if the HTTP request returned an unsuccessful status code
    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
        return []

    data = response.json()
    events = data.get("_embedded", {}).get("events", [])

    events_list = []
    unique_events = set()

    for event in events:
        name = event["name"]
        venue = event.get("_embedded", {}).get("venues", [{}])[0]
        venue_name = venue.get("name", "Unknown Venue")
        lat = venue.get("location", {}).get("latitude")
        lon = venue.get("location", {}).get("longitude")

        if name not in unique_events and lat and lon:
            unique_events.add(name)
            event_details = {
                "name": name,
                "venue_name": venue_name,
                "latitude": float(lat),
                "longitude": float(lon)
            }
            events_list.append(event_details)

            if len(unique_events) >= max_results:
                break

    print("Events fetched:", len(events_list))  # Debugging print statement
    return events_list

# Replace with user inputs
api_key = "MnRuGyDQ0gK5M1K1oed5herUtS34Y8Bs"
location = "New York"
topic = "indie rock"
date = "2023-12-31"
events = get_ticketmaster_events(api_key, location, topic, date)

# Check if events list is populated
if events:
    for event in events:
        print(event)
else:
    print("No events found.")
