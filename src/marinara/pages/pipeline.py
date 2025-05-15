import dash
from dash import html, dcc, callback, set_props, Input, Output, State, MATCH
from tomato import passata, tomato
from zmq import Context
import logging
import pint

logger = logging.getLogger(__name__)

CTXT = Context()
TOUT = 1000
kwargs = dict(timeout=TOUT, context=CTXT)


def get_data_fields(pname, dname):
    if dname == "example_counter":
        return (
            "uts",
            "val",
        )
    elif dname == "bronkhorst":
        return (
            "uts",
            "setpoint",
            "flow",
            "pressure",
            "control_mode",
        )
    elif dname == "jumo":
        return (
            "uts",
            "setpoint",
            "temperature",
            "duty_cycle",
            "ramp_rate",
            "ramp_target",
        )
    elif dname == "drycal":
        return (
            "uts",
            "flow",
        )
    else:
        return ("uts",)


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
        ],
        className="header-store",
    )

    banner = html.Div(
        children=[html.Div(f"The user requested pipeline {name!r} on port {port}.")],
        className="header-banner",
    )

    return html.Div(
        children=[stores, banner],
        className="header-wrapper",
    )


def object_from_attrs(cname, attr, params, value):
    if params.options is not None:
        obj = dcc.Dropdown(
            id={
                "type": "component-attr-val",
                "index": f"{cname}/{attr}",
            },
            disabled=False if params.rw else True,
            options=list(params.options),
            value=value,
            clearable=False,
        )
    else:
        obj = dcc.Input(
            id={
                "type": "component-attr-val",
                "index": f"{cname}/{attr}",
            },
            disabled=False if params.rw else True,
            debounce=True,
            value=value,
            type="text" if params.type is str else "number",
            className="inline",
        )
    return obj


# Create content div once, populate stores
@callback(
    Output("content-wrapper", "children"),
    Input("store-tomato-port", "data"),
    Input("store-pipeline-name", "data"),
)
def create_content_div(port, name):
    pip = tomato.status(**kwargs, port=port, stgrp="pipelines").data[name]

    set_props(
        "store-pipeline-params",
        {
            "data": {
                "jobid": pip.jobid,
                "sampleid": str(pip.sampleid) if pip.sampleid is not None else "",
                "ready": ["ready"] if pip.ready else [],
            }
        },
    )

    jobid = html.Div(
        children=[
            "jobid:",
            dcc.Input(
                id="pipeline-input-jobid", type="number", value=pip.jobid, disabled=True,
            ),
        ],
        className="block",
    )

    sampleid = html.Div(
        children=[
            "sampleid:",
            dcc.Input(
                id="pipeline-input-sampleid",
                type="text",
                value=str(pip.sampleid) if pip.sampleid is not None else "",
                debounce=True,
            ),
        ],
        className="block",
    )

    ready = html.Div(
        children=[
            html.Div(
                "ready:",
                className="inline",
            ),
            dcc.Checklist(
                options=["ready"],
                value=["ready"] if pip.ready else [],
                id="pipeline-input-ready",
                inline=True,
                className="inline",
            ),
        ],
        className="block",
    )

    running_store = {}
    attrs_vals_store = {}
    attrs_units_store = {}
    attrs_rw_store = {}
    components = []
    for cname in pip.components:
        cmp = tomato.status(**kwargs, port=port, stgrp="components").data[cname]
        div_info = html.Div(
            children=[
                html.Div(f"name: {cmp.name}"),
                html.Div(f"role: {cmp.role}"),
                html.Div(f"address: {cmp.address!r}, channel: {cmp.channel!r}"),
            ],
            className="block",
        )

        status = passata.status(**kwargs, port=port, name=cname).data
        div_status = html.Div(
            children=[
                html.Div(
                    "running: ",
                    className="inline",
                ),
                html.Div(
                    f"{status['running']}",
                    id={
                        "type": "component-params",
                        "index": f"{cname}",
                    },
                    className="inline",
                )
            ],
            className="block",
        )
        running_store[cname] = status["running"]

        attrs = passata.attrs(**kwargs, port=port, name=cname).data
        avals = passata.get_attrs(
            **kwargs, port=port, name=cname, attrs=attrs.keys()
        ).data
        attrs_vals_store[cname] = {
            k: v.m if attrs[k].units is not None else v for k, v in avals.items()
        }
        attrs_units_store[cname] = {k: attrs[k].units for k in attrs.keys()}
        attrs_rw_store[cname] = {k: attrs[k].rw for k in attrs.keys()}

        div_attrs_ch = []
        for attr, params in attrs.items():
            value = avals[attr].m if params.units is not None else avals[attr]
            units = (
                f"{pint.Quantity(params.units).units:~H}"
                if params.units is not None
                else ""
            )
            div_attrs_ch.append(
                html.Div(
                    children=[
                        html.Div(
                            f"{attr}:",
                            className="inline",
                        ),
                        object_from_attrs(cname, attr, params, value),
                        html.Div(
                            f"{units}",
                            className="inline",
                        )
                    ],
                    id=f"component-{cname}-attr",
                    className="block",
                )
            )
        div_attrs = html.Div(
            children=div_attrs_ch,
            className="component-attrs block",
        )

        data = passata.get_last_data(**kwargs, port=port, name=cname).data
        div_data_ch = []
        for key in get_data_fields(name, cmp.driver):
            if data is None or key not in data:
                value = None
                units = ""
            else:
                value = data[key].values[-1]
                units = data[key].attrs.get("units", "")
            div_data_ch.append(
                html.Div(
                    children=[
                        f"{key}:",
                        dcc.Input(
                            id={
                                "type": "component-data-val",
                                "index": f"{cname}/{key}",
                            },
                            disabled=True,
                            value=value,
                        ),
                        f"{units}",
                    ],
                    id={"type": "component-data-key", "index": f"{cname}/{key}"},
                )
            )
        div_data = html.Div(
            children=div_data_ch,
            className="component-data block",
        )
        components.append(
            html.Div(
                id=f"component-{cname}",
                children=[div_info, div_status, div_attrs, div_data],
                className="component",
            )
        )
    set_props("store-pipeline-component-names", {"data": pip.components})
    set_props("store-pipeline-component-running", {"data": running_store})
    set_props("store-pipeline-component-attrs-vals", {"data": attrs_vals_store})
    set_props("store-pipeline-component-attrs-units", {"data": attrs_units_store})
    set_props("store-pipeline-component-attrs-rw", {"data": attrs_rw_store})

    children = [
        html.Div(
            children=[ready, jobid, sampleid], className="pipeline-params-wrapper"
        ),
        html.Div(children=components, className="pipeline-components-wrapper"),
    ]
    return children


@callback(
    Output({"type": "component-attr-val", "index": MATCH}, "value"),
    Input({"type": "component-attr-val", "index": MATCH}, "value"),
    State({"type": "component-attr-val", "index": MATCH}, "id"),
    State({"type": "component-attr-val", "index": MATCH}, "disabled"),
    State("store-pipeline-component-attrs-rw", "data"),
    State("store-tomato-port", "data"),
    State("store-pipeline-name", "data"),
    prevent_initial_call=True,
)
def component_attr_interaction(value, id, disabled, arw, port, name):
    cname, attr = id["index"].split("/")
    if arw[cname][attr] and not disabled:
        ret = passata.set_attr(**kwargs, port=port, name=cname, attr=attr, val=value)
        if ret.success:
            return dash.no_update
        else:
            return None
    else:
        return dash.no_update


@callback(
    Output("pipeline-input-ready", "value"),
    Input("pipeline-input-ready", "value"),
    State("store-pipeline-params", "data"),
    State("store-tomato-port", "data"),
    State("store-pipeline-name", "data"),
    prevent_initial_call=True,
)
def pipeline_param_interaction_ready(values, data, port, name):
    if values == data["ready"]:
        return dash.no_update

    if len(values) > 0 and all(values):
        tomato.pipeline_ready(**kwargs, port=port, pipeline=name)
    return ["ready"]


@callback(
    Input("pipeline-input-sampleid", "value"),
    State("store-tomato-port", "data"),
    State("store-pipeline-name", "data"),
    prevent_initial_call=True,
)
def pipeline_param_interaction_sampleid(sampleid, port, name):
    if sampleid == "":
        tomato.pipeline_eject(**kwargs, port=port, pipeline=name)
    else:
        tomato.pipeline_load(**kwargs, port=port, pipeline=name, sampleid=sampleid)


# Background store update using passata / tomato
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
    newdata = {}
    for cmp in cmps:
        newdata[cmp] = {}
        nvals = passata.get_attrs(
            **kwargs, port=port, name=cmp, attrs=avals[cmp].keys()
        ).data
        for key in avals[cmp].keys():
            if aunits[cmp][key] is not None:
                val = nvals[key].to(aunits[cmp][key]).m
            else:
                val = nvals[key]
            newdata[cmp][key] = val
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
    newdata = {}
    for cmp in cmps:
        newdata[cmp] = {}
        ds = passata.get_last_data(**kwargs, port=port, name=cmp).data
        if ds is None:
            continue
        dd = ds.to_dict()
        for k, v in dd["coords"].items():
            newdata[cmp][k] = v["data"][-1]
        for k, v in dd["data_vars"].items():
            newdata[cmp][k] = v["data"][-1]
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
    newparams = {}
    for cname in cmps:
        ret = passata.status(**kwargs, port=port, name=cname).data
        newparams[cname] = ret["running"]
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
    pip = tomato.status(**kwargs, port=port, stgrp="pipelines").data[name]
    newdata = {
        "jobid": pip.jobid,
        "sampleid": str(pip.sampleid) if pip.sampleid is not None else "",
        "ready": ["ready"] if pip.ready else [],
    }
    if newdata == data:
        return dash.no_update
    else:
        return newdata


# UI update if background stores have been changed
@callback(
    Output(
        {"type": "component-attr-val", "index": MATCH},
        "value",
        allow_duplicate=True,
    ),
    Input("store-pipeline-component-attrs-vals", "data"),
    State({"type": "component-attr-val", "index": MATCH}, "value"),
    State({"type": "component-attr-val", "index": MATCH}, "id"),
    prevent_initial_call=True,
)
def components_update_attr_display(avals, value, id):
    cname, key = id["index"].split("/")
    newval = avals[cname][key]
    if isinstance(newval, float):
        newval = round(newval, 3)
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
    print(f"{id=}")
    cname, key = id["index"].split("/")
    print(f"{running=} {key=} {rw[cname][key]=}")
    if running[cname]:
        return True
    else:
        return not rw[cname][key]


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
def pipeline_update_param_display(data, ready, sampleid, jobid):
    if data["ready"] == ready:
        data["ready"] = dash.no_update
    if data["sampleid"] == sampleid:
        data["sampleid"] = dash.no_update
    if data["jobid"] == jobid:
        data["jobid"] = dash.no_update

    return data["ready"], data["sampleid"], data["jobid"]


@callback(
    Output(
        {"type": "component-params", "index": MATCH},
        "children",
        allow_duplicate=True,
    ),
    Input("store-pipeline-component-running", "data"),
    State({"type": "component-params", "index": MATCH}, "children"),
    State({"type": "component-params", "index": MATCH}, "id"),
    prevent_initial_call=True,
)
def components_update_param_display(data, value, id):
    if value == str(data[id["index"]]):
        return dash.no_update
    else:
        return str(data[id["index"]])

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
    if data is None or key not in data[cname]:
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
        html.Div(children=[], id="content-wrapper", className="content-wrapper"),
    ]
