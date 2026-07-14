import dash
from dash import html, dcc, callback, Input, State, Output, MATCH
from tomato import passata, tomato
import zmq
import json
import xarray as xr
import plotly.express as px
from datetime import datetime
import pint

# ZeroMQ Context Setup
CTXT = zmq.Context()
TOUT = 1000
kwargs = dict(timeout=TOUT, context=CTXT)

dash.register_page(__name__, path_template="/components/<port>/<name>")

def get_field(obj, field, default=None):
    """Safely gets a field from an Attr object or dict."""
    if hasattr(obj, field):
        return getattr(obj, field)
    elif isinstance(obj, dict):
        return obj.get(field, default)
    return default

def clean_value(val):
    """Coerces Pint Quantity objects and numpy types to standard serializable types."""
    if hasattr(val, "magnitude"):
        val = val.magnitude
    if hasattr(val, "m"):
        val = val.m
    if hasattr(val, "item") and callable(val.item):
        try:
            val = val.item()
        except Exception:
            pass
    return val

def clean_dict_values(d):
    if isinstance(d, dict):
        return {k: clean_dict_values(v) for k, v in d.items()}
    elif isinstance(d, list):
        return [clean_dict_values(v) for v in d]
    elif isinstance(d, tuple):
        return tuple(clean_dict_values(v) for v in d)
    else:
        return clean_value(d)


def get_unit_str(units):
    """Formats unit names for human-friendly display."""
    if units is None or units == "":
        return ""
    try:
        q = pint.Quantity(1, units)
        return f"{q.units:~H}"
    except Exception:
        return str(units)

def layout(port: int, name: str, **_):
    port = int(port)
    
    # Safely fetch initial state of the component
    try:
        status_ret = passata.status(**kwargs, port=port, name=name)
        running = status_ret.data["running"] if (status_ret and status_ret.success) else False
    except Exception:
        running = False

    try:
        attrs_ret = passata.attrs(**kwargs, port=port, name=name)
        attrs_dict = attrs_ret.data if (attrs_ret and attrs_ret.success) else {}
    except Exception:
        attrs_dict = {}

    try:
        avals_ret = passata.get_attrs(**kwargs, port=port, name=name, attrs=list(attrs_dict.keys()))
        avals_dict = avals_ret.data if (avals_ret and avals_ret.success) else {}
    except Exception:
        avals_dict = {}

    # Initialize store datasets
    init_attrs_vals = {}
    init_attrs_units = {}
    init_attrs_rw = {}
    
    for k, v in attrs_dict.items():
        val = avals_dict.get(k)
        unit = get_field(v, "units")
        init_attrs_vals[k] = clean_value(val)
        init_attrs_units[k] = unit
        init_attrs_rw[k] = get_field(v, "rw", False)

    # Status Badge
    status_badge_class = "badge badge-success" if running else "badge badge-danger"
    status_text = "RUNNING" if running else "IDLE"

    header = html.Div(
        children=[
            html.Div(
                children=[
                    dcc.Link("← Back to Components", href="/components", className="btn inline-block", style={"margin-right": "20px", "text-decoration": "none", "background-color": "var(--accent-color)", "color": "white", "padding": "8px 16px", "border-radius": "4px"}),
                    html.H2(f"Component: {name}", className="inline", style={"margin": 0, "font-size": "22px"}),
                    html.Span(status_text, id="component-status-badge", className=status_badge_class, style={"margin-left": "15px"}),
                ],
                style={"display": "flex", "align-items": "center"}
            )
        ],
        className="theme-header",
    )

    # Build attribute row layout
    attr_rows = []
    for k, v in attrs_dict.items():
        is_rw = get_field(v, "rw", False)
        unit = get_field(v, "units")
        unit_str = get_unit_str(unit)
        options = get_field(v, "options")
        val = init_attrs_vals.get(k)
        
        # Build widget based on read-write / options
        if is_rw:
            if options:
                control = dcc.Dropdown(
                    id={"type": "component-attr-input", "index": k},
                    options=list(options),
                    value=val,
                    clearable=False,
                    className="parameter-control mutable-input"
                )
            else:
                control = dcc.Input(
                    id={"type": "component-attr-input", "index": k},
                    type="text",
                    value=val,
                    debounce=True,
                    className="parameter-control mutable-input"
                )
        else:
            control = dcc.Input(
                id={"type": "component-attr-readonly", "index": k},
                value=str(val) if val is not None else "N/A",
                disabled=True,
                className="parameter-control immutable-input"
            )
            
        # Display constraints helper
        min_val = get_field(v, "minimum")
        max_val = get_field(v, "maximum")
        constraints = []
        if min_val is not None:
            constraints.append(f"min: {clean_value(min_val)}")
        if max_val is not None:
            constraints.append(f"max: {clean_value(max_val)}")
        constraints_str = f" ({', '.join(constraints)})" if constraints else ""

        if is_rw:
            apply_btn = html.Button(
                "Apply",
                id={"type": "component-attr-apply-btn", "index": k},
                className="parameter-apply-btn"
            )
            attr_rows.append(
                html.Div(
                    children=[
                        html.Div(f"{k}:", className="parameter-label"),
                        control,
                        apply_btn,
                        html.Span(f" {unit_str}{constraints_str}", className="parameter-unit"),
                    ],
                    className="parameter-row"
                )
            )
        else:
            attr_rows.append(
                html.Div(
                    children=[
                        html.Div(f"{k}:", className="parameter-label"),
                        control,
                        html.Span(f" {unit_str}{constraints_str}", className="parameter-unit"),
                    ],
                    className="parameter-row"
                )
            )

    attrs_card = html.Div(
        children=[
            html.H3("Attributes & Controls", style={"margin-top": 0, "border-bottom": "1px solid var(--border-color)", "padding-bottom": "10px"}),
            html.Div(children=attr_rows if attr_rows else [html.Div("No registered attributes found.", className="text-secondary")], id="component-attrs-container"),
        ],
        className="card component-attrs"
    )

    # Build graphing card
    graph_card = html.Div(
        children=[
            html.H3("Data Graph", style={"margin-top": 0, "border-bottom": "1px solid var(--border-color)", "padding-bottom": "10px"}),
            html.Div(
                children=[
                    html.Label("Select Data Variables:", style={"margin-right": "10px", "font-weight": "500"}),
                    dcc.Dropdown(
                        id="component-data-dropdown",
                        multi=True,
                        clearable=True,
                        placeholder="Default (All variables)",
                        style={"width": "100%", "margin-top": "5px", "margin-bottom": "15px"}
                    ),
                ],
                className="block",
            ),
            dcc.Graph(id="component-data-graph"),
        ],
        className="card component-data"
    )

    # Action bar for measurement config
    footer_bar = html.Div(
        className="measurement-bar",
        children=[
            html.Div(
                className="measurement-section",
                children=[
                    html.Button("Manual Measurement (Measure)", id="component-measure-button"),
                ]
            ),
            html.Div(className="measurement-divider"),
            html.Div(
                className="measurement-section",
                children=[
                    html.Span("Auto Measure:", style={"font-weight": "600"}),
                    dcc.Input(
                        value=2,
                        type="number",
                        id="component-automeasure-delay",
                        debounce=True,
                        style={"width": "70px"}
                    ),
                    html.Span("seconds interval", className="text-secondary"),
                    dcc.Checklist(
                        options=[{"label": "Auto Measure Active", "value": "auto"}],
                        id="component-automeasure-button",
                        className="dash-checklist"
                    ),
                ]
            )
        ]
    )

    layout_children = [
        # Dashboard Stores
        dcc.Store(id="tomato-port-store", data=port),
        dcc.Store(id="component-name-store", data=name),
        dcc.Store(id="component-data-store", data=None),
        dcc.Store(id="component-attrs-vals-store", data=init_attrs_vals),
        dcc.Store(id="component-attrs-units-store", data=init_attrs_units),
        dcc.Store(id="component-attrs-rw-store", data=init_attrs_rw),
        dcc.Interval(id="component-interval", interval=2000),
        dcc.Interval(id="component-automeasure-interval", interval=2000, disabled=True),
        
        header,
        html.Div(
            children=[attrs_card, graph_card],
            className="component-grid"
        ),
        footer_bar
    ]
    
    return layout_children


# Callbacks for Theme Support removed to app.py to avoid duplicates


# Periodic updates for Store values
@callback(
    Output("component-attrs-vals-store", "data"),
    Output("component-status-badge", "children"),
    Output("component-status-badge", "className"),
    Input("component-interval", "n_intervals"),
    State("tomato-port-store", "data"),
    State("component-name-store", "data"),
    State("component-attrs-vals-store", "data"),
    State("component-attrs-units-store", "data"),
    prevent_initial_call=True,
)
def periodic_attrs_update(_, port, name, current_vals, units_dict):
    try:
        status_ret = passata.status(**kwargs, port=port, name=name)
        running = status_ret.data["running"] if (status_ret and status_ret.success) else False
    except Exception:
        running = False
        
    try:
        avals_ret = passata.get_attrs(**kwargs, port=port, name=name, attrs=list(current_vals.keys()))
        avals_dict = avals_ret.data if (avals_ret and avals_ret.success) else {}
    except Exception:
        avals_dict = {}

    new_vals = {}
    for k in current_vals.keys():
        val = avals_dict.get(k)
        new_vals[k] = clean_value(val)

    status_badge_class = "badge badge-success" if running else "badge badge-danger"
    status_text = "RUNNING" if running else "IDLE"

    return new_vals, status_text, status_badge_class


# UI displays updates from Stores
@callback(
    Output({"type": "component-attr-readonly", "index": MATCH}, "children"),
    Input("component-attrs-vals-store", "data"),
    State({"type": "component-attr-readonly", "index": MATCH}, "id"),
    prevent_initial_call=True,
)
def update_readonly_attr(vals, id):
    k = id["index"]
    val = vals.get(k)
    return str(val) if val is not None else "N/A"

# Input handler for read-write attribute updates via Apply button
@callback(
    Output({"type": "component-attr-input", "index": MATCH}, "value"),
    Input({"type": "component-attr-apply-btn", "index": MATCH}, "n_clicks"),
    State({"type": "component-attr-input", "index": MATCH}, "value"),
    State({"type": "component-attr-input", "index": MATCH}, "id"),
    State("tomato-port-store", "data"),
    State("component-name-store", "data"),
    prevent_initial_call=True,
)
def set_component_attribute(n_clicks, value, id, port, name):
    if n_clicks is None:
        return dash.no_update
    k = id["index"]
    try:
        ret = passata.set_attr(**kwargs, port=port, name=name, attr=k, val=value)
        if not ret.success:
            current = passata.get_attrs(**kwargs, port=port, name=name, attrs=[k]).data.get(k)
            return clean_value(current)
    except Exception:
        try:
            current = passata.get_attrs(**kwargs, port=port, name=name, attrs=[k]).data.get(k)
            return clean_value(current)
        except Exception:
            return dash.no_update
    return value


# Measure button and Automeasure intervals callbacks
@callback(
    Input("component-measure-button", "n_clicks"),
    Input("component-automeasure-interval", "n_intervals"),
    State("tomato-port-store", "data"),
    State("component-name-store", "data"),
    prevent_initial_call=True,
)
def component_measure(n_clicks, n_intervals, port, name):
    try:
        passata.measure(port=port, name=name, **kwargs)
    except Exception:
        pass


@callback(
    Output("component-automeasure-interval", "interval"),
    Input("component-automeasure-delay", "value"),
)
def component_automeasure_delay(value):
    if value is None or value <= 0:
        return 2000
    return value * 1000


@callback(
    Output("component-automeasure-interval", "disabled"),
    Input("component-automeasure-button", "value"),
)
def component_automeasure_toggle(value):
    if value is None or len(value) == 0:
        return True
    return False


# Data Store Updater
@callback(
    Output("component-data-store", "data"),
    State("tomato-port-store", "data"),
    State("component-name-store", "data"),
    State("component-data-store", "data"),
    Input("component-interval", "n_intervals"),
)
def component_data_update(port, name, data, n_intervals):
    try:
        ret = passata.get_last_data(**kwargs, port=port, name=name)
        if not ret.success:
            return data
        if data is None:
            ndata = ret.data
        else:
            odata = xr.Dataset.from_dict(data)
            ndata = xr.merge([odata, ret.data])
        return clean_dict_values(ndata.to_dict())
    except Exception:
        return data


# Dropdown key compiler
@callback(
    Output("component-data-dropdown", "options"),
    Input("component-data-store", "data"),
)
def component_data_dropdown(data: dict | None):
    if data is None:
        return []
    return list(data["data_vars"].keys())


# Plotly Graph Constructor with Local Time and Theme support
@callback(
    Output("component-data-graph", "figure"),
    Input("component-data-dropdown", "value"),
    Input("component-data-store", "data"),
    Input("app-theme-store", "data"),
)
def component_data_graph(keys, ds, theme):
    if ds is None:
        return {}
    if keys is None or len(keys) == 0:
        keys = list(ds["data_vars"].keys())
    
    # Formatting Unix timestamp (uts) to local timezone
    raw_x = ds["coords"]["uts"]["data"]
    formatted_x = []
    for t in raw_x:
        try:
            formatted_x.append(datetime.fromtimestamp(t).strftime('%Y-%m-%d %H:%M:%S'))
        except Exception:
            formatted_x.append(t)

    data = []
    for key in keys:
        data.append(
            {
                "x": formatted_x,
                "y": ds["data_vars"][key]["data"],
                "name": key,
                "type": "scatter",
                "mode": "lines+markers"
            }
        )
        
    layout = {
        "uirevision": True,
        "template": "plotly_dark" if theme == "dark" else "plotly",
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"color": "#ffffff" if theme == "dark" else "#212529"},
        "xaxis": {
            "gridcolor": "rgba(255,255,255,0.08)" if theme == "dark" else "rgba(0,0,0,0.08)",
            "title": "Time (Local)",
            "tickangle": -30
        },
        "yaxis": {
            "gridcolor": "rgba(255,255,255,0.08)" if theme == "dark" else "rgba(0,0,0,0.08)"
        },
        "margin": {"t": 30, "b": 80, "l": 50, "r": 20},
    }
    return {"data": data, "layout": layout}

