import logging
import dash
from dash import MATCH, Input, Output, State, callback, dcc, html, set_props
from marinara.icons import get_icon
from marinara.utils import (
    clean_value,
    format_attr_value,
    format_constraint,
    get_field,
    get_unit_str,
    kwargs,
    parse_input_value,
)
from tomato import passata, tomato

logger = logging.getLogger(__name__)


def get_data_fields(data):
    """Dynamically extracts all coordinate and data variable keys from a device dataset."""
    if data is not None and hasattr(data, "data_vars"):
        return ["uts"] + list(data.data_vars.keys())
    elif isinstance(data, dict):
        return list(data.keys())
    return ["uts"]


def create_header_div(port: int, name: str):
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
            dcc.Store(id="store-pipeline-component-data", data=None),
            dcc.Interval(id="interval-pipeline-content", interval=2000),
            dcc.Interval(id="interval-pipeline-init", interval=300, max_intervals=1),
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


def object_from_attrs(cname, attr, params, value):
    options = get_field(params, "options")
    is_rw = get_field(params, "rw", False)

    if options is not None:
        obj = dcc.Dropdown(
            id={
                "type": "component-attr-val",
                "index": f"{cname}/{attr}",
            },
            disabled=False if is_rw else True,
            options=sorted(options),
            value=value,
            clearable=False,
            className="attr-control mutable-input"
            if is_rw
            else "attr-control immutable-input",
        )
    else:
        obj = dcc.Input(
            id={
                "type": "component-attr-val",
                "index": f"{cname}/{attr}",
            },
            disabled=False if is_rw else True,
            debounce=True,
            value=format_attr_value(value),
            type="text",
            className="attr-control mutable-input"
            if is_rw
            else "attr-control immutable-input",
        )
    return obj


# Create content div once, populate stores
@callback(
    Output("content-wrapper", "children"),
    Input("store-tomato-port", "data"),
    Input("store-pipeline-name", "data"),
    Input("interval-pipeline-init", "n_intervals"),
)
def create_content_div(port, name, n_intervals):
    try:
        pip_ret = tomato.status(**kwargs, port=port, stgrp="pipelines")
        pip = pip_ret.data[name] if pip_ret.success else None
    except Exception:
        pip = None

    if not pip:
        return html.Div("Failed to load pipeline.", className="card")

    set_props(
        "store-pipeline-params",
        {
            "data": {
                "jobid": pip.jobid,
                "sampleid": str(pip.sampleid) if pip.sampleid is not None else "",
                "ready": "ready" if pip.ready else "not_ready",
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
                value=pip.jobid,
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
                value=str(pip.sampleid) if pip.sampleid is not None else "",
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
            dcc.Dropdown(
                options=[
                    {"label": "Idle (Not Ready)", "value": "not_ready"},
                    {"label": "Ready", "value": "ready"},
                ],
                value="ready" if pip.ready else "not_ready",
                id="pipeline-input-ready",
                clearable=False,
                disabled=bool(pip.jobid),
                style={"min-width": "160px", "font-size": "14px"},
            ),
        ],
        style={"display": "flex", "align-items": "center", "flex-shrink": "0"},
    )

    running_store = {}
    attrs_vals_store = {}
    attrs_units_store = {}
    attrs_rw_store = {}
    components = []

    for cname in pip.components:
        try:
            cmp = tomato.status(**kwargs, port=port, stgrp="components").data[cname]
        except Exception:
            continue

        div_info = html.Div(
            children=[
                html.H4(f"Component: {cmp.name}", style={"margin": "0 0 5px 0"}),
                html.Div(
                    f"Role: {cmp.role} | Address: {cmp.address!r} | Channel: {cmp.channel!r}",
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
            status_ret = passata.status(**kwargs, port=port, name=cname)
            status = status_ret.data if status_ret.success else {"running": False}
        except Exception:
            status = {"running": False}

        badge_class = (
            "badge badge-success" if status["running"] else "badge badge-secondary"
        )
        badge_text = "RUNNING" if status["running"] else "STOPPED"

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
        running_store[cname] = status["running"]
        try:
            attrs_ret = passata.attrs(**kwargs, port=port, name=cname)
            attrs = attrs_ret.data if attrs_ret.success else {}
        except Exception:
            attrs = {}

        try:
            avals_ret = passata.get_attrs(
                **kwargs, port=port, name=cname, attrs=list(attrs.keys())
            )
            avals = avals_ret.data if avals_ret.success else {}
        except Exception:
            avals = {}

        attrs_vals_store[cname] = {k: clean_value(v) for k, v in avals.items()}
        attrs_units_store[cname] = {
            k: get_field(attrs[k], "units") for k in attrs.keys()
        }
        attrs_rw_store[cname] = {
            k: get_field(attrs[k], "rw", False) for k in attrs.keys()
        }

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
            is_rw = get_field(params, "rw", False)
            value = clean_value(avals.get(attr))
            units = get_unit_str(get_field(params, "units"))

            min_val = get_field(params, "minimum")
            max_val = get_field(params, "maximum")
            constraints = []
            if min_val is not None:
                constraints.append(
                    f"min: {format_constraint(min_val, get_field(params, 'units'))}"
                )
            if max_val is not None:
                constraints.append(
                    f"max: {format_constraint(max_val, get_field(params, 'units'))}"
                )
            constraints_str = f" ({', '.join(constraints)})" if constraints else ""

            if is_rw:
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
                                f" {units}{constraints_str}", className="attr-unit"
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
                                f" {units}{constraints_str}", className="attr-unit"
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
            data_ret = passata.get_last_data(**kwargs, port=port, name=cname)
            data = data_ret.data if data_ret.success else None
        except Exception:
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
        for key in get_data_fields(data):
            if data is None or key not in data:
                value = None
                units = ""
            else:
                value = clean_value(data[key].values[-1])
                units = data[key].attrs.get("units", "")

            if isinstance(value, float):
                value = round(value, 3)
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
                            value=value,
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

    set_props("store-pipeline-component-names", {"data": pip.components})
    set_props("store-pipeline-component-running", {"data": running_store})
    set_props("store-pipeline-component-attrs-vals", {"data": attrs_vals_store})
    set_props("store-pipeline-component-attrs-units", {"data": attrs_units_store})
    set_props("store-pipeline-component-attrs-rw", {"data": attrs_rw_store})

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
def component_attr_interaction(n_clicks, value, id, disabled, arw, port, name):
    if n_clicks is None:
        return dash.no_update
    cname, attr = id["index"].split("/")
    if arw and arw.get(cname, {}).get(attr) and not disabled:
        parsed_val = parse_input_value(value)
        try:
            ret = passata.set_attr(
                **kwargs, port=port, name=cname, attr=attr, val=parsed_val
            )
            if ret.success:
                return format_attr_value(ret.data)
            get_ret = passata.get_attrs(
                **kwargs, port=port, name=cname, attrs=[attr]
            )
            current = (
                get_ret.data.get(attr)
                if (get_ret.success and isinstance(get_ret.data, dict))
                else None
            )
            return format_attr_value(current)
        except Exception as e:
            logger.warning(f"Failed to set attribute {attr} on component {cname}: {e}")
            try:
                get_ret = passata.get_attrs(
                    **kwargs, port=port, name=cname, attrs=[attr]
                )
                current = (
                    get_ret.data.get(attr)
                    if (get_ret.success and isinstance(get_ret.data, dict))
                    else None
                )
                return format_attr_value(current)
            except Exception:
                return dash.no_update
    return dash.no_update


@callback(
    Output("pipeline-input-ready", "value"),
    Output("pipeline-input-sampleid", "value"),
    Output("pipeline-alert-container", "children"),
    Input("pipeline-input-ready", "value"),
    State("pipeline-input-sampleid", "value"),
    State("store-pipeline-params", "data"),
    State("store-tomato-port", "data"),
    State("store-pipeline-name", "data"),
    prevent_initial_call=True,
)
def pipeline_param_interaction_ready(value, sampleid, data, port, name):
    clean_sampleid = sampleid.strip() if sampleid else ""

    if value == "ready":
        if not clean_sampleid:
            alert = html.Div(
                [
                    get_icon("alert-circle", size=18),
                    html.Span(
                        " Cannot set pipeline status to 'Ready' without a valid Sample ID. Please enter a Sample ID first.",
                        style={"font-weight": "600", "margin-left": "8px", "flex-grow": "1"},
                    ),
                    html.Button(
                        "×",
                        id="btn-close-pipeline-alert",
                        className="close-alert-btn",
                        style={
                            "background": "none",
                            "border": "none",
                            "font-size": "20px",
                            "font-weight": "700",
                            "color": "#b45309",
                            "cursor": "pointer",
                            "margin-left": "15px",
                            "line-height": "1",
                        },
                    ),
                ],
                className="badge badge-warning",
                style={
                    "display": "flex",
                    "align-items": "center",
                    "padding": "12px 20px",
                    "font-size": "14px",
                    "border-radius": "8px",
                    "background-color": "rgba(245, 158, 11, 0.15)",
                    "color": "#b45309",
                    "border": "1px solid rgba(245, 158, 11, 0.4)",
                    "margin-bottom": "20px",
                },
            )
            return "not_ready", sampleid, alert

        try:
            tomato.pipeline_ready(**kwargs, port=port, pipeline=name)
        except Exception as e:
            logger.error("Failed to set pipeline ready: %s", e)
            return (
                "not_ready",
                sampleid,
                html.Div(f"Error setting ready: {e}", className="text-secondary"),
            )

        return "ready", sampleid, None

    else:
        try:
            tomato.pipeline_eject(**kwargs, port=port, pipeline=name)
        except Exception as e:
            logger.error("Failed to eject pipeline sample: %s", e)

        return "not_ready", "", dash.no_update


@callback(
    Output("pipeline-alert-container", "children", allow_duplicate=True),
    Input("btn-close-pipeline-alert", "n_clicks"),
    prevent_initial_call=True,
)
def close_pipeline_alert(n_clicks):
    if n_clicks:
        return None
    return dash.no_update


@callback(
    Output("pipeline-alert-container", "children", allow_duplicate=True),
    Input("pipeline-input-sampleid", "value"),
    State("store-tomato-port", "data"),
    State("store-pipeline-name", "data"),
    prevent_initial_call=True,
)
def pipeline_param_interaction_sampleid(sampleid, port, name):
    clean_sampleid = sampleid.strip() if sampleid else ""
    try:
        if not clean_sampleid:
            tomato.pipeline_eject(**kwargs, port=port, pipeline=name)
            return dash.no_update
        else:
            tomato.pipeline_load(
                **kwargs, port=port, pipeline=name, sampleid=clean_sampleid
            )
            return None
    except Exception as e:
        logger.error("Failed to update sampleid: %s", e)
    return dash.no_update


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
def components_periodic_update_attrs_vals_store(_, cmps, avals, aunits, port, name):
    if not cmps or not avals or not aunits:
        return dash.no_update
    newdata = {}
    for cmp in cmps:
        if cmp not in avals or cmp not in aunits:
            continue
        newdata[cmp] = {}
        try:
            nvals_ret = passata.get_attrs(
                **kwargs, port=port, name=cmp, attrs=list(avals[cmp].keys())
            )
            nvals = nvals_ret.data if nvals_ret.success else {}
        except Exception:
            nvals = {}

        for key in avals[cmp].keys():
            val = nvals.get(key)
            if hasattr(val, "to") and aunits[cmp].get(key) is not None:
                try:
                    val = val.to(aunits[cmp][key])
                except Exception:
                    pass
            newdata[cmp][key] = clean_value(val)

    if newdata == avals:
        return dash.no_update
    else:
        return newdata


@callback(
    Output("store-pipeline-component-data", "data"),
    Input("interval-pipeline-content", "n_intervals"),
    State("store-pipeline-component-names", "data"),
    State("store-pipeline-component-data", "data"),
    State("store-tomato-port", "data"),
    State("store-pipeline-name", "data"),
    prevent_initial_call=True,
)
def components_periodic_update_data_store(_, cmps, data, port, name):
    if not cmps:
        return dash.no_update
    newdata = {}
    for cmp in cmps:
        newdata[cmp] = {}
        try:
            ds_ret = passata.get_last_data(**kwargs, port=port, name=cmp)
            ds = ds_ret.data if ds_ret.success else None
        except Exception:
            ds = None

        if ds is None:
            continue
        dd = ds.to_dict()
        for k, v in dd["coords"].items():
            newdata[cmp][k] = clean_value(v["data"][-1])
        for k, v in dd["data_vars"].items():
            newdata[cmp][k] = clean_value(v["data"][-1])

    if newdata == {}:
        return dash.no_update
    elif newdata == data:
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
def components_periodic_update_params_store(_, cmps, params, port):
    if not cmps:
        return dash.no_update
    newparams = {}
    for cname in cmps:
        try:
            ret = passata.status(**kwargs, port=port, name=cname).data
            newparams[cname] = ret["running"]
        except Exception:
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
def pipeline_periodic_update_params_store(_, data, port, name):
    try:
        pip = tomato.status(**kwargs, port=port, stgrp="pipelines").data[name]
        newdata = {
            "jobid": pip.jobid,
            "sampleid": str(pip.sampleid) if pip.sampleid is not None else "",
            "ready": "ready" if pip.ready else "not_ready",
        }
    except Exception:
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
def components_update_attr_display(avals, value, id, rw):
    if not avals or not id or "index" not in id or not rw:
        return dash.no_update
    try:
        cname, key = id["index"].split("/")
        if cname not in avals or key not in avals[cname]:
            return dash.no_update
        if rw.get(cname, {}).get(key, False):
            return dash.no_update
        newval = avals[cname][key]
    except Exception:
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
def components_disable_attr_running(running, id, rw):
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
    except Exception:
        return dash.no_update


@callback(
    Output("pipeline-input-ready", "value", allow_duplicate=True),
    Output("pipeline-input-ready", "disabled"),
    Output("pipeline-input-sampleid", "value", allow_duplicate=True),
    Output("pipeline-input-jobid", "value", allow_duplicate=True),
    Input("store-pipeline-params", "data"),
    State("pipeline-input-ready", "value"),
    State("pipeline-input-sampleid", "value"),
    State("pipeline-input-jobid", "value"),
    prevent_initial_call=True,
)
def pipeline_update_param_display(data, ready, sampleid, jobid):
    # Dropdown is disabled while job is executing
    is_executing = bool(data.get("jobid"))
    r_val = data["ready"] if data["ready"] != ready else dash.no_update
    s_val = data["sampleid"] if data["sampleid"] != sampleid else dash.no_update
    j_val = data["jobid"] if data["jobid"] != jobid else dash.no_update
    return r_val, is_executing, s_val, j_val


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
def components_update_param_display(data, value, id):
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
    Output(
        {"type": "component-data-val", "index": MATCH},
        "value",
        allow_duplicate=True,
    ),
    Input("store-pipeline-component-data", "data"),
    State({"type": "component-data-val", "index": MATCH}, "value"),
    State({"type": "component-data-val", "index": MATCH}, "id"),
    prevent_initial_call=True,
)
def components_update_data_display(data, value, id):
    cname, key = id["index"].split("/")
    if data is None or key not in data.get(cname, {}):
        return dash.no_update
    elif value == data[cname][key]:
        return dash.no_update
    else:
        val = data[cname][key]
        if isinstance(val, float):
            val = round(val, 3)
        return val


dash.register_page(__name__, path_template="/pipelines/<port>/<name>")


def layout(port=None, name=None, **_):
    port = int(port)

    return [
        create_header_div(port, name),
        html.Div(id="pipeline-alert-container"),
        html.Div(children=[], id="content-wrapper", className="content-wrapper"),
    ]
