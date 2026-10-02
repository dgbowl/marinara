import logging
from typing import Any

import dash
from dash import ALL, MATCH, Input, Output, State, callback, dcc, html
from tomato import passata, tomato

from marinara import callbacks, utils
from marinara.utils import TOUT

logger = logging.getLogger(__name__)
dash.register_page(__name__, path_template="/pipelines/<port>/<name>")


def layout(port: int, name: str, **_) -> list[html.Div | dcc.Store]:
    header = utils.create_header("pipeline", name)

    cfg_ret = tomato.status(port=port, stgrp="tomato", timeout=TOUT)
    if not cfg_ret.success or cfg_ret.data is None:
        return [html.Div("Failed to contact tomato daemon.", className="card")]
    elif name in cfg_ret.data.devicefile.pipelines:
        devicefile = cfg_ret.data.devicefile
        pip_components = devicefile.pipelines[name].components
    else:
        pip_components = {}

    pip_ret = tomato.status(port=port, stgrp="pipelines", timeout=TOUT)
    if not pip_ret.success or pip_ret.data is None or name not in pip_ret.data:
        return [html.Div("Failed to load pipeline.", className="card")]
    else:
        pip = pip_ret.data[name]

    stores = html.Div(
        children=[
            dcc.Store(id="pipeline-name", data=name),
            dcc.Store(id="pipeline-params", data=pip),
        ]
    )

    jobid = html.Div(
        children=[
            html.Span(
                "Job ID:",
                style={
                    "font-weight": "600",
                    "margin-right": "12px",
                    "font-size": "14px",
                    "flex-shrink": "0",
                },
            ),
            dcc.Input(
                id="jobid-input",
                type="number",
                value=pip["jobid"],
                disabled=True,
                className="top-card-input",
                style={"width": "100%", "height": "36px"},
            ),
        ],
        style={
            "display": "flex",
            "align-items": "center",
            "flex": "1 1 auto",
            "min-width": "100px",
            "max-width": "180px",
        },
    )

    sampleid = html.Div(
        children=[
            html.Span(
                "Sample ID:",
                style={
                    "font-weight": "600",
                    "margin-right": "12px",
                    "font-size": "14px",
                    "flex-shrink": "0",
                },
            ),
            dcc.Input(
                id="sampleid-input",
                type="text",
                value=pip.get("sampleid", ""),
                debounce=True,
                className="top-card-input",
                style={"width": "100%", "height": "36px"},
            ),
        ],
        style={
            "display": "flex",
            "align-items": "center",
            "flex": "1.5 1 auto",
            "min-width": "150px",
            "max-width": "260px",
        },
    )

    ready = html.Div(
        children=[
            html.Span(
                "Pipeline Status:",
                style={
                    "font-weight": "600",
                    "margin-right": "12px",
                    "font-size": "14px",
                    "flex-shrink": "0",
                },
            ),
            dcc.Checklist(
                options=[{"label": " Ready", "value": "ready"}],
                value=["ready"] if pip.get("ready", False) else [],
                id="ready-input",
                style={
                    "display": "inline-block",
                    "font-size": "14px",
                    "font-weight": "500",
                    "flex-shrink": "0",
                },
            ),
        ],
        style={"display": "flex", "align-items": "center", "flex-shrink": "0"},
    )

    cmp_ret = tomato.status(port=port, stgrp="components", timeout=TOUT)
    if not cmp_ret.success or cmp_ret.data is None:
        return [html.Div("Failed to load pipeline components.", className="card")]

    components = []
    for role, cname in pip_components.items():
        cmp = cmp_ret.data[cname]
        datastore = dcc.Store(id={"type": "data-store", "index": cname}, data={})

        status_ret = passata.status(port=port, name=cname, timeout=TOUT)
        if status_ret.success and status_ret.data is not None:
            running = utils.is_component_running(status_ret.data)
        else:
            running = False
        statusstore = dcc.Store(
            id={"type": "status-store", "index": cname}, data=running
        )

        attrs_ret = passata.attrs(port=port, name=cname, timeout=TOUT)
        if attrs_ret.success and attrs_ret.data is not None:
            attrs = attrs_ret.data
        else:
            attrs = {}
        avals = utils.get_attrs_vals(port=port, name=cname, attrs=list(attrs))

        div_info = html.Div(
            children=[
                html.H4(f"Component: {cname}", style={"margin": "0 0 5px 0"}),
                html.Div(
                    f"Role: {role} | Address: {cmp['address']!r} "
                    + f"| Channel: {cmp['channel']!r}",
                    className="text-secondary",
                    style={"font-size": "12px"},
                ),
                datastore,
                statusstore,
            ],
            className="block",
            style={
                "border-bottom": "1px solid var(--border-color)",
                "padding-bottom": "8px",
                "margin-bottom": "10px",
            },
        )

        badge_class = "badge badge-success" if running else "badge badge-secondary"
        badge_text = "RUNNING" if running else "STOPPED"
        badge = html.Span(
            badge_text,
            id={
                "type": "badge",
                "index": f"{cname}",
            },
            className=badge_class,
        )

        div_status = html.Div(
            children=[
                html.Span("Status: ", style={"font-weight": "500"}),
                badge,
            ],
            className="block",
            style={"margin-bottom": "12px"},
        )

        # Build attribute row layout
        attr_rows = utils.build_attr_rows(attrs, avals, cname)
        div_attrs = html.Div(
            children=attr_rows,
            className="component-attrs block",
        )

        div_data_ch = [
            html.Div(
                "Live Data:",
                style={
                    "font-weight": "600",
                    "margin-bottom": "8px",
                    "font-size": "13px",
                },
            )
        ]

        div_data = html.Div(
            children=div_data_ch,
            className="component-data block",
            id={"type": "data-container", "index": cname},
        )

        components.append(
            html.Div(
                id=f"component-{cname}",
                children=[
                    div_info,
                    div_status,
                    html.Div(
                        children=[div_attrs, div_data],
                        className="pipeline-params-data-grid",
                    ),
                ],
                className="card",
                style={"margin-bottom": "0px"},  # Managed by grid gap
            )
        )

    layout_children = [
        header,
        html.Div(
            children=[ready, jobid, sampleid],
            className="card",
            style={
                "display": "flex",
                "flex-direction": "row",
                "flex-wrap": "nowrap",
                "align-items": "center",
                "gap": "30px",
                "background-color": "var(--card-bg)",
                "border": "1px solid var(--border-color)",
                "padding": "15px 25px",
                "margin-bottom": "25px",
                "border-radius": "var(--radius)",
                "overflow": "hidden",
            },
        ),
        html.Div(children=components, className="pipeline-component-grid"),
        html.Div(children=stores),
    ]
    return layout_children


callbacks.periodic_data_store_update()
callbacks.periodic_attr_val_update()
callbacks.attr_display_val_update()
callbacks.periodic_status_store_update()


@callback(
    Output({"type": "data-container", "index": MATCH}, "children"),
    Input({"type": "data-store", "index": MATCH}, "data"),
    Input({"type": "data-store", "index": MATCH}, "id"),
    State({"type": "attr-param", "index": ALL}, "data"),
    State({"type": "attr-param", "index": ALL}, "id"),
    State({"type": "data-container", "index": MATCH}, "children"),
    prevent_initial_call=True,
)
def populate_data_container(
    ds: dict,
    id: dict,
    adicts: dict,
    aids: dict,
    old_children: list,
) -> list[html.Div] | dash.NoUpdate:
    cname = id["index"]
    attrs = {}
    for aid, attr in zip(aids, adicts):
        _, aname = aid["index"].split("/")
        attrs[aname] = attr

    div_data_ch = [old_children[0]]
    for key in ds["data_vars"]:
        if key in attrs and attrs[key]["status"] is False:
            continue
        units = ds["data_vars"][key].get("attrs", {}).get("units", "")
        units_str = utils.get_unit_str(units)
        div_data_ch.append(
            html.Div(
                children=[
                    html.Div(f"{key}:", className="attr-label"),
                    dcc.Input(
                        id={
                            "type": "data-val",
                            "index": f"{cname}/{key}",
                        },
                        disabled=True,
                        value=None,
                        className="attr-control",
                        style={"width": "200px"},
                    ),
                    html.Div(style={"width": "66px", "flex-shrink": "0"}),
                    html.Span(f" {units_str}", className="attr-unit"),
                ],
                id={"type": "component-data-key", "index": f"{cname}/{key}"},
                className="attr-row",
            )
        )
    if len(old_children) == len(div_data_ch):
        return dash.no_update
    return div_data_ch


callbacks.attr_apply_btn_update()
callbacks.attr_input_action_update_value()
callbacks.attr_input_disable_status()
callbacks.badge_update()


@callback(
    Output("pipeline-params", "data", allow_duplicate=True),
    Input("ready-input", "value"),
    State("tomato-port", "data"),
    State("pipeline-name", "data"),
    prevent_initial_call=True,
)
def pipeline_params_interaction_ready(
    values: list[str],
    port: int,
    name: str,
) -> list[str] | dash.NoUpdate:
    if "ready" in values:
        tomato.pipeline_ready(port=port, pipeline=name, timeout=TOUT)
    pip_ret = tomato.status(port=port, stgrp="pipelines", timeout=TOUT)
    assert pip_ret is not None
    assert pip_ret.data is not None
    return pip_ret.data[name]


@callback(
    Output("pipeline-params", "data", allow_duplicate=True),
    Input("sampleid-input", "value"),
    State("tomato-port", "data"),
    State("pipeline-name", "data"),
    prevent_initial_call=True,
)
def pipeline_params_interaction_sampleid(
    sampleid: str | None,
    port: int,
    name: str,
) -> None:
    ret = tomato.pipeline_eject(port=port, pipeline=name, timeout=TOUT)
    assert ret.success
    if sampleid is not None:
        ret = tomato.pipeline_load(
            port=port, pipeline=name, sampleid=sampleid, timeout=TOUT
        )
        assert ret.success
    pip_ret = tomato.status(port=port, stgrp="pipelines", timeout=TOUT)
    assert pip_ret.success
    assert pip_ret.data is not None
    return pip_ret.data[name]


@callback(
    Output("pipeline-params", "data", allow_duplicate=True),
    Input("interval", "n_intervals"),
    State("tomato-port", "data"),
    State("pipeline-name", "data"),
    State("pipeline-params", "data"),
    prevent_initial_call=True,
)
def periodic_pipeline_params_update(
    _: int,
    port: int,
    name: str,
    odata: dict,
) -> dict[str, Any] | dash.NoUpdate:
    pip_ret = tomato.status(port=port, stgrp="pipelines", timeout=TOUT)
    assert pip_ret is not None
    assert pip_ret.data is not None
    if odata == pip_ret.data[name]:
        return dash.no_update
    else:
        return pip_ret.data[name]


@callback(
    Output("ready-input", "value", allow_duplicate=True),
    Output("sampleid-input", "value", allow_duplicate=True),
    Output("jobid-input", "value", allow_duplicate=True),
    Input("pipeline-params", "data"),
    State("ready-input", "value"),
    State("sampleid-input", "value"),
    State("jobid-input", "value"),
    prevent_initial_call=True,
)
def pipeline_params_update_display(
    data: dict | None,
    ready: list[str],
    sampleid: str | None,
    jobid: int,
) -> tuple[Any | dash.NoUpdate, Any | dash.NoUpdate, Any | dash.NoUpdate]:
    if data is not None:
        r_new = ["ready"] if data["ready"] else []
        r_val = r_new if r_new != ready else dash.no_update
        s_val = data["sampleid"] if data["sampleid"] != sampleid else dash.no_update
        j_val = data["jobid"] if data["jobid"] != jobid else dash.no_update
        return r_val, s_val, j_val
    else:
        return dash.no_update, dash.no_update, dash.no_update


@callback(
    Output({"type": "data-val", "index": ALL}, "value"),
    Input({"type": "data-store", "index": MATCH}, "data"),
    Input({"type": "data-store", "index": MATCH}, "id"),
    State({"type": "data-val", "index": ALL}, "value"),
    State({"type": "data-val", "index": ALL}, "id"),
    prevent_initial_call=True,
)
def live_data_update_display(
    cdata: dict,
    cid: dict,
    vals: Any,
    vids: dict,
) -> list[Any | dash.NoUpdate]:
    nvals: list[Any | dash.NoUpdate] = [dash.no_update for v in vals]
    cname = cid["index"]
    for vi, vid in enumerate(vids):
        vcname, vattr = vid["index"].split("/")
        if vcname != cname:
            continue
        val = utils.pretty(cdata["data_vars"][vattr]["data"][-1])
        if val != vals[vi]:
            nvals[vi] = val
    return nvals
