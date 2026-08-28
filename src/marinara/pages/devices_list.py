import dash
from dash import html, callback, Input, Output, State
from marinara.utils import format_obj

from marinara.icons import get_icon

dash.register_page(__name__, path="/devices", title="Devices")

layout = html.Div(
    className="dashboard-container",
    children=[
        html.Div(
            className="theme-header",
            children=[
                html.Div(
                    children=[
                        html.H2(
                            "Devices",
                            className="inline",
                            style={"margin": 0, "font-size": "22px"},
                        ),
                        html.Button(
                            get_icon("refresh", size=14, stroke_width=2.5),
                            id="tomato-status",
                            className="btn-reload",
                            title="Reload status data",
                        ),
                    ],
                    style={"display": "flex", "align-items": "center"},
                )
            ],
        ),
        html.Div(
            id="tomato-list-devices",
            className="text-secondary",
            children="Loading data...",
        ),
    ],
)


@callback(
    Output("tomato-list-devices", "children"),
    Input("tomato-status", "n_clicks"),
    State("tomato-port", "data"),
)
def update_devices(n_clicks, port):
    try:
        import zmq
        from tomato import tomato

        CTXT = zmq.Context()
        ret = tomato.status(stgrp="tomato", port=port, timeout=1000, context=CTXT)
        if not ret.success:
            return html.Div(
                f"No data found. Error: {ret.msg}. Please check the reload button above.",
                className="text-secondary",
                style={"text-align": "center", "padding": "20px"},
            )
        devs = ret.data.devicefile.devices
        return format_obj(
            obj=devs,
            headers=["Device Name", "Driver", "Address", "Channels"],
            attrs=["name", "driver", "address", "channels"],
            otype="devices",
            port=port,
        )
    except Exception as e:
        return html.Div(
            f"Error loading devices: {str(e)}",
            className="text-secondary",
            style={"padding": "20px"},
        )
