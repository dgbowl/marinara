import dash
from dash import html, dcc, callback, Input, Output, State
from marinara.utils import format_obj

dash.register_page(__name__, path="/components", title="Components")

layout = html.Div(
    className="dashboard-container",
    children=[
        html.Div(
            className="theme-header",
            children=[
                html.Div(
                    children=[
                        html.H2("Components", className="inline", style={"margin": 0, "font-size": "22px"}),
                        html.Button("⟳", id="tomato-status", className="btn-reload", title="Reload status data"),
                    ],
                    style={"display": "flex", "align-items": "center"}
                )
            ]
        ),
        html.Div(
            className="card",
            children=[
                html.Div("Loading data or service inactive. Please click the reload button above to check status.", 
                         id="tomato-list-components",
                         className="text-secondary", style={"text-align": "center", "padding": "40px"})
            ]
        )
    ]
)

@callback(
    Output("tomato-list-components", "children"),
    Input("tomato-status", "n_clicks"),
    State("tomato-port", "data"),
)
def update_components(n_clicks, port):
    try:
        import zmq
        from tomato import tomato
        CTXT = zmq.Context()
        ret = tomato.status(stgrp="tomato", port=port, timeout=1000, context=CTXT)
        if not ret.success:
            return html.Div(f"No data found. Error: {ret.msg}. Please check the reload button above.", 
                            className="text-secondary", style={"text-align": "center", "padding": "20px"})
        cmps = ret.data.cmps
        return format_obj(
            obj=cmps,
            headers=["Component Name", "Driver", "Address", "Channel", "Role", "Capabilities"],
            attrs=["name", "driver", "address", "channel", "role", "capabilities"],
            otype="components",
            port=port
        )
    except Exception as e:
        return html.Div(f"Error loading components: {str(e)}", className="text-secondary", style={"padding": "20px"})
