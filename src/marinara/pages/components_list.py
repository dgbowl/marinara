import logging
import dash
from dash import Input, Output, State, callback, dcc, html
from marinara.icons import get_icon
from marinara.utils import format_obj
from tomato import tomato
import zmq

logger = logging.getLogger(__name__)

dash.register_page(__name__, path="/components", title="Components")

layout = html.Div(
    className="dashboard-container",
    children=[
        dcc.Interval(id="components-load-interval", interval=500, max_intervals=1),
        html.Div(
            className="theme-header",
            children=[
                html.Div(
                    children=[
                        html.H2(
                            "Components",
                            className="inline",
                            style={"margin": 0, "font-size": "22px"},
                        ),
                        html.Button(
                            get_icon("refresh", size=14, stroke_width=2.5),
                            id="components-reload-btn",
                            className="btn-reload",
                            title="Reload status data",
                        ),
                    ],
                    style={"display": "flex", "align-items": "center"},
                )
            ],
        ),
        html.Div(
            id="tomato-list-components",
            className="text-secondary",
            children="Loading data...",
        ),
    ],
)


@callback(
    Output("tomato-list-components", "children"),
    Input("components-reload-btn", "n_clicks"),
    Input("components-load-interval", "n_intervals"),
    State("tomato-port", "data"),
)
def update_components(n_clicks, n_intervals, port):
    try:
        CTXT = zmq.Context()
        ret = tomato.status(stgrp="components", port=port, timeout=1000, context=CTXT)
        if not ret.success:
            return html.Div(
                f"No data found. Error: {ret.msg}. Please check the reload button above.",
                className="text-secondary",
                style={"text-align": "center", "padding": "20px"},
            )
        cmps = ret.data.cmps if hasattr(ret.data, "cmps") else ret.data
        return format_obj(
            obj=cmps,
            headers=[
                "Component Name",
                "Driver",
                "Address",
                "Channel",
                "Capabilities",
            ],
            attrs=["name", "driver", "address", "channel", "capabilities"],
            otype="components",
            port=port,
        )
    except Exception as e:
        logger.error("Error loading components: %s", e)
        return html.Div(
            f"Error loading components: {str(e)}",
            className="text-secondary",
            style={"padding": "20px"},
        )
