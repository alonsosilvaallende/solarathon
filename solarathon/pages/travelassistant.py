import solara
import datetime as dt
import ipyleaflet

zoom = solara.reactive(10)
center = solara.reactive((48.8566, 2.3522))
bounds = solara.reactive(None)

@solara.component
def Page():
    dates = solara.use_reactive(tuple([dt.date.today(), dt.date.today() + dt.timedelta(days=1)]))
    solara.lab.InputDateRange(dates)
    
    #solara.Text(str(dates.value))
    solara.Text("You are travelling from " + str(dates.value[0].strftime("%A, %d %B %Y")) + " to " + str(dates.value[1].strftime("%A, %d %B %Y"))+".")
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
        solara.Text(f"Zoom: {zoom.value}")
        solara.Text(f"Center: {center.value}")
        solara.Text(f"Bounds: {bounds.value}")
