import solara
import datetime as dt
import ipyleaflet
import os
import openai
from pydantic import BaseModel, Field
from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers.openai_functions import JsonOutputFunctionsParser
from langchain.utils.openai_functions import convert_pydantic_to_openai_function
import requests
from bs4 import BeautifulSoup

#from dotenv import load_dotenv, find_dotenv
#_ = load_dotenv(find_dotenv())

def get_ticketmaster_events(api_key, location_events, topic, date, max_results=20):
    endpoint = "https://app.ticketmaster.com/discovery/v2/events.json"
    params = {
        "apikey": api_key,
        "keyword": topic,
        "locale": "*",
        "startDateTime": date + "T00:00:00Z",
        "city": location_events,
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

def scrap_gg_image(keyword):
    params = {"q": 'travel '+keyword,
              "tbm": "isch", 
              "content-type": "image/png",
             }
    html = requests.get("https://www.google.com/search", params=params)
    soup = BeautifulSoup(html.text, 'html.parser')
    image_list = []
    for img in soup.select("img"):
        if 'googlelogo' not in img['src']:
            image_list.append(img['src'])
    return(image_list)


OPENAI_API_KEY = solara.reactive("")
key_provided = solara.reactive(False)
location = solara.reactive("Paris")
zoom = solara.reactive(10)
center = solara.reactive((48.8566, 2.3522))
bounds = solara.reactive(None)
markers = solara.reactive([])
image = solara.reactive([])

def add_marker(longitude, latitude, label):
    markers.set(markers.value + [{"location": (latitude, longitude), "label": label}])
    return "Marker added"

url = ipyleaflet.basemaps.OpenStreetMap.Mapnik.build_url()

@solara.component
def FirstComponent():
    dates = solara.use_reactive(tuple([None, None]))
    solara.lab.InputDateRange(dates, label="Select traveling dates")
    if dates.value != tuple([None, None]):
        if len(dates.value) == 2:
            if (dates.value[1]-dates.value[0]).days == 1:
                solara.Text(f"You are traveling for {(dates.value[1]-dates.value[0]).days} day from " + str(dates.value[0].strftime("%A, %d %B %Y")) + " to " + str(dates.value[1].strftime("%A, %d %B %Y"))+".")
            else:
                solara.Text(f"You are traveling for {(dates.value[1]-dates.value[0]).days} days from " + str(dates.value[0].strftime("%A, %d %B %Y")) + " to " + str(dates.value[1].strftime("%A, %d %B %Y"))+".")

    solara.InputText("Select traveling location", value=location)
    if location.value != "":
        solara.Text(f"You are traveling to {location.value}. How exciting!")
        os.environ["OPENAI_API_KEY"] = f"{OPENAI_API_KEY.value}"
        model = ChatOpenAI(temperature=0)
        model_with_functions = model.bind(functions=tagging_functions)
        prompt = ChatPromptTemplate.from_messages([
            ("system", "Think carefully, and then tag the text as required"),
            ("user", "{input}")
        ])
        output_parser = JsonOutputFunctionsParser()
        tagging_chain = prompt | model_with_functions | output_parser

        location_dict = tagging_chain.invoke({"input": f"{location.value}"})
        solara.Text(f"Location: {location_dict['location']}")
        solara.Text(f"Latitude: {location_dict['latitude']}")
        solara.Text(f"Longitude: {location_dict['longitude']}")
        location.value = location_dict['location']
        center.value = (location_dict['latitude'], location_dict['longitude'])
        image.value = scrap_gg_image(location.value)

@solara.component
def Map():
    ipyleaflet.Map.element(  # type: ignore
        zoom=zoom.value,
        center=center.value,
        scroll_wheel_zoom=True,
        layers=[
           ipyleaflet.TileLayer.element(url=url),
           *[
           ipyleaflet.Marker.element(location=k["location"], title=k["label"], draggable=False)
           for k in markers.value
           ],
        ],
    )

@solara.component
def image_tile():
    disp_item = 16 # google image provide up to 20 image
    with solara.GridFixed(columns=4, align_items="end", justify_items="stretch"):
        for img in image.value[:disp_item]:
            solara.Image(img, width='100%')

class Location(BaseModel):
    """Tag the text with the information required"""
    location: str = Field(description="the location")
    latitude: float = Field(description="the latitude of the location")
    longitude: float = Field(description="the longitude of the location")

tagging_functions = [convert_pydantic_to_openai_function(Location)]

@solara.component
def Page():
    with solara.Columns([1, 2, 2]):
        if OPENAI_API_KEY.value == "":
            solara.InputText("Enter your OpenAI API key", value=OPENAI_API_KEY, password=True)
        else:
            #openai.api_key = os.environ[f"{OPENAI_API_KEY.value}"]
            FirstComponent()
            # Replace with user inputs
            api_key = "MnRuGyDQ0gK5M1K1oed5herUtS34Y8Bs"
            topic = "rock"
            date = "2023-12-31"
            def get_events():
                events = get_ticketmaster_events(api_key, location.value, topic, date)
                for event in events:
                    add_marker(event["longitude"], event["latitude"], event["name"])
                return events
            events = solara.use_memo(get_events, [location.value])

            if image.value:
                image_tile()

            with solara.Column():
                Map()
                if not events:
                   solara.Warning("Not events found.")