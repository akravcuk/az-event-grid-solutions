import azure.functions as func
from monitor_ip_usage import monitor_ip_usage
import json

app = func.FunctionApp()

@app.function_name("MonitorIPUsage")
@app.event_grid_trigger(arg_name="azdoc")
def event_grid_trigger(azdoc: func.EventGridEvent) -> None:
    monitor_ip_usage(azdoc)
