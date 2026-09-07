import logging
from typing import Any

import dash
from dash import Input, Output, State, callback, dcc, html
from dash_svg.Svg import Svg
from tomato import passata, tomato

from marinara import plotting
from marinara.icons import get_icon
from marinara.utils import TOUT, clean_value, get_field

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


def create_kpi_card(title: str, id: str, value: str, icon: Svg) -> html.Div:
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
def update_dashboard_stats(
    n_clicks: int,
    port: int,
    current_selector_value: str | None,
) -> tuple[str, str, str, str, list[dict[str, Any]], str | None, html.Div]:
    try:
        from tomato import ketchup

        ret = tomato.status(stgrp="tomato", port=port, timeout=TOUT)
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

        pips = ret.data.devicefile.pipelines
        pipret = tomato.status(stgrp="pipelines", port=port, timeout=TOUT)
        pips_count = len(pips)
        devs_count = len(ret.data.devicefile.devices)
        drvs_count = len(ret.data.devicefile.drivers)
        cmps = ret.data.devicefile.components
        cmps_count = len(cmps)

        selector_options = [{"label": k, "value": k} for k in pips]

        default_val = current_selector_value
        if not default_val and pips.keys():
            default_val = next(iter(pips.keys()))

        # Resolve active job users
        jobs_ret = ketchup.status(daemon=ret.data, jobids=[])
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

        for pip_name in pips:
            pstate = pipret.data.get(pip_name, {}) if pipret.success else {}
            pip_jobid = pstate.get("jobid")
            pip_ready = pstate.get("ready", False)
            pip_sampleid = pstate.get("sampleid")
            if pip_jobid:
                status_badge = html.Span(
                    "Executing Job", className="badge badge-primary"
                )
            elif pip_ready:
                status_badge = html.Span(
                    "Ready / Idle", className="badge badge-success"
                )
            else:
                status_badge = html.Span("Not Ready", className="badge badge-warning")

            job_link = (
                dcc.Link(
                    f"Job #{pip_jobid}",
                    href="/jobs",
                    style={"font-weight": "600", "color": "var(--accent-color)"},
                )
                if pip_jobid
                else "-"
            )
            sample_name = pip_sampleid or "-"
            owner_name = jobs_map.get(pip_jobid, "N/A") if pip_jobid else "-"

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
        logger.warning("Exception during update_dashboard_stats:", exc_info=e)
        return (
            "0",
            "0",
            "0",
            "0",
            [],
            None,
            html.Div(f"Error loading assignments: {e!s}", className="text-secondary"),
        )


@callback(
    Output("dash-parameters-list", "children"),
    Output("dash-live-graph", "figure"),
    Output("dash-plot-data-store", "data"),
    Input("dash-graph-interval", "n_intervals"),
    Input("dash-plot-device-selector", "value"),
    Input("app-theme-store", "data"),
    State("tomato-port", "data"),
    State("dash-plot-data-store", "data"),
    State("dash-live-graph", "figure"),
)
def update_dashboard_live_view(
    n_intervals: int,
    selected_pip: str | None,
    theme: str,
    port: int,
    historical_data: dict,
    prev_figure: dict | None,
) -> tuple[html.Div, dict | dash.Patch, dict]:
    if not selected_pip:
        return (
            html.Div(
                "Select a pipeline to view parameters.", className="text-secondary"
            ),
            plotting.empty_figure("Select a pipeline above to view live plot", theme),
            {},
        )

    try:
        ret = tomato.status(stgrp="tomato", port=port, timeout=TOUT)
        if not ret.success or not ret.data:
            raise RuntimeError("Daemon offline")
        pips = ret.data.devicefile.pipelines
        pip = pips.get(selected_pip)
    except Exception as e:
        logger.warning("Exception during update_dashboard_live_view:", exc_info=e)
        return (
            html.Div("Parameters temporarily unavailable.", className="text-secondary"),
            plotting.empty_figure("Offline or loading...", theme),
            {},
        )

    if not pip:
        return (
            html.Div("Pipeline parameters not found.", className="text-secondary"),
            plotting.empty_figure("Pipeline not found", theme),
            {},
        )

    if not historical_data or historical_data.get("pip") != selected_pip:
        historical_data = {"pip": selected_pip, "components": {}}
    historical_data.setdefault("components", {})

    # 1. Fetch attributes/parameters for each component in the pipeline
    param_items = []
    # pip.components maps role name to real component name, e.g. 'counter' to 'example_counter:(addr,1)'.
    # We need the real component names (the values), not the role names (the keys). Used again further below.
    for cname in pip.components.values():
        try:
            attrs_ret = passata.attrs(port=port, name=cname, timeout=TOUT)
            attrs_meta = attrs_ret.data if attrs_ret.success else {}

            vals_ret = passata.get_attrs(
                port=port, name=cname, attrs=list(attrs_meta), timeout=TOUT
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
                    unit = get_field(meta, "units", "")
                    unit_str = f" {unit}" if unit else ""
                    param_items.append(
                        html.Div(
                            className="param-item",
                            children=[
                                html.Span(f"{k}:", className="param-item-name"),
                                html.Span(
                                    f"{clean_value(v)}{unit_str}",
                                    className="param-item-val",
                                ),
                            ],
                        )
                    )
        except Exception as e:
            logger.warning(
                f"Failed to fetch parameters for component {cname} of pipeline {selected_pip}: {e}",
                exc_info=e,
            )

    params_list = html.Div(param_items, className="params-list-container")

    # 2. Fetch live data for plotting for each component in the pipeline, kept
    # in the same per-component "component store" shape as component.py's
    # component-data-store (capped at 50 rows rather than 500, since this is a
    # compact multi-component overview rather than a detailed single-component
    # page).
    traces = []
    for cname in pip.components.values():
        try:
            data_ret = passata.get_last_data(port=port, name=cname, timeout=TOUT)
            if data_ret.success and data_ret.data:
                comp_ds = plotting.merge_and_cap(
                    historical_data["components"].get(cname), data_ret.data, cap=50
                )
                historical_data["components"][cname] = comp_ds
            else:
                # Transient fetch failure: keep plotting this component's last
                # known data instead of dropping its trace for the tick, same
                # as pipeline.py's components_update_data_display does for
                # its own per-component polling.
                comp_ds = historical_data["components"].get(cname)
            if not comp_ds:
                continue
            formatted_x, _ = plotting.format_timeseries_x(
                comp_ds["coords"]["uts"]["data"], compact=True
            )
            keys = list(comp_ds["data_vars"].keys())
            traces.extend(
                plotting.build_traces(comp_ds, keys, formatted_x, prefix=cname)
            )
        except Exception as e:
            logger.warning(
                f"Failed to fetch live data for component {cname} of pipeline {selected_pip}: {e}",
                exc_info=e,
            )

    layout = plotting.build_layout(theme, margin={"t": 15, "b": 90, "l": 50, "r": 15})
    figure = plotting.patch_or_redraw(prev_figure, traces, layout)

    # historical_data's per-component datasets already come out of
    # merge_and_cap clean (JSON-safe) - no need to walk the whole structure
    # again here.
    return params_list, figure, historical_data


def layout(**_) -> list[html.Div]:
    return [dashboard_layout]
