import dash
from dash import html, dcc, callback, Output, Input, State
from tomato import passata, tomato
import zmq
import logging
from datetime import datetime, timezone
from marinara.icons import get_icon
from marinara.utils import get_field, clean_value, clean_dict_values

logger = logging.getLogger(__name__)

CTXT = zmq.Context()
TOUT = 1000
PORT = 1234
kwargs = dict(timeout=TOUT, context=CTXT)

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
                                    "Select a component to view parameters.",
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
                                    "Live Device Plot",
                                    className="card-header",
                                    style={
                                        "margin-bottom": 0,
                                        "border-bottom": "none",
                                        "padding-bottom": 0,
                                    },
                                ),
                                dcc.Dropdown(
                                    id="dash-plot-device-selector",
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
    Output("dash-plot-device-selector", "options"),
    Output("dash-plot-device-selector", "value"),
    Output("dash-pipelines-assignments-table", "children"),
    Input("tomato-status", "n_clicks"),
    State("tomato-port", "data"),
    State("dash-plot-device-selector", "value"),
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
    Input("dash-plot-device-selector", "value"),
    State("tomato-port", "data"),
    State("dash-plot-data-store", "data"),
    State("app-theme-store", "data"),
)
def update_dashboard_live_view(n_intervals, selected_pip, port, historical_data, theme):
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
        pips = ret.data.pips
        pip = pips.get(selected_pip)
    except Exception as e:
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
            html.Div("Parameters temporarily unavailable.", className="text-secondary"),
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
                            "color": "var(--accent-color)"
                        }
                    )
                )
                for k, v in vals.items():
                    meta = attrs_meta.get(k, {})
                    unit = get_field(meta, "units", "")
                    unit_str = f" {unit}" if unit else ""
                    param_items.append(
                        html.Div(
                            className="param-item",
                            children=[
                                html.Span(f"{k}:", className="param-item-name"),
                                html.Span(
                                    f"{clean_value(v)}{unit_str}", className="param-item-val"
                                ),
                            ],
                        )
                    )
        except Exception as e:
            logger.warning(f"Failed to fetch parameters for component {cname} of pipeline {selected_pip}: {e}")

    params_list = html.Div(param_items, className="params-list-container")

    # 2. Fetch live data for plotting for each component in the pipeline
    if "traces" not in historical_data:
        historical_data["traces"] = {}

    for cname in pip.components:
        try:
            data_ret = passata.get_last_data(**kwargs, port=port, name=cname)
            if data_ret.success and data_ret.data:
                ds = data_ret.data.to_dict()
                uts_list = ds["coords"]["uts"]["data"]
                
                for idx, t in enumerate(uts_list):
                    cleaned_t = clean_value(t)
                    
                    for var_name, var_info in ds["data_vars"].items():
                        raw_val = var_info["data"][idx]
                        
                        # Handle multi-dimensional variables
                        if isinstance(raw_val, (list, tuple)):
                            for i, sub_val in enumerate(raw_val):
                                trace_key = f"{cname}/{var_name}[{i}]"
                                if trace_key not in historical_data["traces"]:
                                    historical_data["traces"][trace_key] = {"x": [], "y": []}
                                
                                trace = historical_data["traces"][trace_key]
                                if cleaned_t not in trace["x"]:
                                    trace["x"].append(cleaned_t)
                                    trace["y"].append(clean_value(sub_val))
                                    if len(trace["x"]) > 50:
                                        trace["x"].pop(0)
                                        trace["y"].pop(0)
                        else:
                            trace_key = f"{cname}/{var_name}"
                            if trace_key not in historical_data["traces"]:
                                historical_data["traces"][trace_key] = {"x": [], "y": []}
                            
                            trace = historical_data["traces"][trace_key]
                            if cleaned_t not in trace["x"]:
                                trace["x"].append(cleaned_t)
                                trace["y"].append(clean_value(raw_val))
                                if len(trace["x"]) > 50:
                                    trace["x"].pop(0)
                                    trace["y"].pop(0)
        except Exception as e:
            logger.warning(f"Failed to fetch live data for component {cname} of pipeline {selected_pip}: {e}")

    traces = []
    for trace_key, trace_data in historical_data["traces"].items():
        formatted_x = []
        for t in trace_data["x"]:
            try:
                formatted_x.append(
                    datetime.fromtimestamp(t, timezone.utc)
                    .astimezone()
                    .strftime("%H:%M:%S")
                )
            except Exception:
                formatted_x.append(str(t))
        
        traces.append(
            {
                "x": formatted_x,
                "y": trace_data["y"],
                "name": trace_key,
                "type": "scatter",
                "mode": "lines+markers",
            }
        )

    figure = {
        "data": traces,
        "layout": {
            "autosize": True,
            "template": "plotly_dark" if theme == "dark" else "plotly",
            "paper_bgcolor": "rgba(0,0,0,0)",
            "plot_bgcolor": "rgba(0,0,0,0)",
            "font": {"color": "#ffffff" if theme == "dark" else "#212529"},
            "margin": {"t": 15, "b": 90, "l": 50, "r": 15},
            "xaxis": {
                "gridcolor": "rgba(255,255,255,0.08)"
                if theme == "dark"
                else "rgba(0,0,0,0.08)",
            },
            "yaxis": {
                "gridcolor": "rgba(255,255,255,0.08)"
                if theme == "dark"
                else "rgba(0,0,0,0.08)",
            },
            "legend": {
                "orientation": "h",
                "x": 0.5,
                "y": -0.18,
                "xanchor": "center",
                "yanchor": "top",
            },
            "uirevision": True,
        },
    }

    return params_list, figure, clean_dict_values(historical_data)


def format_obj(obj, headers, attrs, otype, port):
    if not obj:
        return html.Div(
            "No registered elements found.",
            className="text-secondary",
            style={"text-align": "center", "padding": "20px"},
        )

    rows = [html.Tr(children=[html.Th(h) for h in headers])]
    for k, v in obj.items():
        row = [html.Td(str(v.get(i, ""))) for i in attrs]

        if otype in ["pipelines", "components"]:
            row[0].children = dcc.Link(
                row[0].children,
                href=f"/{otype}/{port}/{row[0].children}",
                style={
                    "font-weight": "600",
                    "text-decoration": "none",
                    "color": "var(--accent-color)",
                },
            )
        rows.append(html.Tr(children=row))
    return html.Table(children=rows, className="stgrp")


def layout(**_):
    return [dashboard_layout]
