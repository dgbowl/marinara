import dash
from dash import html, dcc, callback, Input, State, Output
from tomato import passata, tomato
import zmq
import json
import xarray as xr
import plotly.express as px

CTXT = zmq.Context()
TOUT = 1000
kwargs = dict(timeout=TOUT, context=CTXT)
dash.register_page(__name__, path_template="/components/<port>/<name>")


@callback(
    Input("component-measure-button", "n_clicks"),
    Input("component-automeasure-interval", "n_intervals"),
    State("tomato-port-store", "data"),
    State("component-name-store", "data"),
)
def component_measure(n_clicks, n_intervals, port, name):
    passata.measure(port=port, name=name, **kwargs)


@callback(
    Output("component-running-div", "children"),
    State("tomato-port-store", "data"),
    State("component-name-store", "data"),
    Input("component-interval", "n_intervals"),
)
def component_running(port, name, n_intervals):
    ret = passata.status(**kwargs, port=port, name=name)
    if ret.success:
        return str(ret.data["running"])
    else:
        return ret.msg


@callback(
    Output("component-automeasure-interval", "interval"),
    Input("component-automeasure-delay", "value"),
)
def component_automeasure_delay(value):
    return value * 1000


@callback(
    Output("component-automeasure-interval", "disabled"),
    Input("component-automeasure-button", "value"),
)
def component_automeasure_toggle(value):
    if value is None or len(value) == 0:
        return True
    else:
        return False


@callback(
    Output("component-attrs-div", "children"),
    State("tomato-port-store", "data"),
    State("component-name-store", "data"),
    Input("component-interval", "n_intervals"),
)
def component_attrs(port, name, n_intervals):
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
    Output("component-data-store", "data"),
    State("tomato-port-store", "data"),
    State("component-name-store", "data"),
    State("component-data-store", "data"),
    Input("component-interval", "n_intervals"),
)
def component_data_update(port, name, data, n_intervals):
    ret = passata.get_last_data(**kwargs, port=port, name=name)
    if not ret.success:
        return None
    if data is None:
        ndata = ret.data
    else:
        odata = xr.Dataset.from_dict(data)
        ndata = xr.merge([odata, ret.data])
    return ndata.to_dict()


@callback(
    Output("component-data-dropdown", "options"),
    Input("component-data-store", "data"),
)
def component_data_dropdown(data: dict | None):
    if data is None:
        return []
    return list(data["data_vars"].keys())


@callback(
    Output("component-data-graph", "figure"),
    Input("component-data-dropdown", "value"),
    Input("component-data-store", "data"),
)
def component_data(keys, ds):
    if ds is None:
        return None
    if keys is None or len(keys) == 0:
        keys = list(ds["data_vars"].keys())
    data = []
    for key in keys:
        data.append(
            {
                "x": ds["coords"]["uts"]["data"],
                "y": ds["data_vars"][key]["data"],
                "name": key,
            }
        )
    return {"data": data, "layout": {"uirevision": True}}


def layout(port: int, name: str, **_):
    port = int(port)
    header = html.Div(
        children=[
            html.Div(f"The user requested component {name=} on {port=}"),
            dcc.Store(id="tomato-port-store", data=port),
            dcc.Store(id="component-name-store", data=name),
            dcc.Store(id="component-data-store", data=None),
            dcc.Interval(id="component-interval", interval=2000),
            dcc.Interval(
                id="component-automeasure-interval", interval=2000, disabled=True
            ),
        ]
    )
    content = html.Table(
        children=[
            html.Tr(
                children=[
                    html.Td("Running:"),
                    html.Td(id="component-running-div"),
                ]
            ),
            html.Tr(
                children=[
                    html.Td("Attrs:"),
                    html.Td(id="component-attrs-div"),
                ]
            ),
            html.Tr(
                children=[
                    html.Td("Data:"),
                    html.Td(
                        children=[
                            dcc.Dropdown(
                                id="component-data-dropdown",
                                multi=True,
                                clearable=True,
                                placeholder="all data_vars",
                            ),
                            dcc.Graph(id="component-data-graph"),
                        ]
                    ),
                ]
            ),
        ]
    )
    footer = html.Div(
        [
            html.Button("Measure", id="component-measure-button"),
            html.Div(
                [
                    "Measurement Frequency:",
                    dcc.Input(
                        value=2,
                        type="number",
                        id="component-automeasure-delay",
                        debounce=True,
                    ),
                    dcc.Checklist(
                        options=["Auto Measure"],
                        id="component-automeasure-button",
                        inline=True,
                    ),
                ]
            ),
        ]
    )

    return [header, content, footer]


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
