import logging

import dash
from dash import Input, Output, State, callback, html
from tomato import tomato

from marinara.icons import get_icon
from marinara.utils import format_obj, kwargs

logger = logging.getLogger(__name__)
dash.register_page(__name__, path="/drivers", title="Drivers")

layout = html.Div(
    className="dashboard-container",
    children=[
        html.Div(
            className="theme-header",
            children=[
                html.Div(
                    children=[
                        html.H2(
                            "Drivers",
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
            id="tomato-list-drivers",
            className="text-secondary",
            children="Loading data...",
        ),
    ],
)


@callback(
    Output("tomato-list-drivers", "children"),
    Input("tomato-status", "n_clicks"),
    State("tomato-port", "data"),
)
def update_drivers(n_clicks, port):
    try:
        ret = tomato.status(stgrp="tomato", port=port, **kwargs)
        if not ret.success:
            logger.warning(f"tomato.status returned failure: {ret.msg}")
            return html.Div(
                f"No data found. Error: {ret.msg}. Please check the reload button above.",
                className="text-secondary",
                style={"text-align": "center", "padding": "20px"},
            )
        drvs = ret.data.drvs
        return format_obj(
            obj=drvs,
            headers=["Driver Name", "Version", "Port", "Process ID (PID)"],
            attrs=["name", "version", "port", "pid"],
            otype="drivers",
            port=port,
        )
    except Exception as e:
        logger.warning("Exception during update_drivers:", exc_info=e)
        return html.Div(
            f"Error loading drivers: {e!s}",
            className="text-secondary",
            style={"padding": "20px"},
        )
