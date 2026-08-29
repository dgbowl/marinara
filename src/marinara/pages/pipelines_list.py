import logging

import dash
from dash import Input, Output, State, callback, dcc, html
from tomato import tomato

from marinara.icons import get_icon
from marinara.utils import kwargs

logger = logging.getLogger(__name__)

dash.register_page(__name__, path="/pipelines", title="Pipelines")

layout = html.Div(
    className="dashboard-container",
    children=[
        html.Div(
            className="theme-header",
            children=[
                html.Div(
                    children=[
                        html.H2(
                            "Pipelines",
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
            id="tomato-list-pipelines",
            className="text-secondary",
            children="Loading data...",
        ),
    ],
)


@callback(
    Output("tomato-list-pipelines", "children"),
    Input("tomato-status", "n_clicks"),
    State("tomato-port", "data"),
)
def update_pipelines(n_clicks, port):
    try:
        ret = tomato.status(stgrp="tomato", port=port, **kwargs)
        if not ret.success:
            logger.warning("tomato.status returned failure: %s", ret.msg)
            return html.Div(
                f"No data found. Error: {ret.msg}. Please check the reload button above.",
                className="text-secondary",
                style={"text-align": "center", "padding": "20px"},
            )
        pips = ret.data.pips
        cmps = ret.data.cmps
        if not pips:
            return html.Div(
                "No pipelines registered in system.",
                className="text-secondary",
                style={"text-align": "center", "padding": "20px"},
            )

        pipeline_cards = []
        for name, pip in pips.items():
            comp_details = []
            for cname in pip.components:
                cmp = cmps.get(cname)
                if cmp:
                    capabilities_str = (
                        ", ".join(str(x) for x in cmp.capabilities)
                        if cmp.capabilities
                        else "None"
                    )

                    comp_title = dcc.Link(
                        cname,
                        href=f"/components/{port}/{cname}",
                        style={
                            "font-size": "15px",
                            "font-weight": "700",
                            "text-decoration": "none",
                            "color": "var(--accent-color)",
                        },
                    )

                    metadata_row = html.Div(
                        children=[
                            html.Div(
                                [html.Strong("Driver: "), html.Span(cmp.driver)],
                                style={"margin-right": "25px"},
                            ),
                            html.Div(
                                [html.Strong("Address: "), html.Span(cmp.address)],
                                style={"margin-right": "25px"},
                            ),
                            html.Div(
                                [html.Strong("Channel: "), html.Span(str(cmp.channel))],
                                style={"margin-right": "25px"},
                            ),
                            html.Div(
                                [html.Strong("Role: "), html.Span(cmp.role)],
                                style={"margin-right": "25px"},
                            ),
                        ],
                        style={
                            "display": "flex",
                            "flex-wrap": "wrap",
                            "margin-top": "8px",
                            "font-size": "13px",
                            "gap": "5px",
                        },
                    )

                    cap_block = html.Div(
                        children=[
                            html.Div(
                                "Capabilities Info",
                                style={
                                    "font-weight": "600",
                                    "font-size": "13px",
                                    "margin-top": "10px",
                                    "border-bottom": "1px solid var(--border-color)",
                                    "padding-bottom": "3px",
                                    "margin-bottom": "5px",
                                },
                            ),
                            html.Div(
                                capabilities_str,
                                className="text-secondary",
                                style={"font-size": "12px"},
                            ),
                        ]
                    )

                    comp_details.append(
                        html.Div(
                            style={
                                "border": "1px solid var(--border-color)",
                                "border-radius": "var(--radius)",
                                "padding": "15px",
                                "margin-top": "10px",
                                "background-color": "rgba(0,0,0,0.005)",
                            },
                            children=[html.Div(comp_title), metadata_row, cap_block],
                        )
                    )

            if comp_details:
                comp_section = html.Div(comp_details)
            else:
                comp_section = html.Div(
                    "No components registered for this pipeline.",
                    className="text-secondary",
                    style={"font-size": "13px", "padding": "10px"},
                )

            pipeline_cards.append(
                html.Div(
                    className="card",
                    style={"margin-bottom": "20px", "padding": "20px"},
                    children=[
                        html.Div(
                            children=[
                                dcc.Link(
                                    name,
                                    href=f"/pipelines/{port}/{name}",
                                    style={
                                        "font-size": "18px",
                                        "font-weight": "700",
                                        "text-decoration": "none",
                                        "color": "var(--accent-color)",
                                    },
                                ),
                                html.Span(
                                    "Executing"
                                    if pip.jobid
                                    else ("Ready" if pip.ready else "Not Ready"),
                                    className="badge badge-primary"
                                    if pip.jobid
                                    else (
                                        "badge badge-success"
                                        if pip.ready
                                        else "badge badge-warning"
                                    ),
                                    style={"margin-left": "15px"},
                                ),
                            ],
                            style={
                                "display": "flex",
                                "align-items": "center",
                                "margin-bottom": "15px",
                            },
                        ),
                        html.Div(
                            children=[
                                html.Div(
                                    [
                                        html.Strong("Active Job ID: "),
                                        str(
                                            pip.jobid if pip.jobid is not None else "-"
                                        ),
                                    ],
                                    style={"margin-right": "30px"},
                                ),
                                html.Div(
                                    [
                                        html.Strong("Sample ID: "),
                                        str(
                                            pip.sampleid
                                            if pip.sampleid is not None
                                            else "-"
                                        ),
                                    ]
                                ),
                            ],
                            style={
                                "display": "flex",
                                "font-size": "14px",
                                "margin-bottom": "15px",
                                "color": "var(--text-secondary)",
                            },
                        ),
                        html.Div(
                            [
                                html.Div(
                                    "Components Info",
                                    style={
                                        "font-weight": "600",
                                        "font-size": "14px",
                                        "margin-bottom": "8px",
                                    },
                                ),
                                comp_section,
                            ]
                        ),
                    ],
                )
            )
        return html.Div(pipeline_cards, className="card-grid")
    except Exception as e:
        logger.warning("Exception during update_pipelines:", exc_info=e)
        return html.Div(
            f"Error loading pipelines: {e!s}",
            className="text-secondary",
            style={"padding": "20px"},
        )
