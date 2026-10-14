import logging

import dash
from dash import ALL, Input, Output, State, callback, dcc, html
from tomato import ketchup, passata, tomato

from marinara import callbacks, plotting, utils
from marinara.icons import get_icon
from marinara.utils import TOUT

logger = logging.getLogger(__name__)
dash.register_page(__name__, path_template="/", title="Dashboard")


def layout():
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

    cards = []
    for title, obj in (
        ("Active Pipelines", "pipelines"),
        ("Connected Devices", "devices"),
        ("Running Drivers", "drivers"),
        ("Active Components", "components"),
    ):
        card = utils.create_kpi_card(
            title,
            f"kpi-{obj}",
            "N/A",
            get_icon(obj, size=32, stroke="var(--accent-color)", stroke_width=1.5),
        )
        cards.append(card)
    kpi_row = html.Div(className="kpi-row", children=cards)

    # Middle Grid
    graph_row = html.Div(
        className="dashboard-grid",
        children=[
            # Left Column: Parameters
            html.Div(
                className="grid-card",
                children=[
                    html.Div("Live Attributes", className="card-header"),
                    html.Div(
                        id="attrs-list",
                        children=[
                            html.Div(
                                "Select a pipeline to view its attrs.",
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
                                id="pipeline-selector",
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
                        id="live-graph",
                        # Seeded so Patch() has a figure to apply onto
                        figure=plotting.empty_figure(
                            "Select a pipeline above to view live plot", "light"
                        ),
                        style={"height": "450px"},
                        responsive=True,
                    ),
                ],
            ),
        ],
    )

    pipeline_row = html.Div(
        className="card",
        style={"margin-top": "20px"},
        children=[
            html.Div("Pipeline Info Table", className="card-header"),
            html.Div(
                id="pipeline-table",
                children="Loading pipeline info...",
                className="text-secondary",
                style={"padding": "20px"},
            ),
        ],
    )

    stores = html.Div(children=[], id="data-store-container")
    cmps = dcc.Store("component-names", data=[])
    return html.Div(
        className="dashboard-container",
        children=[header, kpi_row, graph_row, pipeline_row, stores, cmps],
    )


@callback(
    Output("kpi-pipelines", "children"),
    Output("kpi-devices", "children"),
    Output("kpi-drivers", "children"),
    Output("kpi-components", "children"),
    Output("pipeline-selector", "options"),
    Output("data-store-container", "children"),
    Input("tomato-status", "n_clicks"),
    Input("tomato-port", "data"),
)
def refresh_tomato_port(_: int, port: int):
    ret = tomato.status(port=port, timeout=1)
    if ret.success is False or ret.data is None:
        return "N/A", "N/A", "N/A", "N/A", [], []

    devicefile = ret.data.devicefile
    stores = []
    for name in devicefile.components:
        stores.append(dcc.Store(id={"type": "data-store", "index": name}, data={}))

    return (
        str(len(devicefile.pipelines)),
        str(len(devicefile.devices)),
        str(len(devicefile.drivers)),
        str(len(devicefile.components)),
        list(devicefile.pipelines),
        stores,
    )


@callback(
    Output("component-names", "data"),
    Input("pipeline-selector", "value"),
    State("component-names", "data"),
    State("tomato-port", "data"),
    prevent_initial_call=True,
)
def update_component_names(
    pname: str, old_cnames: list, port: int
) -> list[str] | dash.NoUpdate:
    ret = tomato.status(port=port, timeout=1)
    if ret.success is False or ret.data is None:
        return []

    pipeline = ret.data.devicefile.pipelines[pname]
    cnames = sorted(pipeline.components.values())
    if cnames == old_cnames:
        return dash.no_update
    else:
        return cnames


@callback(
    Output("pipeline-table", "children"),
    Input("pipeline-selector", "options"),
    State("tomato-port", "data"),
)
def update_pipeline_table(pnames: list[str], port: int) -> html.Table | dash.NoUpdate:
    rows = [
        html.Tr(
            children=[
                html.Th("Pipeline"),
                html.Th("Status"),
                html.Th("Sample"),
                html.Th("Job ID"),
                html.Th("Job Owner"),
            ]
        )
    ]

    ret = tomato.status(port=port, timeout=TOUT)
    if ret.success is False or ret.data is None:
        return dash.no_update
    pip_ret = tomato.status(stgrp="pipelines", port=port, timeout=TOUT)
    if pip_ret.success is False or pip_ret.data is None:
        return dash.no_update
    for pname in pnames:
        pstate = pip_ret.data[pname]
        pip_jobid = pstate.get("jobid")
        pip_ready = pstate.get("ready", False)
        pip_sampleid = pstate.get("sampleid")
        if pip_jobid:
            status_badge = html.Span("Executing Job", className="badge badge-primary")
        elif pip_ready:
            status_badge = html.Span("Ready / Idle", className="badge badge-success")
        else:
            status_badge = html.Span("Not Ready", className="badge badge-warning")

        if pip_jobid:
            job_link = dcc.Link(
                f"Job #{pip_jobid}",
                href="/jobs",
                className="entity-link",
                style={"font-weight": "600"},
            )
            job_ret = ketchup.status(daemon=ret.data, jobids=[pip_jobid])
            if job_ret.success and job_ret.data is not None:
                job = job_ret.data[0]
                owner_name = job.payload.user.identifier
            else:
                owner_name = "N/A"
        else:
            job_link = "-"
            owner_name = "-"

        sample_name = pip_sampleid or "-"

        rows.append(
            html.Tr(
                children=[
                    html.Td(
                        dcc.Link(
                            pname,
                            href=f"/pipelines/{port}/{pname}",
                            className="entity-link",
                            style={"font-weight": "600"},
                        )
                    ),
                    html.Td(status_badge),
                    html.Td(sample_name),
                    html.Td(job_link),
                    html.Td(
                        owner_name,
                        style={"font-weight": "600" if owner_name != "-" else "normal"},
                    ),
                ]
            )
        )

    return html.Table(children=rows, className="stgrp")


@callback(
    Output("attrs-list", "children"),
    Input("component-names", "data"),
    State("tomato-port", "data"),
    prevent_initial_call=True,
)
def update_attrs_list(cnames: list[str], port: int):
    print(f"{cnames=}")
    children = []
    for cname in cnames:
        children.append(
            dcc.Link(
                cname,
                href=f"/components/{port}/{cname}",
                className="entity-link",
                style={
                    "display": "block",
                    "font-weight": "700",
                    "font-size": "14px",
                    "margin-top": "12px",
                    "margin-bottom": "6px",
                    "border-bottom": "1px solid var(--border-color)",
                    "padding-bottom": "2px",
                },
            )
        )
        attrs_ret = passata.attrs(port=port, name=cname, timeout=TOUT)
        if attrs_ret.success and attrs_ret.data is not None:
            attrs = attrs_ret.data
        else:
            attrs = {}
        avals = utils.get_attrs_vals(port=port, name=cname, attrs=list(attrs))
        attr_rows = utils.build_attr_rows(attrs, avals, cname, rw=False)
        children.append(html.Div(children=attr_rows))
    return children


callbacks.periodic_data_store_update()
callbacks.periodic_attr_val_update()
callbacks.attr_display_val_update()


# Layout only - traces are patched separately below
@callback(
    Output("live-graph", "figure", allow_duplicate=True),
    Input("component-names", "data"),
    Input("app-theme-store", "data"),
    prevent_initial_call="initial_duplicate",
)
def render_dashboard_graph_layout(
    cnames: list[str], theme: str
) -> dict | dash.Patch | dash.NoUpdate:
    if not cnames:
        return dash.no_update
    layout = plotting.build_layout(theme, margin={"t": 15, "b": 90, "l": 50, "r": 15})
    patch = dash.Patch()
    patch["layout"] = layout
    return patch


# Traces only - layout handled above
@callback(
    Output("live-graph", "figure", allow_duplicate=True),
    Input("component-names", "data"),
    Input({"type": "data-store", "index": ALL}, "data"),
    Input({"type": "data-store", "index": ALL}, "id"),
    State("live-graph", "figure"),
    prevent_initial_call="initial_duplicate",
)
def render_dashboard_graph_traces(
    cnames: list[str],
    all_datastores: list[dict],
    all_datastore_ids: list[dict],
    prev_figure: dict | None,
) -> dash.Patch:
    traces = []
    for id, ds in zip(all_datastore_ids, all_datastores):
        if id["index"] not in cnames:
            continue
        if ds == {}:
            continue
        status_map = {}  # component_status.get(cname, {})
        keys = [k for k in ds["data_vars"] if status_map.get(k, True)]
        traces.extend(
            plotting.build_traces(ds, "uts", keys, compact=True, prefix=id["index"])
        )
    return plotting.patch_traces(prev_figure, traces)
