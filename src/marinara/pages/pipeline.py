import logging
from typing import Any

import dash
import pint
from dash import ALL, MATCH, Input, Output, State, callback, dcc, html, set_props
from tomato import passata, tomato

from marinara.utils import (
    TOUT,
    format_constraint,
    get_attrs_vals,
    get_unit_str,
    is_component_running,
    pretty,
    update_datastore,
)

logger = logging.getLogger(__name__)


def create_header_div(port: int, name: str) -> html.Div:
    stores = html.Div(
        children=[
            dcc.Store(id="store-tomato-port", data=port),
            dcc.Store(id="store-pipeline-name", data=name),
            dcc.Store(id="store-pipeline-params", data=None),
            dcc.Store(id="store-pipeline-component-names", data=None),
            dcc.Store(id="store-pipeline-component-running", data=None),
            dcc.Store(id="store-pipeline-component-attrs-vals", data=None),
            dcc.Store(id="store-pipeline-component-attrs-units", data=None),
            dcc.Store(id="store-pipeline-component-attrs-rw", data=None),
            dcc.Interval(id="interval-pipeline-content", interval=2000),
        ],
        className="header-store",
    )

    header = html.Div(
        children=[
            html.Div(
                children=[
                    dcc.Link(
                        "← Back to Pipelines",
                        href="/pipelines",
                        className="btn inline-block",
                        style={
                            "margin-right": "20px",
                            "text-decoration": "none",
                            "background-color": "var(--accent-color)",
                            "color": "white",
                            "padding": "8px 16px",
                            "border-radius": "4px",
                        },
                    ),
                    html.H2(
                        f"Pipeline: {name}",
                        className="inline",
                        style={"margin": 0, "font-size": "22px"},
                    ),
                ],
                style={"display": "flex", "align-items": "center"},
            )
        ],
        className="theme-header",
    )

    return html.Div(
        children=[stores, header],
        className="header-wrapper",
    )


def object_from_attrs(cname, attr, params, value) -> dcc.Dropdown | dcc.Input:
    if params.options is not None:
        obj = dcc.Dropdown(
            id={
                "type": "component-attr-val",
                "index": f"{cname}/{attr}",
            },
            disabled=not params.rw,
            options=sorted(params.options),
            value=value,
            clearable=False,
            className=f"attr-control {'im' if not params.rw else ''}mutable-input",
        )
    else:
        obj = dcc.Input(
            id={
                "type": "component-attr-val",
                "index": f"{cname}/{attr}",
            },
            disabled=not params.rw,
            debounce=True,
            value=value,
            type="text",
            className=f"attr-control {'im' if not params.rw else ''}mutable-input",
        )
    return obj


# Create content div once, populate stores
@callback(
    Output("content-wrapper", "children"),
    Input("store-tomato-port", "data"),
    Input("store-pipeline-name", "data"),
)
def create_content_div(port: int, name: str) -> html.Div:
    try:
        cfg_ret = tomato.status(port=port, stgrp="tomato", timeout=TOUT)
        pip_ret = tomato.status(port=port, stgrp="pipelines", timeout=TOUT)
        if (
            cfg_ret.success
            and cfg_ret.data is not None
            and name in cfg_ret.data.devicefile.pipelines
        ):
            pip_components = cfg_ret.data.devicefile.pipelines[name].components
        else:
            pip_components = {}
        if pip_ret.success and pip_ret.data is not None:
            pip = pip_ret.data[name]
        else:
            pip = None
    except Exception as e:
        logger.warning("Exception during tomato.status:", exc_info=e)
        pip = None

    if not pip:
        return html.Div("Failed to load pipeline.", className="card")

    set_props(
        "store-pipeline-params",
        {
            "data": {
                "jobid": pip.get("jobid"),
                "sampleid": pip.get("sampleid", ""),
                "ready": ["ready"] if pip.get("ready", False) else [],
            }
        },
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
                id="pipeline-input-jobid",
                type="number",
                value=pip.get("jobid"),
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
                id="pipeline-input-sampleid",
                type="text",
                value=pip.get("sampleid", ""),
                debounce=True,
                className="top-card-input",
                style={"width": "100%", "height": "36px"},
            ),
            html.Span(
                id="pipeline-sampleid-error",
                style={
                    "font-size": "12px",
                    "margin-left": "10px",
                    "color": "var(--danger-color)",
                },
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
                id="pipeline-input-ready",
                style={
                    "display": "inline-block",
                    "font-size": "14px",
                    "font-weight": "500",
                    "flex-shrink": "0",
                },
            ),
            html.Span(
                id="pipeline-ready-error",
                style={
                    "font-size": "12px",
                    "margin-left": "10px",
                    "color": "var(--danger-color)",
                },
            ),
        ],
        style={"display": "flex", "align-items": "center", "flex-shrink": "0"},
    )

    running_store = {}
    attrs_vals_store = {}
    attrs_units_store = {}
    attrs_rw_store = {}
    components = []

    # pip_components maps role name -> real component name (e.g. "counter" -> "example_counter:(addr,1)").
    # We need the real component names (the values) to look components up below, not the role names (the keys).
    for role, cname in pip_components.items():
        try:
            ret = tomato.status(port=port, stgrp="components", timeout=TOUT)
            if ret.success and ret.data is not None:
                cmp = ret.data[cname]

        except Exception as e:
            logger.warning("Exception during tomato.status:", exc_info=e)
            continue

        div_info = html.Div(
            children=[
                html.H4(f"Component: {cmp.get('name')}", style={"margin": "0 0 5px 0"}),
                html.Div(
                    f"Role: {role} | Address: {cmp['address']!r} "
                    + f"| Channel: {cmp['channel']!r}",
                    className="text-secondary",
                    style={"font-size": "12px"},
                ),
            ],
            className="block",
            style={
                "border-bottom": "1px solid var(--border-color)",
                "padding-bottom": "8px",
                "margin-bottom": "10px",
            },
        )

        try:
            status_ret = passata.status(port=port, name=cname, timeout=TOUT)
            is_running = (
                is_component_running(status_ret.data) if status_ret.success else False
            )
        except Exception as e:
            logger.warning("Exception during passata.status:", exc_info=e)
            is_running = False

        badge_class = "badge badge-success" if is_running else "badge badge-secondary"
        badge_text = "RUNNING" if is_running else "STOPPED"

        div_status = html.Div(
            children=[
                html.Span("Status: ", style={"font-weight": "500"}),
                html.Span(
                    badge_text,
                    id={
                        "type": "component-params",
                        "index": f"{cname}",
                    },
                    className=badge_class,
                ),
            ],
            className="block",
            style={"margin-bottom": "12px"},
        )
        running_store[cname] = is_running
        try:
            attrs_ret = passata.attrs(port=port, name=cname, timeout=TOUT)
            if attrs_ret.success and attrs_ret.data is not None:
                attrs = attrs_ret.data
            else:
                attrs = {}
        except Exception as e:
            logger.warning("caught Exception during passata.attrs:", exc_info=e)
            attrs = {}

        avals = get_attrs_vals(port=port, name=cname, attrs=list(attrs))
        attrs_vals_store[cname] = {
            k: str(v.m if isinstance(v, pint.Quantity) else v) for k, v in avals.items()
        }
        attrs_units_store[cname] = {k: v.units for k, v in attrs.items()}
        attrs_rw_store[cname] = {k: v.rw for k, v in attrs.items()}

        div_attrs_ch = [
            html.Div(
                "Parameters:",
                style={
                    "font-weight": "600",
                    "margin-bottom": "8px",
                    "font-size": "13px",
                },
            )
        ]
        for attr, params in attrs.items():
            val = avals.get(attr)
            value = str(val.m if isinstance(val, pint.Quantity) else val)
            units_str = get_unit_str(params.units)

            constraints = []
            if params.minimum is not None:
                constraints.append(
                    f"min: {format_constraint(params.minimum, params.units)}"
                )
            if params.maximum is not None:
                constraints.append(
                    f"max: {format_constraint(params.maximum, params.units)}"
                )
            constraints_str = f" ({', '.join(constraints)})" if constraints else ""

            if params.rw:
                apply_btn = html.Button(
                    "Apply",
                    id={"type": "component-attr-apply-btn", "index": f"{cname}/{attr}"},
                    className="attr-apply-btn",
                )
                div_attrs_ch.append(
                    html.Div(
                        children=[
                            html.Div(f"{attr}:", className="attr-label"),
                            object_from_attrs(cname, attr, params, value),
                            apply_btn,
                            html.Span(
                                f" {units_str}{constraints_str}", className="attr-unit"
                            ),
                        ],
                        id=f"component-{cname}-attr-{attr}",
                        className="attr-row",
                    )
                )
            else:
                div_attrs_ch.append(
                    html.Div(
                        children=[
                            html.Div(f"{attr}:", className="attr-label"),
                            object_from_attrs(cname, attr, params, value),
                            html.Div(style={"width": "66px", "flex-shrink": "0"}),
                            html.Span(
                                f" {units_str}{constraints_str}", className="attr-unit"
                            ),
                        ],
                        id=f"component-{cname}-attr-{attr}",
                        className="attr-row",
                    )
                )
        div_attrs = html.Div(
            children=div_attrs_ch,
            className="component-attrs block",
        )

        try:
            data_ret = passata.get_last_data(port=port, name=cname, timeout=TOUT)
            data = data_ret.data if data_ret.success else None
        except Exception as e:
            logger.warning("Exception during passata.get_last_data:", exc_info=e)
            data = None

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
        if data is not None:
            for key in data.data_vars:
                units = data[key].attrs.get("units", "")

                units_str = get_unit_str(units)

                div_data_ch.append(
                    html.Div(
                        children=[
                            html.Div(f"{key}:", className="attr-label"),
                            dcc.Input(
                                id={
                                    "type": "component-data-val",
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
        div_data = html.Div(
            children=div_data_ch,
            className="component-data block",
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

    set_props("store-pipeline-component-names", {"data": list(pip_components.values())})
    set_props("store-pipeline-component-running", {"data": running_store})
    set_props("store-pipeline-component-attrs-vals", {"data": attrs_vals_store})
    set_props("store-pipeline-component-attrs-units", {"data": attrs_units_store})
    set_props("store-pipeline-component-attrs-rw", {"data": attrs_rw_store})

    # Create component stores
    stores = []
    for cname in pip_components.values():
        stores.append(
            dcc.Store(id={"type": "component-data-store", "index": cname}, data=None)
        )

    children = [
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
    return children


# Sync theme selection callbacks removed to app.py to avoid duplicates


@callback(
    Output({"type": "component-attr-val", "index": MATCH}, "value"),
    Input({"type": "component-attr-apply-btn", "index": MATCH}, "n_clicks"),
    State({"type": "component-attr-val", "index": MATCH}, "value"),
    State({"type": "component-attr-val", "index": MATCH}, "id"),
    State({"type": "component-attr-val", "index": MATCH}, "disabled"),
    State("store-pipeline-component-attrs-rw", "data"),
    State("store-tomato-port", "data"),
    State("store-pipeline-name", "data"),
    prevent_initial_call=True,
)
def component_attr_interaction(
    n_clicks: int,
    value: str,
    id: dict[str, str],
    disabled: bool,
    arw: dict[str, dict[str, bool]] | None,
    port: int,
    name: str,
) -> Any | dash.NoUpdate:
    if n_clicks is None:
        return dash.no_update
    cname, attr = id["index"].split("/")
    if arw[cname][attr] and not disabled:
        ret = passata.set_attr(
            port=port, name=cname, attr=attr, val=value, timeout=TOUT
        )
        if not ret.success:
            logger.warning("ret=%s", str(ret))
        current = get_attrs_vals(port=port, name=cname, attrs=[attr]).get(attr)
        return str(current)

    return dash.no_update


@callback(
    Output("pipeline-input-ready", "value"),
    Input("pipeline-input-ready", "value"),
    State("store-pipeline-params", "data"),
    State("store-tomato-port", "data"),
    State("store-pipeline-name", "data"),
    prevent_initial_call=True,
)
def pipeline_param_interaction_ready(
    values: list[str],
    data: dict | None,
    port: int,
    name: str,
) -> list[str] | dash.NoUpdate:
    if values == data["ready"]:
        return dash.no_update

    if len(values) > 0 and all(values):
        try:
            ret = tomato.pipeline_ready(port=port, pipeline=name, timeout=TOUT)
            if ret.success:
                set_props("pipeline-ready-error", {"children": ""})
            else:
                logger.warning("tomato.pipeline_ready returned failure: %s", ret.msg)
                set_props(
                    "pipeline-ready-error",
                    {"children": f"Failed to set ready: {ret.msg}"},
                )
        except Exception as e:
            logger.warning("Exception during tomato.pipeline_ready:", exc_info=e)
            set_props(
                "pipeline-ready-error",
                {"children": "Failed to set ready: could not reach pipeline daemon."},
            )
    else:
        set_props("pipeline-ready-error", {"children": ""})
    return ["ready"]


@callback(
    Input("pipeline-input-sampleid", "value"),
    State("store-tomato-port", "data"),
    State("store-pipeline-name", "data"),
    prevent_initial_call=True,
)
def pipeline_param_interaction_sampleid(sampleid: str, port: int, name: str) -> None:
    try:
        if sampleid == "":
            ret = tomato.pipeline_eject(port=port, pipeline=name, timeout=TOUT)
        else:
            ret = tomato.pipeline_load(
                port=port, pipeline=name, sampleid=sampleid, timeout=TOUT
            )
        if ret.success:
            set_props("pipeline-sampleid-error", {"children": ""})
        else:
            logger.warning("tomato.pipeline_eject/load returned failure: %s", ret.msg)
            set_props("pipeline-sampleid-error", {"children": f"Failed: {ret.msg}"})
    except Exception as e:
        logger.warning("Exception during tomato.pipeline_eject:", exc_info=e)
        set_props(
            "pipeline-sampleid-error",
            {"children": "Failed to update sample: could not reach pipeline daemon."},
        )


# Periodic updates for attributes store values
@callback(
    Output("store-pipeline-component-attrs-vals", "data"),
    Input("interval-pipeline-content", "n_intervals"),
    State("store-pipeline-component-names", "data"),
    State("store-pipeline-component-attrs-vals", "data"),
    State("store-pipeline-component-attrs-units", "data"),
    State("store-tomato-port", "data"),
    State("store-pipeline-name", "data"),
    prevent_initial_call=True,
)
def components_periodic_update_attrs_vals_store(
    _: int,
    cmps: list[str],
    avals: dict[str, dict[str, Any]] | None,
    aunits: dict[str, dict[str, str]] | None,
    port: int,
    name: str,
) -> dict[str, dict[str, Any]] | dash.NoUpdate:
    if not cmps or not avals or not aunits:
        return dash.no_update
    newdata = {}
    for cmp in cmps:
        if cmp not in avals or cmp not in aunits:
            continue
        newdata[cmp] = {}
        nvals = get_attrs_vals(port=port, name=cmp, attrs=list(avals[cmp]))
        nvals = {
            k: str(v.m if isinstance(v, pint.Quantity) else v) for k, v in nvals.items()
        }
        for key in avals[cmp]:
            val = nvals.get(key)
            if hasattr(val, "to") and aunits[cmp].get(key) is not None:
                try:
                    val = val.to(aunits[cmp][key])
                except Exception as e:
                    logger.warning("Exception during unit conversion:", exc_info=e)
            newdata[cmp][key] = val

    if newdata == avals:
        return dash.no_update
    else:
        return newdata


@callback(
    Output("store-pipeline-component-running", "data"),
    Input("interval-pipeline-content", "n_intervals"),
    State("store-pipeline-component-names", "data"),
    State("store-pipeline-component-running", "data"),
    State("store-tomato-port", "data"),
    prevent_initial_call=True,
)
def components_periodic_update_params_store(
    _: int, cmps: list[str] | None, params: dict[str, Any] | None, port: int
) -> dict[str, Any] | dash.NoUpdate:
    if not cmps:
        return dash.no_update
    newparams = {}
    for cname in cmps:
        try:
            ret = passata.status(port=port, name=cname, timeout=TOUT).data
            newparams[cname] = is_component_running(ret)
        except Exception as e:
            logger.warning("Exception during passata.status:", exc_info=e)
            newparams[cname] = False

    if newparams == params:
        return dash.no_update
    else:
        return newparams


@callback(
    Output("store-pipeline-params", "data"),
    Input("interval-pipeline-content", "n_intervals"),
    State("store-pipeline-params", "data"),
    State("store-tomato-port", "data"),
    State("store-pipeline-name", "data"),
    prevent_initial_call=True,
)
def pipeline_periodic_update_params_store(
    _: int, data: dict | None, port: int, name: str
) -> dict | dash.NoUpdate:
    try:
        pip = tomato.status(port=port, stgrp="pipelines", timeout=TOUT).data[name]
        newdata = {
            "jobid": pip.get("jobid"),
            "sampleid": pip.get("sampleid", ""),
            "ready": ["ready"] if pip.get("ready", False) else [],
        }
    except Exception as e:
        logger.warning("Exception during tomato.status:", exc_info=e)
        newdata = data

    if newdata == data:
        return dash.no_update
    else:
        return newdata


# UI updates triggered by Stores
@callback(
    Output(
        {"type": "component-attr-val", "index": MATCH},
        "value",
        allow_duplicate=True,
    ),
    Input("store-pipeline-component-attrs-vals", "data"),
    State({"type": "component-attr-val", "index": MATCH}, "value"),
    State({"type": "component-attr-val", "index": MATCH}, "id"),
    State("store-pipeline-component-attrs-rw", "data"),
    prevent_initial_call=True,
)
def components_update_attr_display(
    avals: dict[str, dict[str, Any]] | None,
    value: Any,
    id: dict[str, str],
    rw: dict[str, dict[str, bool]] | None,
) -> Any | dash.NoUpdate:
    if not avals or not id or "index" not in id or not rw:
        return dash.no_update
    try:
        cname, key = id["index"].split("/")
        if cname not in avals or key not in avals[cname]:
            return dash.no_update
        if rw.get(cname, {}).get(key, False):
            return dash.no_update
        newval = avals[cname][key]
    except Exception as e:
        logger.warning("Exception during components_update_attr_display:", exc_info=e)
        return dash.no_update
    if isinstance(newval, float):
        newval = round(newval, 3)
    if isinstance(value, float):
        value = round(value, 3)
    if newval == value:
        return dash.no_update
    else:
        return newval


@callback(
    Output({"type": "component-attr-val", "index": MATCH}, "disabled"),
    Input("store-pipeline-component-running", "data"),
    State({"type": "component-attr-val", "index": MATCH}, "id"),
    State("store-pipeline-component-attrs-rw", "data"),
    prevent_initial_call=True,
)
def components_disable_attr_running(
    running, id: dict[str, str], rw: dict[str, dict[str, bool]] | None
) -> bool | dash.NoUpdate:
    if not running or not id or "index" not in id or not rw:
        return dash.no_update
    try:
        cname, key = id["index"].split("/")
        if cname not in running or cname not in rw or key not in rw[cname]:
            return dash.no_update
        if running.get(cname, False):
            return True
        else:
            return not rw[cname].get(key, False)
    except Exception as e:
        logger.warning("Exception during components_disable_attr_running:", exc_info=e)
        return dash.no_update


@callback(
    Output("pipeline-input-ready", "value", allow_duplicate=True),
    Output("pipeline-input-sampleid", "value", allow_duplicate=True),
    Output("pipeline-input-jobid", "value", allow_duplicate=True),
    Input("store-pipeline-params", "data"),
    State("pipeline-input-ready", "value"),
    State("pipeline-input-sampleid", "value"),
    State("pipeline-input-jobid", "value"),
    prevent_initial_call=True,
)
def pipeline_update_param_display(
    data: dict | None, ready: list[str], sampleid: str | None, jobid: int
) -> tuple[Any | dash.NoUpdate, Any | dash.NoUpdate, Any | dash.NoUpdate]:
    r_val = data["ready"] if data["ready"] != ready else dash.no_update
    s_val = data["sampleid"] if data["sampleid"] != sampleid else dash.no_update
    j_val = data["jobid"] if data["jobid"] != jobid else dash.no_update
    return r_val, s_val, j_val


@callback(
    Output(
        {"type": "component-params", "index": MATCH},
        "children",
        allow_duplicate=True,
    ),
    Output(
        {"type": "component-params", "index": MATCH},
        "className",
        allow_duplicate=True,
    ),
    Input("store-pipeline-component-running", "data"),
    State({"type": "component-params", "index": MATCH}, "children"),
    State({"type": "component-params", "index": MATCH}, "id"),
    prevent_initial_call=True,
)
def components_update_param_display(
    data: dict | None, value: str, id: dict[str, str]
) -> tuple[str | dash.NoUpdate, str | dash.NoUpdate]:
    if not data or not id or "index" not in id:
        return dash.no_update, dash.no_update
    running_state = data.get(id["index"], False)
    new_text = "RUNNING" if running_state else "STOPPED"
    new_class = "badge badge-success" if running_state else "badge badge-secondary"
    if value == new_text:
        return dash.no_update, dash.no_update
    else:
        return new_text, new_class


@callback(
    Output({"type": "component-data-store", "index": MATCH}, "data"),
    Input("interval-pipeline-content", "n_intervals"),
    State("store-tomato-port", "data"),
    State({"type": "component-data-store", "index": MATCH}, "id"),
    State({"type": "component-data-store", "index": MATCH}, "data"),
)
def update_component_stores(n_intervals: int, port: int, id: dict, data: dict | None):
    logger.debug("updating store '%s'", id["index"])
    return update_datastore(port=port, name=id["index"], datastore=data)


@callback(
    Output({"type": "component-data-val", "index": ALL}, "value"),
    Input({"type": "component-data-store", "index": MATCH}, "data"),
    Input({"type": "component-data-store", "index": MATCH}, "id"),
    State({"type": "component-data-val", "index": ALL}, "value"),
    State({"type": "component-data-val", "index": ALL}, "id"),
    prevent_initial_call=True,
)
def components_update_data_display(
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
        val = pretty(cdata["data_vars"][vattr]["data"][-1])
        if val != vals[vi]:
            nvals[vi] = val
    return nvals


dash.register_page(__name__, path_template="/pipelines/<port>/<name>")


def layout(port: int, name: str, **_) -> list[html.Div]:
    return [
        create_header_div(port, name),
        html.Div(children=[], id="content-wrapper", className="content-wrapper"),
    ]
