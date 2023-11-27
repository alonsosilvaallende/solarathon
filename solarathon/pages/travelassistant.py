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

from dotenv import load_dotenv, find_dotenv
_ = load_dotenv(find_dotenv())
openai.api_key = os.environ["OPENAI_API_KEY"]

class Location(BaseModel):
    """Tag the text with the information required"""
    latitude: float = Field(description="the latitude of the location")
    longitude: float = Field(description="the longitude of the location")

tagging_functions = [convert_pydantic_to_openai_function(Location)]
model = ChatOpenAI(temperature=0)
model_with_functions = model.bind(functions=tagging_functions)
prompt = ChatPromptTemplate.from_messages([
    ("system", "Think carefully, and then tag the text as required"),
    ("user", "{input}")
])
output_parser = JsonOutputFunctionsParser()
tagging_chain = prompt | model_with_functions | output_parser

location = solara.reactive("")
zoom = solara.reactive(10)
center = solara.reactive((48.8566, 2.3522))
bounds = solara.reactive(None)

@solara.component
def Page():
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
        location_dict = tagging_chain.invoke({"input": f"{location.value}"})
        solara.Text(f"Latitude: {location_dict['latitude']}")
        solara.Text(f"Longitude: {location_dict['longitude']}")
        center.value = (location_dict['latitude'], location_dict['longitude'])
        with solara.Column(style={"max-width": "500px", "height": "500px"}):
            solara.SliderInt(label="Zoom level", value=zoom, min=1, max=20)
            ipyleaflet.Map.element(  # type: ignore
                    zoom=zoom.value,
                    on_zoom=zoom.set,
                    center=center.value,
                    on_center=center.set,
                    on_bounds=bounds.set,
                    scroll_wheel_zoom=True,
                )
