import dash
from dash import html, dcc, callback, Output, Input, State
from tomato import passata, tomato
import zmq
import json

CTXT = zmq.Context()
TOUT = 1000
PORT = 1234
kwargs = dict(timeout=TOUT, context=CTXT)

dash.register_page(__name__, path_template="/")


header = html.Header(
    className="header",
    children=[
        "tomato port:",
        dcc.Input(
            value=PORT,
            type="number",
            id="tomato-port-setter",
        ),
        html.Button("Reload", id="tomato-status"),
        dcc.Store(id="tomato-port", data=PORT),
    ],
)

content = html.Div(
    className="main",
    children=[
        dcc.Tabs(
            children=[
                dcc.Tab(label="pipelines", value="pipelines"),
                dcc.Tab(label="drivers", value="drivers"),
                dcc.Tab(label="devices", value="devices"),
                dcc.Tab(label="components", value="components"),
                dcc.Tab(label="jobs", value="jobs"),
            ],
            id="tomato-stgrp-tab",
            value="pipelines",
        ),
        html.Div(id="tomato-stgrp", children=["Default text."]),
        dcc.Store(id="store-tomato-status"),
    ],
)


@callback(Output("tomato-port", "data"), Input("tomato-port-setter", "value"))
def store_tomato_port(value):
    return int(value)


@callback(
    Output("store-tomato-status", "data"),
    Input("tomato-status", "n_clicks"),
    State("tomato-port", "data"),
)
def store_tomato_status(n_clicks, port):
    ret = tomato.status(stgrp="tomato", port=port, **kwargs)
    if not ret.success:
        return ret.msg
    else:
        return ret.data.model_dump_json()


@callback(
    Output("tomato-stgrp", "children"),
    Input("store-tomato-status", "data"),
    Input("tomato-stgrp-tab", "value"),
    State("tomato-port", "data"),
)
def update_tomato_stgrp(data, stgrp, port):
    try:
        js = json.loads(data)
    except json.JSONDecodeError:
        return data

    if stgrp == "pipelines":
        return format_obj(
            obj=js["pips"],
            headers=["Name", "Ready", "Job ID", "Sample ID"],
            attrs=["name", "ready", "jobid", "sampleid"],
            otype=stgrp,
            port=port,
        )
    elif stgrp == "drivers":
        return format_obj(
            obj=js["drvs"],
            headers=["Name", "Version", "Port", "Process ID"],
            attrs=["name", "version", "port", "pid"],
            otype=stgrp,
            port=port,
        )
    elif stgrp == "devices":
        return format_obj(
            obj=js["devs"],
            headers=["Name", "Driver", "Address", "Channels"],
            attrs=["name", "driver", "address", "channels"],
            otype=stgrp,
            port=port,
        )
    elif stgrp == "components":
        return format_obj(
            obj=js["cmps"],
            headers=["Name", "Driver", "Address", "Channel", "Role", "Capabs"],
            attrs=["name", "driver", "address", "channel", "role", "capabilities"],
            otype=stgrp,
            port=port,
        )
    else:
        return data
    # return str(value)


def format_obj(obj, headers, attrs, otype, port):
    rows = [html.Tr(children=[html.Th(h) for h in headers])]
    for k, v in obj.items():
        row = [html.Td(str(v[i])) for i in attrs]
        row[0].children = dcc.Link(
            row[0].children,
            href=f"./{otype}/{port}/{row[0].children}",
            target="_blank",
        )
        rows.append(html.Tr(children=row))
    return html.Table(children=rows, className="stgrp")


def layout(**_):
    return [header, content]
