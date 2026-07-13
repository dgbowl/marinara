import dash
from dash import html, dcc, callback, Input, Output, State

dash.register_page(__name__, path="/pipelines", title="Pipelines")

layout = html.Div(
    className="dashboard-container",
    children=[
        html.Div(
            className="theme-header",
            children=[
                html.Div(
                    children=[
                        html.H2("Pipelines", className="inline", style={"margin": 0, "font-size": "22px"}),
                        html.Button("⟳", id="tomato-status", className="btn-reload", title="Reload status data"),
                    ],
                    style={"display": "flex", "align-items": "center"}
                )
            ]
        ),
        html.Div(
            id="tomato-list-pipelines",
            className="text-secondary",
            children="Loading data..."
        )
    ]
)

@callback(
    Output("tomato-list-pipelines", "children"),
    Input("tomato-status", "n_clicks"),
    State("tomato-port", "data"),
)
def update_pipelines(n_clicks, port):
    try:
        import zmq
        from tomato import tomato
        CTXT = zmq.Context()
        ret = tomato.status(stgrp="tomato", port=port, timeout=1000, context=CTXT)
        if not ret.success:
            return html.Div(f"No data found. Error: {ret.msg}. Please check the reload button above.", 
                            className="text-secondary", style={"text-align": "center", "padding": "20px"})
        pips = ret.data.pips
        cmps = ret.data.cmps
        if not pips:
            return html.Div("No pipelines registered in system.", className="text-secondary", style={"text-align": "center", "padding": "20px"})
            
        pipeline_cards = []
        for name, pip in pips.items():
            comp_rows = []
            for cname in pip.components:
                cmp = cmps.get(cname)
                if cmp:
                    capabilities_str = ", ".join(cmp.capabilities) if cmp.capabilities else "None"
                    comp_rows.append(
                        html.Tr(children=[
                            html.Td(cname, style={"font-weight": "600"}),
                            html.Td(cmp.driver),
                            html.Td(cmp.address),
                            html.Td(str(cmp.channel)),
                            html.Td(cmp.role),
                            html.Td(capabilities_str)
                        ])
                    )
                    
            if comp_rows:
                comp_table = html.Table(
                    children=[
                        html.Tr(children=[
                            html.Th("Component Name"),
                            html.Th("Driver"),
                            html.Th("Address"),
                            html.Th("Channel"),
                            html.Th("Role"),
                            html.Th("Capabilities")
                        ]),
                        *comp_rows
                    ],
                    className="stgrp stgrp-6col",
                    style={"margin-top": "10px", "border": "1px solid var(--border-color)", "font-size": "13px"}
                )
            else:
                comp_table = html.Div("No components registered for this pipeline.", className="text-secondary", style={"font-size": "13px", "padding": "10px"})
                
            pipeline_cards.append(
                html.Div(
                    className="card",
                    style={"margin-bottom": "20px", "padding": "20px"},
                    children=[
                        html.Div(
                            children=[
                                dcc.Link(name, href=f"/pipelines/{port}/{name}", style={"font-size": "18px", "font-weight": "700", "text-decoration": "none", "color": "var(--accent-color)"}),
                                html.Span("Ready" if pip.ready else "Busy", className="badge badge-success" if pip.ready else "badge badge-warning", style={"margin-left": "15px"})
                            ],
                            style={"display": "flex", "align-items": "center", "margin-bottom": "15px"}
                        ),
                        html.Div(
                            children=[
                                html.Div([html.Strong("Active Job ID: "), str(pip.jobid if pip.jobid is not None else "-")], style={"margin-right": "30px"}),
                                html.Div([html.Strong("Sample ID: "), str(pip.sampleid if pip.sampleid is not None else "-")]),
                            ],
                            style={"display": "flex", "font-size": "14px", "margin-bottom": "15px", "color": "var(--text-secondary)"}
                        ),
                        html.Div([
                            html.Div("Components Info", style={"font-weight": "600", "font-size": "14px", "margin-bottom": "8px"}),
                            comp_table
                        ])
                    ]
                )
            )
        return html.Div(pipeline_cards)
    except Exception as e:
        return html.Div(f"Error loading pipelines: {str(e)}", className="text-secondary", style={"padding": "20px"})
