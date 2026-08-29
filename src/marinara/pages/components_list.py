import dash
from dash import Input, Output, State, callback, html
from tomato import tomato

from marinara.icons import get_icon
from marinara.utils import format_obj, kwargs

dash.register_page(__name__, path="/components", title="Components")

layout = html.Div(
    className="dashboard-container",
    children=[
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
            id="tomato-list-components",
            className="text-secondary",
            children="Loading data...",
        ),
    ],
)


@callback(
    Output("tomato-list-components", "children"),
    Input("tomato-status", "n_clicks"),
    State("tomato-port", "data"),
)
def update_components(n_clicks, port):
    try:
        ret = tomato.status(stgrp="tomato", port=port, **kwargs)
        if not ret.success:
            return html.Div(
                f"No data found. Error: {ret.msg}. Please check the reload button above.",
                className="text-secondary",
                style={"text-align": "center", "padding": "20px"},
            )
        cmps = ret.data.cmps
        return format_obj(
            obj=cmps,
            headers=[
                "Component Name",
                "Driver",
                "Address",
                "Channel",
                "Role",
                "Capabilities",
            ],
            attrs=["name", "driver", "address", "channel", "role", "capabilities"],
            otype="components",
            port=port,
        )
    except Exception as e:
        return html.Div(
            f"Error loading components: {e!s}",
            className="text-secondary",
            style={"padding": "20px"},
        )
