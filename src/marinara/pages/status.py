import dash
from dash import html, dcc, callback, Output, Input, State
from tomato import passata, tomato
import zmq
from datetime import datetime, timezone
from marinara.icons import get_icon
from marinara.utils import get_field, clean_value, clean_dict_values

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
                                    placeholder="Select Component to Plot",
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
                            style={"height": "320px"},
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

        selector_options = [{"label": k, "value": k} for k in cmps.keys()]

        default_val = current_selector_value
        if not default_val and cmps.keys():
            default_val = list(cmps.keys())[0]

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
            status_badge = (
                html.Span("Ready / Idle", className="badge badge-success")
                if pip.ready
                else html.Span("Offline / Busy", className="badge badge-warning")
            )
            if pip.jobid:
                status_badge = html.Span(
                    "Executing Job", className="badge badge-primary"
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
def update_dashboard_live_view(n_intervals, selected_cmp, port, historical_data, theme):
    if not selected_cmp:
        empty_fig = {
            "layout": {
                "autosize": True,
                "xaxis": {"visible": False},
                "yaxis": {"visible": False},
                "annotations": [
                    {
                        "text": "Select a component above to view live plot",
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
                "Select a component to view parameters.", className="text-secondary"
            ),
            empty_fig,
            {},
        )

    if not historical_data or historical_data.get("cmp") != selected_cmp:
        historical_data = {"cmp": selected_cmp, "x": [], "y_data": {}}
    try:
        # 1. Fetch attributes/parameters
        attrs_ret = passata.attrs(**kwargs, port=port, name=selected_cmp)
        attrs_meta = attrs_ret.data if attrs_ret.success else {}

        vals_ret = passata.get_attrs(
            **kwargs, port=port, name=selected_cmp, attrs=list(attrs_meta.keys())
        )
        vals = vals_ret.data if vals_ret.success else {}

        param_items = []
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
        params_list = html.Div(param_items, className="params-list-container")

        # 2. Fetch live data for plotting
        data_ret = passata.get_last_data(**kwargs, port=port, name=selected_cmp)
        if data_ret.success and data_ret.data:
            ds = data_ret.data.to_dict()
            uts_list = ds["coords"]["uts"]["data"]
            for t in uts_list:
                cleaned_t = clean_value(t)
                if cleaned_t not in historical_data["x"]:
                    historical_data["x"].append(cleaned_t)
                    if len(historical_data["x"]) > 50:
                        historical_data["x"].pop(0)

                    for var_name, var_info in ds["data_vars"].items():
                        raw_val = var_info["data"][-1]
                        # Check if raw_val is list-like
                        if isinstance(raw_val, (list, tuple)):
                            for i, sub_val in enumerate(raw_val):
                                sub_name = f"{var_name}[{i}]"
                                if sub_name not in historical_data["y_data"]:
                                    historical_data["y_data"][sub_name] = []
                                historical_data["y_data"][sub_name].append(
                                    clean_value(sub_val)
                                )
                                if len(historical_data["y_data"][sub_name]) > 50:
                                    historical_data["y_data"][sub_name].pop(0)
                        else:
                            if var_name not in historical_data["y_data"]:
                                historical_data["y_data"][var_name] = []
                            historical_data["y_data"][var_name].append(
                                clean_value(raw_val)
                            )
                            if len(historical_data["y_data"][var_name]) > 50:
                                historical_data["y_data"][var_name].pop(0)

        formatted_x = []
        for t in historical_data["x"]:
            try:
                formatted_x.append(
                    datetime.fromtimestamp(t, timezone.utc)
                    .astimezone()
                    .strftime("%H:%M:%S")
                )
            except Exception:
                formatted_x.append(str(t))

        traces = []
        for var_name, y_vals in historical_data["y_data"].items():
            traces.append(
                {
                    "x": formatted_x,
                    "y": y_vals,
                    "name": var_name,
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
                "margin": {"t": 10, "b": 30, "l": 40, "r": 10},
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
                "uirevision": True,
            },
        }

        return params_list, figure, clean_dict_values(historical_data)

    except Exception:
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
