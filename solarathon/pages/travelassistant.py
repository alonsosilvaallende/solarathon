import solara
import asyncio
import datetime
import ipyleaflet
from ipyleaflet import AwesomeIcon
import os
import openai
from typing import List
from pydantic import BaseModel, Field
from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers.openai_functions import JsonOutputFunctionsParser
from langchain.schema.output_parser import StrOutputParser
from langchain.output_parsers.openai_functions import JsonKeyOutputFunctionsParser
from langchain.utils.openai_functions import convert_pydantic_to_openai_function
import requests
from bs4 import BeautifulSoup
# needed to make calls to OpenAI concurrently
import nest_asyncio
nest_asyncio.apply()

#from dotenv import load_dotenv, find_dotenv
#_ = load_dotenv(find_dotenv())

def get_season(date: datetime.datetime, north_hemisphere: bool = True) -> str:
    now = (date.month, date.day)
    if (3, 21) <= now < (6, 21):
        season = 'spring' if north_hemisphere else 'fall'
    elif (6, 21) <= now < (9, 21):
        season = 'summer' if north_hemisphere else 'winter'
    elif (9, 21) <= now < (12, 21):
        season = 'fall' if north_hemisphere else 'spring'
    else:
        season = 'winter' if north_hemisphere else 'summer'
    return season

# Scrap Google Images of a city during a season
# e.g. 'travel Paris winter'
def scrap_gg_images(keyword, season=""):
    params = {"q": 'travel '+keyword+season,
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

# Get ticketmaster events for a date and a topic
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


OPENAI_API_KEY = solara.reactive("")
key_provided = solara.reactive(False)
location = solara.reactive("Paris")
result = solara.reactive("")
zoom = solara.reactive(10)
center = solara.reactive((48.8566, 2.3522))
bounds = solara.reactive(None)
markers = solara.reactive([])
current_events = solara.reactive(False)
initial_images = scrap_gg_images(f"{location.value}")
images = solara.reactive(initial_images)
topic_keyword = solara.reactive("rock")

def add_marker(longitude, latitude, label, icon):
    markers.set(markers.value + [{"location": (latitude, longitude), "label": label, "icon": icon}])
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
    solara.Checkbox(label="Concerts happening on those dates", value=current_events)
    solara.InputText("Select concerts topic", value=topic_keyword)
    solara.InputText("Select traveling location", value=location)
    if location.value != "":
        solara.Markdown(f"You are traveling to {location.value}. How exciting!\n\nThe main turistic attractions in {location.value} are:")
        if dates.value != tuple([None, None]):
            images.value = scrap_gg_images(f"{location.value}", f"{get_season(dates.value[0])}")
        else:
            images.value = scrap_gg_images(f"{location.value}")
        os.environ["OPENAI_API_KEY"] = f"{OPENAI_API_KEY.value}"
        # Tagging chain to determine the location, its latitude and its longitude
        def get_location():
            model = ChatOpenAI(temperature=0)
            model_with_functions = model.bind(functions=tagging_functions)
            prompt = ChatPromptTemplate.from_messages([
                ("system", "Think carefully, and then tag the text as required"),
                ("user", "{input}")
            ])
            output_parser = JsonOutputFunctionsParser()
            tagging_chain = prompt | model_with_functions | output_parser
            location_dict = tagging_chain.invoke({"input": f"{location.value}"})
            location.value = location_dict['location']
            center.value = (location_dict['latitude'], location_dict['longitude'])

        precise_location = solara.use_thread(get_location, [location.value])
        solara.ProgressLinear(precise_location.state == solara.ResultState.RUNNING)
        # Chain to obtain the top 10 touristic attractions in a location
        def get_top10():
            model = ChatOpenAI(temperature=0)
            prompt_get_top10 = ChatPromptTemplate.from_messages([
                ("system", "You are a helpful travel assistant"),
                ("user", "Give me the top 10 touristic attractions names in {input}. Do not add comments.")
            ])
            output_parser_get_top10 = StrOutputParser()
            chain_get_top10 = prompt_get_top10 | model | output_parser_get_top10
            partial_result = chain_get_top10.invoke({"input": location.value})
            return partial_result
        partial_result = solara.use_thread(get_top10, [location.value])
        solara.ProgressLinear(partial_result.state == solara.ResultState.RUNNING)
        if partial_result.value is None:
            return
        result.value = partial_result.value
        solara.Markdown(result.value)
    
        def get_attractions():
            # Extraction chain to obtain latitude and longitude of the top 10 touristic attractions in a location
            model = ChatOpenAI(temperature=0)
            extraction_model = model.bind(functions=extraction_functions, function_call={"name": "Information"})
            extraction_output_parser = JsonKeyOutputFunctionsParser(key_name="TuristicAttractions")
            extraction_prompt = ChatPromptTemplate.from_messages([
                ("system", "Extract the relevant information, if not explicitly provided do not guess. Extract partial info"),
                ("human", "{input}")
            ])
            extraction_chain = extraction_prompt | extraction_model | extraction_output_parser
            async def async_invoke(input):
                return await extraction_chain.ainvoke({"input": f"{input}"})

            async def invoke_concurrently():
                tasks = [async_invoke(attraction) for attraction in result.value.split('\n')]
                return await asyncio.gather(*tasks)

            attractions = asyncio.run(invoke_concurrently())
            for attraction in attractions:
                add_marker(attraction[0]["longitude"], attraction[0]["latitude"], attraction[0]["name"], "icon_attraction")

            return attractions
        attractions = solara.use_thread(get_attractions, [result.value])
        solara.ProgressLinear(attractions.state == solara.ResultState.RUNNING)

        if attractions.value is None:
            return
        #for attraction in attractions.value:
        #    add_marker(attraction[0]["longitude"], attraction[0]["latitude"], attraction[0]["name"], "icon_attraction")


@solara.component
def Map():
    def my_icon(icon):
        return AwesomeIcon(name="music", marker_color="red") if icon=="icon_event" else AwesomeIcon(name="bolt", marker_color="blue")
    ipyleaflet.Map.element(  # type: ignore
        zoom=zoom.value,
        center=center.value,
        scroll_wheel_zoom=True,
        layers=[
           ipyleaflet.TileLayer.element(url=url),
           *[
           ipyleaflet.Marker.element(location=k["location"], title=k["label"], draggable=False, icon=my_icon(k["icon"]))
           for k in markers.value
           ],
        ],
    )
class Location(BaseModel):
    """Tag the text with the information required"""
    location: str = Field(description="the location")
    latitude: float = Field(description="the latitude of the location")
    longitude: float = Field(description="the longitude of the location")

tagging_functions = [convert_pydantic_to_openai_function(Location)]

class TuristicAttraction(BaseModel):
    """Information about a touristic attraction"""
    name: str = Field(description="The name of the touristic attraction")
    latitude: float = Field(description="the latitude of the touristic attraction")
    longitude: float = Field(description="the longitude of the touristic attraction")

class Information(BaseModel):
    """Information to extract."""
    TuristicAttractions: List[TuristicAttraction] = Field(description="List of info about touristic attractions")

extraction_functions = [convert_pydantic_to_openai_function(Information)]

@solara.component
def DisplayImages(images):
    with solara.GridFixed(columns=3, align_items="end", justify_items="stretch"):
        for img in images:
            solara.Image(img, width='300')

@solara.component
def Page():
    with solara.Columns(style={"height": "calc(100% - 30px)"}):
        #if False:
        if OPENAI_API_KEY.value == "":
            solara.InputText("Enter your OpenAI API key", value=OPENAI_API_KEY, password=True)
        else:
            #openai.api_key = os.environ[f"{OPENAI_API_KEY.value}"]
            os.environ["OPENAI_API_KEY"] = f"{OPENAI_API_KEY.value}"
            FirstComponent()
            # Replace with user inputs
            api_key = "MnRuGyDQ0gK5M1K1oed5herUtS34Y8Bs"
            topic = topic_keyword.value
            date = "2023-12-31"
            def get_events():
                if current_events.value:
                    events = get_ticketmaster_events(api_key, location.value, topic, date)
                    for event in events:
                        add_marker(event["longitude"], event["latitude"], event["name"], "icon_event")
                    return events
                else:
                    markers.value = []
            events = solara.use_memo(get_events, [location.value, current_events.value])
            DisplayImages(images.value)
            Map()
#            if not events:
#                solara.Text("Not events found.")
