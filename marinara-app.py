from dash import Dash, html, dcc, callback, Output, Input, State
from tomato import passata, tomato
import zmq
import json

CTXT = zmq.Context()
TOUT = 1000
kwargs = dict(timeout=TOUT, context=CTXT)

app = Dash()

header = html.Header(
    className="header",
    children=[
        "tomato port:",
        dcc.Input(
            # placeholder=PORT,
            value=1234,
            type="number",
            id="tomato-port",
        ),
        html.Button("Reload", id="tomato-status"),
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


@callback(
    Output("store-tomato-status", "data"),
    Input("tomato-status", "n_clicks"),
    State("tomato-port", "value"),
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
    #State("tomato-stgrp-tab", "value"),
)
def update_tomato_stgrp(data, stgrp):
    try:
        js = json.loads(data)
    except json.JSONDecodeError:
        return data

    if stgrp == "pipelines":
        return format_obj(
            js["pips"],
            ["Name", "Ready", "Job ID", "Sample ID"],
            ["name", "ready", "jobid", "sampleid"],
        )
    elif stgrp == "drivers":
        return format_obj(
            js["drvs"],
            ["Name", "Version", "Port", "Process ID"],
            ["name", "version", "port", "pid"],
        )
    elif stgrp == "devices":
        return format_obj(
            js["devs"],
            ["Name", "Driver", "Address", "Channels"],
            ["name", "driver", "address", "channels"],
        )
    elif stgrp == "components":
        return format_obj(
            js["cmps"],
            ["Driver", "Address", "Channel", "Role", "Capabs"],
            ["driver", "address", "channel", "role", "capabilities"],
        )
    else:
        return data
    # return str(value)


def format_obj(obj, headers, attrs):
    rows = [html.Tr(children=[html.Th(h) for h in headers])]
    for k, v in obj.items():
        row = [html.Td(str(v[i])) for i in attrs]
        rows.append(html.Tr(children=row))
    return html.Table(children=rows, className="stgrp")

# title = html.H1(children="tomato pipelines")
# reload = html.Button("Reload", id="reload-pips")
# pipdiv = html.Div([dcc.Tabs(id="piptabs", children=[]), html.Div(id="pip")])


app.layout = [header, content]


# @callback(
#    Output("piptabs", "children"),
#    Input("reload-pips", "n_clicks"),
# )
def refresh_pipelines(val):
    ret = tomato.status(stgrp="pipelines", **kwargs)
    if not ret.success:
        return []
    pips = []
    for k, v in ret.data.items():
        pips.append(dcc.Tab(label=k, value=k))
    return pips


# @callback(
#    Output("pip", "children"),
#    Input("piptabs", "value"),
# )
def render_content(tab):
    ret = tomato.status(stgrp="pipelines", **kwargs)
    if not ret.success:
        return html.Div([html.P(f"Failure: {ret.msg}")])
    if tab == "tab-1":
        tab = next(iter(ret.data))
    if tab not in ret.data:
        return html.Div([html.P(f"Failure: {ret.data.keys()} {tab=}")])
    pip = ret.data[tab]

    div = html.Div(
        [
            html.Div(
                [
                    html.P("Ready:"),
                    html.Img(src=f"assets/{'check' if pip.ready else 'cross'}.png"),
                ],
                id="pip-ready",
                style={"display": "inline-block", "padding": "1em"},
            ),
            html.Div(
                [
                    html.P("Job:"),
                    html.Img(
                        src=f"assets/{'stop' if pip.jobid is None else 'play'}.png"
                    ),
                ],
                id="pip-job",
                style={"display": "inline-block", "padding": "1em"},
            ),
            html.Div(
                [
                    html.P("Sample ID:"),
                    html.P(pip.sampleid),
                ],
                id="pip-sampleid",
                style={"display": "inline-block", "padding": "1em"},
            ),
            html.Div(
                [
                    html.P(f"{pip=}"),
                ],
                id="pip-text",
            ),
        ]
    )

    return div


if __name__ == "__main__":
    app.run(debug=True)
