import logging
import dash
from dash import Input, Output, State, callback, dcc, html
from marinara.graphing import (
    DEFAULT_MAX_POINTS,
    extract_telemetry_points,
    update_live_patch,
)
from marinara.icons import get_icon
from marinara.utils import (
    CTXT,
    PORT,
    TOUT,
    clean_value,
    ensure_drivers_registered,
    format_sigfig,
    kwargs,
)
from tomato import passata, tomato

logger = logging.getLogger(__name__)

dash.register_page(__name__, path_template="/", title="Marinara")


header = html.Div(
    className="theme-header",
    children=[
        html.Div(
            children=[
                html.H2(
                    "Experiment Tracking Dashboard",
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
)


def create_kpi_card(title, id, value, icon):
    return html.Div(
        className="kpi-card",
        children=[
            html.Div(
                className="kpi-details",
                children=[html.H4(title), html.H2(value, id=id)],
            ),
            html.Div(icon, className="kpi-icon"),
        ],
    )


dashboard_layout = html.Div(
    className="dashboard-container",
    children=[
        header,
        dcc.Store(id="dash-plot-data-store", data={}),
        # KPI Cards Row
        html.Div(
            className="kpi-row",
            children=[
                create_kpi_card(
                    "Active Pipelines",
                    "kpi-pipelines",
                    "0",
                    get_icon(
                        "pipelines",
                        size=32,
                        stroke="var(--accent-color)",
                        stroke_width=1.5,
                    ),
                ),
                create_kpi_card(
                    "Connected Devices",
                    "kpi-devices",
                    "0",
                    get_icon(
                        "devices",
                        size=32,
                        stroke="var(--accent-color)",
                        stroke_width=1.5,
                    ),
                ),
                create_kpi_card(
                    "Running Drivers",
                    "kpi-drivers",
                    "0",
                    get_icon(
                        "drivers",
                        size=32,
                        stroke="var(--accent-color)",
                        stroke_width=1.5,
                    ),
                ),
                create_kpi_card(
                    "Active Components",
                    "kpi-components",
                    "0",
                    get_icon(
                        "components",
                        size=32,
                        stroke="var(--accent-color)",
                        stroke_width=1.5,
                    ),
                ),
            ],
        ),
        # Middle Grid
        html.Div(
            className="dashboard-grid",
            children=[
                # Left Column: Parameters
                html.Div(
                    className="grid-card",
                    children=[
                        html.Div("Live Parameters", className="card-header"),
                        html.Div(
                            id="dash-parameters-list",
                            children=[
                                html.Div(
                                    "Select a pipeline to view parameters.",
                                    className="text-secondary",
                                )
                            ],
                        ),
                    ],
                ),
                # Center Column: Live Graph
                html.Div(
                    className="grid-card",
                    children=[
                        html.Div(
                            children=[
                                html.Span(
                                    "Live Pipeline Plot",
                                    className="card-header",
                                    style={
                                        "margin-bottom": 0,
                                        "border-bottom": "none",
                                        "padding-bottom": 0,
                                    },
                                ),
                                dcc.Dropdown(
                                    id="dash-plot-pipeline-selector",
                                    options=[],
                                    placeholder="Select Pipeline to Plot",
                                    clearable=False,
                                    style={"width": "220px", "margin-left": "auto"},
                                ),
                            ],
                            style={
                                "display": "flex",
                                "align-items": "center",
                                "margin-bottom": "15px",
                                "border-bottom": "1px solid var(--border-color)",
                                "padding-bottom": "10px",
                            },
                        ),
                        dcc.Graph(
                            id="dash-live-graph",
                            style={"height": "450px"},
                            responsive=True,
                        ),
                        dcc.Interval(id="dash-graph-interval", interval=2000),
                    ],
                ),
            ],
        ),
        # Bottom Row: Active Pipelines & Assignments
        html.Div(
            className="card",
            style={"margin-top": "20px"},
            children=[
                html.Div(
                    "Active Pipelines & User Assignments", className="card-header"
                ),
                html.Div(
                    id="dash-pipelines-assignments-table",
                    children="Loading assignments...",
                    className="text-secondary",
                    style={"padding": "20px"},
                ),
            ],
        ),
    ],
)


@callback(
    Output("kpi-pipelines", "children"),
    Output("kpi-devices", "children"),
    Output("kpi-drivers", "children"),
    Output("kpi-components", "children"),
    Output("dash-plot-pipeline-selector", "options"),
    Output("dash-plot-pipeline-selector", "value"),
    Output("dash-pipelines-assignments-table", "children"),
    Input("tomato-status", "n_clicks"),
    State("tomato-port", "data"),
    State("dash-plot-pipeline-selector", "value"),
)
def update_dashboard_stats(n_clicks, port, current_selector_value):
    try:
        from tomato import ketchup

        ret = tomato.status(stgrp="tomato", port=port, **kwargs)
        if not ret.success:
            return (
                "0",
                "0",
                "0",
                "0",
                [],
                None,
                html.Div("Daemon offline.", className="text-secondary"),
            )

        pips = ret.data.pips
        pips_count = len(pips)
        devs_count = len(ret.data.devs)
        drvs_count = len(ret.data.drvs)
        cmps = ret.data.cmps
        cmps_count = len(cmps)

        selector_options = [{"label": k, "value": k} for k in pips.keys()]

        default_val = current_selector_value
        if not default_val and pips.keys():
            default_val = list(pips.keys())[0]

        # Resolve active job users
        jobs_ret = ketchup.status(port=port, context=CTXT, verbosity=20, jobids=[])
        jobs_map = {}
        if jobs_ret.success:
            for job in jobs_ret.data:
                user_id = "N/A"
                if (
                    hasattr(job, "payload")
                    and hasattr(job.payload, "user")
                    and job.payload.user
                ):
                    user_id = job.payload.user.identifier
                jobs_map[job.id] = user_id

        # Build Assignments Table
        rows = [
            html.Tr(
                children=[
                    html.Th("Pipeline"),
                    html.Th("Status"),
                    html.Th("Active Job ID"),
                    html.Th("Sample"),
                    html.Th("Assigned User / Owner"),
                ]
            )
        ]

        for pip_name, pip in pips.items():
            if pip.jobid:
                status_badge = html.Span(
                    "Executing Job", className="badge badge-primary"
                )
            elif pip.ready:
                status_badge = html.Span(
                    "Ready / Idle", className="badge badge-success"
                )
            else:
                status_badge = html.Span(
                    "Not Ready", className="badge badge-warning"
                )

            job_link = (
                dcc.Link(
                    f"Job #{pip.jobid}",
                    href="/jobs",
                    style={"font-weight": "600", "color": "var(--accent-color)"},
                )
                if pip.jobid
                else "-"
            )
            sample_name = pip.sampleid or "-"
            owner_name = jobs_map.get(pip.jobid, "N/A") if pip.jobid else "-"

            rows.append(
                html.Tr(
                    children=[
                        html.Td(
                            dcc.Link(
                                pip_name,
                                href=f"/pipelines/{port}/{pip_name}",
                                style={
                                    "font-weight": "600",
                                    "color": "var(--accent-color)",
                                    "text-decoration": "none",
                                },
                            )
                        ),
                        html.Td(status_badge),
                        html.Td(job_link),
                        html.Td(sample_name),
                        html.Td(
                            owner_name,
                            style={
                                "font-weight": "600" if owner_name != "-" else "normal"
                            },
                        ),
                    ]
                )
            )

        table = html.Table(children=rows, className="stgrp")
        return (
            str(pips_count),
            str(devs_count),
            str(drvs_count),
            str(cmps_count),
            selector_options,
            default_val,
            table,
        )
    except Exception as e:
        logger.error("Failed to update dashboard stats: %s", e)
        return (
            "0",
            "0",
            "0",
            "0",
            [],
            None,
            html.Div(
                f"Error loading assignments: {str(e)}", className="text-secondary"
            ),
        )


@callback(
    Output("dash-parameters-list", "children"),
    Output("dash-live-graph", "figure"),
    Output("dash-plot-data-store", "data"),
    Input("dash-graph-interval", "n_intervals"),
    Input("dash-plot-pipeline-selector", "value"),
    State("tomato-port", "data"),
    State("dash-plot-data-store", "data"),
    State("app-theme-store", "data"),
)
def update_dashboard_live_view(
    n_intervals, selected_pip, port, historical_data, theme
):
    if not selected_pip:
        empty_fig = {
            "layout": {
                "autosize": True,
                "xaxis": {"visible": False},
                "yaxis": {"visible": False},
                "annotations": [
                    {
                        "text": "Select a pipeline above to view live plot",
                        "xref": "paper",
                        "yref": "paper",
                        "showarrow": False,
                        "font": {"size": 16, "color": "gray"},
                    }
                ],
                "paper_bgcolor": "rgba(0,0,0,0)",
                "plot_bgcolor": "rgba(0,0,0,0)",
                "template": "plotly_dark" if theme == "dark" else "plotly",
            }
        }
        return (
            html.Div(
                "Select a pipeline to view parameters.", className="text-secondary"
            ),
            empty_fig,
            {},
        )

    try:
        ret = tomato.status(stgrp="tomato", port=port, **kwargs)
        if not ret.success or not ret.data:
            raise Exception("Daemon offline")
        ensure_drivers_registered(ret.data)
        pips = ret.data.pips
        pip = pips.get(selected_pip)
    except Exception as e:
        logger.warning("Daemon offline or status query failed: %s", e)
        empty_fig = {
            "layout": {
                "autosize": True,
                "xaxis": {"visible": False},
                "yaxis": {"visible": False},
                "annotations": [
                    {
                        "text": "Offline or loading...",
                        "xref": "paper",
                        "yref": "paper",
                        "showarrow": False,
                        "font": {"size": 14, "color": "gray"},
                    }
                ],
                "paper_bgcolor": "rgba(0,0,0,0)",
                "plot_bgcolor": "rgba(0,0,0,0)",
                "template": "plotly_dark" if theme == "dark" else "plotly",
            }
        }
        return (
            html.Div(
                "Parameters temporarily unavailable.", className="text-secondary"
            ),
            empty_fig,
            {},
        )

    if not pip:
        empty_fig = {
            "layout": {
                "autosize": True,
                "xaxis": {"visible": False},
                "yaxis": {"visible": False},
                "annotations": [
                    {
                        "text": "Pipeline not found",
                        "xref": "paper",
                        "yref": "paper",
                        "showarrow": False,
                        "font": {"size": 14, "color": "gray"},
                    }
                ],
                "paper_bgcolor": "rgba(0,0,0,0)",
                "plot_bgcolor": "rgba(0,0,0,0)",
                "template": "plotly_dark" if theme == "dark" else "plotly",
            }
        }
        return (
            html.Div("Pipeline parameters not found.", className="text-secondary"),
            empty_fig,
            {},
        )

    if not historical_data or historical_data.get("pip") != selected_pip:
        historical_data = {"pip": selected_pip, "traces": {}}

    # 1. Fetch attributes/parameters for each component in the pipeline
    param_items = []
    for cname in pip.components:
        try:
            attrs_ret = passata.attrs(**kwargs, port=port, name=cname)
            attrs_meta = attrs_ret.data if attrs_ret.success else {}

            vals_ret = passata.get_attrs(
                **kwargs, port=port, name=cname, attrs=list(attrs_meta.keys())
            )
            vals = vals_ret.data if vals_ret.success else {}

            if vals:
                param_items.append(
                    html.Div(
                        cname,
                        style={
                            "font-weight": "700",
                            "font-size": "14px",
                            "margin-top": "12px",
                            "margin-bottom": "6px",
                            "border-bottom": "1px solid var(--border-color)",
                            "padding-bottom": "2px",
                            "color": "var(--accent-color)",
                        },
                    )
                )
                for k, v in vals.items():
                    meta = attrs_meta.get(k, {})
                    unit = (
                        meta.get("units", "")
                        if isinstance(meta, dict)
                        else getattr(meta, "units", "")
                    )
                    unit_str = f" {unit}" if unit else ""
                    param_items.append(
                        html.Div(
                            className="param-item",
                            children=[
                                html.Span(f"{k}:", className="param-item-name"),
                                html.Span(
                                    f"{format_sigfig(clean_value(v))}{unit_str}",
                                    className="param-item-val",
                                ),
                            ],
                        )
                    )
        except Exception as e:
            logger.warning(
                f"Failed to fetch parameters for component {cname} of pipeline {selected_pip}: {e}"
            )

    params_list = html.Div(param_items, className="params-list-container")

    # 2. Fetch live data for plotting for each component in the pipeline
    new_points = {}
    for cname in pip.components:
        try:
            data_ret = passata.get_last_data(**kwargs, port=port, name=cname)
            if data_ret.success and data_ret.data:
                ds = data_ret.data
                if hasattr(ds, "isel") and hasattr(ds, "sizes") and "uts" in ds.sizes:
                    ds = ds.isel(uts=slice(-50, None))
                comp_points = extract_telemetry_points(ds.to_dict(), cname)
                new_points.update(comp_points)
        except Exception as e:
            logger.warning(
                f"Failed to fetch live data for component {cname} of pipeline {selected_pip}: {e}"
            )

    fig_or_patch, historical_data = update_live_patch(
        current_store=historical_data,
        new_points=new_points,
        theme=theme,
        max_points=DEFAULT_MAX_POINTS,
    )

    return params_list, fig_or_patch, historical_data


def layout(**_):
    return [dashboard_layout]
