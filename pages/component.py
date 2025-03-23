import dash
from dash import html, dcc, callback, Input, State, Output
from tomato import passata, tomato
import zmq
import json

CTXT = zmq.Context()
TOUT = 1000
kwargs = dict(timeout=TOUT, context=CTXT)
dash.register_page(__name__, path_template="/components/<port>/<name>")


@callback(
    Input("component-measure", "n_clicks"),
    State("tomato-port", "data"),
    State("component-name", "data"),
)
def component_measure(n_clicks, port, name):
    passata.measure(port=port, name=name, **kwargs)


@callback(
    Output("component-running", "children"),
    Input("tomato-port", "data"),
    State("component-name", "data"),
)
def component_running(port, name):
    ret = passata.status(**kwargs, port=port, name=name)
    if ret.success:
        return str(ret.data["running"])
    else:
        return ret.msg


@callback(
    Output("component-attrs", "children"),
    Input("tomato-port", "data"),
    State("component-name", "data"),
)
def component_attrs(port, name):
    ret = passata.attrs(**kwargs, port=port, name=name)
    if ret.success:
        attrs = []
        for k, v in ret.data.items():
            val = passata.get_attrs(**kwargs, port=port, name=name, attrs=[k])
            attrs.append(
                html.Tr(
                    children=[html.Td(k), html.Td(str(val.data[k])), html.Td(str(v))]
                )
            )
        return attrs


@callback(
    Output("component-data", "children"),
    Input("tomato-port", "data"),
    State("component-name", "data"),
)
def component_data(port, name):
    ret = passata.get_last_data(**kwargs, port=port, name=name)
    if ret.success:
        return str(ret.data)
    else:
        return ret.msg


def layout(port: int, name: str, **_):
    port = int(port)
    header = html.Div(
        children=[
            html.Div(f"The user requested component {name=} on {port=}"),
            dcc.Store(id="tomato-port", data=port),
            dcc.Store(id="component-name", data=name),
        ]
    )
    content = html.Table(
        children=[
            html.Tr(
                children=[
                    html.Td("Running:"),
                    html.Td(id="component-running"),
                ]
            ),
            html.Tr(
                children=[
                    html.Td("Attrs:"),
                    html.Td(id="component-attrs"),
                ]
            ),
            html.Tr(
                children=[
                    html.Td("Data:"),
                    html.Td(id="component-data"),
                ]
            ),
        ]
    )
    measure = html.Button("Measure", id="component-measure")

    return [header, content, measure]


if False:
    rows = []
    ret = passata.status(**kwargs, port=port, name=name)
    if ret.success:
        rows.append(
            html.Tr(children=[html.Td("Running:"), html.Td(str(ret.data["running"]))])
        )
    ret = passata.attrs(**kwargs, port=port, name=name)
    if ret.success:
        attrs = []
        for k, v in ret.data.items():
            val = passata.get_attrs(**kwargs, port=port, name=name, attrs=[k])

            attrs.append(
                html.Tr(
                    children=[html.Td(k), html.Td(str(val.data[k])), html.Td(str(v))]
                )
            )
        rows.append(html.Tr(children=[html.Td("Attrs:"), html.Td(children=attrs)]))
    ret = passata.get_last_data(**kwargs, port=port, name=name)
    if ret.success:
        rows.append(html.Tr(children=[html.Td("Data:"), str(ret.data)]))
    else:
        rows.append(html.Tr(children=[html.Td("Data:"), ret.msg]))

    content = html.Table(children=rows)

    # body = html.Div(ret)
