import solara
import datetime as dt

@solara.component
def Page():
    dates = solara.use_reactive(tuple([dt.date.today(), dt.date.today() + dt.timedelta(days=1)]))
    solara.lab.InputDateRange(dates)
    
    #solara.Text(str(dates.value))
    solara.Text("You are travelling from " + str(dates.value[0].strftime("%A, %d %B %Y")) + " to " + str(dates.value[1].strftime("%A, %d %B %Y"))+".")
