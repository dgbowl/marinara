import dash
from dash import html, dcc, callback, Input, State, Output, MATCH
from tomato import passata
import zmq
import xarray as xr
import logging
from datetime import datetime, timezone
from marinara.utils import (
    get_field,
    clean_value,
    clean_data,
    get_unit_str,
    format_constraint,
)

logger = logging.getLogger(__name__)

# ZeroMQ Context Setup
CTXT = zmq.Context()
TOUT = 1000
kwargs = dict(timeout=TOUT, context=CTXT)

dash.register_page(__name__, path_template="/components/<port>/<name>")


def layout(port: int, name: str, **_):
    port = int(port)

    # Safely fetch initial state of the component
    try:
        status_ret = passata.status(**kwargs, port=port, name=name)
        running = status_ret.data["running"] if status_ret.success else False
    except Exception as e:
        logger.warning(f"Failed to fetch initial status for component {name}: {e}")
        running = False

    try:
        attrs_ret = passata.attrs(**kwargs, port=port, name=name)
        attrs_dict = attrs_ret.data if attrs_ret.success else {}
    except Exception as e:
        logger.warning(f"Failed to fetch attributes for component {name}: {e}")
        attrs_dict = {}

    try:
        avals_ret = passata.get_attrs(
            **kwargs, port=port, name=name, attrs=list(attrs_dict.keys())
        )
        avals_dict = avals_ret.data if avals_ret.success else {}
    except Exception as e:
        logger.warning(f"Failed to fetch attribute values for component {name}: {e}")
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
    if isinstance(running, bool):
        running_bool = running
        task_name = None
    else:
        running_bool = bool(running)
        if isinstance(running, dict):
            task_name = running.get("technique_name")
        else:
            task_name = getattr(running, "technique_name", None)

    status_badge_class = (
        "badge badge-success" if running_bool else "badge badge-secondary"
    )
    status_text = (
        f"RUNNING ({task_name})"
        if task_name
        else ("RUNNING" if running_bool else "STOPPED")
    )

    header = html.Div(
        children=[
            html.Div(
                children=[
                    dcc.Link(
                        "← Back to Components",
                        href="/components",
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
                        f"Component: {name}",
                        className="inline",
                        style={"margin": 0, "font-size": "22px"},
                    ),
                    html.Span(
                        status_text,
                        id="component-status-badge",
                        className=status_badge_class,
                        style={"margin-left": "15px"},
                    ),
                ],
                style={"display": "flex", "align-items": "center"},
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
                    options=sorted(list(options)),
                    value=val,
                    clearable=False,
                    className="attr-control mutable-input",
                )
            else:
                control = dcc.Input(
                    id={"type": "component-attr-input", "index": k},
                    type="text",
                    value=val,
                    debounce=True,
                    className="attr-control mutable-input",
                )
        else:
            control = dcc.Input(
                id={"type": "component-attr-readonly", "index": k},
                value=str(val) if val is not None else "N/A",
                disabled=True,
                className="attr-control immutable-input",
            )

        # Display constraints helper
        min_val = get_field(v, "minimum")
        max_val = get_field(v, "maximum")
        constraints = []
        if min_val is not None:
            constraints.append(f"min: {format_constraint(min_val, unit)}")
        if max_val is not None:
            constraints.append(f"max: {format_constraint(max_val, unit)}")
        constraints_str = f" ({', '.join(constraints)})" if constraints else ""

        if is_rw:
            apply_btn = html.Button(
                "Apply",
                id={"type": "component-attr-apply-btn", "index": k},
                className="attr-apply-btn",
            )
            attr_rows.append(
                html.Div(
                    children=[
                        html.Div(f"{k}:", className="attr-label"),
                        control,
                        apply_btn,
                        html.Span(
                            f" {unit_str}{constraints_str}", className="attr-unit"
                        ),
                    ],
                    className="attr-row",
                )
            )
        else:
            attr_rows.append(
                html.Div(
                    children=[
                        html.Div(f"{k}:", className="attr-label"),
                        control,
                        html.Span(
                            f" {unit_str}{constraints_str}", className="attr-unit"
                        ),
                    ],
                    className="attr-row",
                )
            )

    attrs_card = html.Div(
        children=[
            html.H3(
                "Attributes & Controls",
                style={
                    "margin-top": 0,
                    "border-bottom": "1px solid var(--border-color)",
                    "padding-bottom": "10px",
                },
            ),
            html.Div(
                children=attr_rows
                if attr_rows
                else [
                    html.Div(
                        "No registered attributes found.", className="text-secondary"
                    )
                ],
                id="component-attrs-container",
            ),
        ],
        className="card component-attrs",
    )

    # Build graphing card
    graph_card = html.Div(
        children=[
            html.Div(
                children=[
                    html.H3("Data Graph", style={"margin": 0}),
                    dcc.Checklist(
                        options=[
                            {
                                "label": " Align start at t=0 (Relative)",
                                "value": "relative",
                            }
                        ],
                        value=[],
                        id="checkbox-align-time",
                        style={
                            "margin-left": "auto",
                            "font-weight": "500",
                            "font-size": "14px",
                        },
                    ),
                ],
                style={
                    "display": "flex",
                    "align-items": "center",
                    "border-bottom": "1px solid var(--border-color)",
                    "padding-bottom": "10px",
                    "margin-bottom": "15px",
                },
            ),
            dcc.Graph(
                id="component-data-graph", style={"height": "400px"}, responsive=True
            ),
        ],
        className="card component-data",
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
        header,
        html.Div(children=[attrs_card, graph_card], className="component-grid"),
    ]

    return layout_children


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
        running = status_ret.data["running"] if status_ret.success else False
    except Exception as e:
        logger.warning(f"Failed to fetch periodic status for component {name}: {e}")
        running = False

    try:
        avals_ret = passata.get_attrs(
            **kwargs, port=port, name=name, attrs=list(current_vals.keys())
        )
        avals_dict = avals_ret.data if avals_ret.success else {}
    except Exception as e:
        logger.warning(
            f"Failed to fetch periodic attribute values for component {name}: {e}"
        )
        avals_dict = {}

    new_vals = {}
    for k in current_vals.keys():
        val = avals_dict.get(k)
        new_vals[k] = clean_value(val)

    if isinstance(running, bool):
        running_bool = running
        task_name = None
    else:
        running_bool = bool(running)
        if isinstance(running, dict):
            task_name = running.get("technique_name")
        else:
            task_name = getattr(running, "technique_name", None)

    status_badge_class = (
        "badge badge-success" if running_bool else "badge badge-secondary"
    )
    status_text = (
        f"RUNNING ({task_name})"
        if task_name
        else ("RUNNING" if running_bool else "STOPPED")
    )

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
        if ret.success:
            return clean_value(ret.data)
        # If set_attr returned success=False, fetch current value to revert
        current = passata.get_attrs(**kwargs, port=port, name=name, attrs=[k]).data.get(
            k
        )
        return clean_value(current)
    except Exception as e:
        logger.warning(f"Failed to set attribute {k} on component {name}: {e}")
        try:
            current = passata.get_attrs(
                **kwargs, port=port, name=name, attrs=[k]
            ).data.get(k)
            return clean_value(current)
        except Exception:
            return dash.no_update


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
        # Cap dataset size to prevent JSON serialization and memory bottlenecks
        if ndata.sizes["uts"] > 500:
            ndata = ndata.isel(uts=slice(-500, None))
        return clean_data(ndata.to_dict())
    except Exception as e:
        logger.warning(f"Failed to fetch last data for component {name}: {e}")
        return data


# Plotly Graph Constructor with Local Time and Theme support
@callback(
    Output("component-data-graph", "figure"),
    Input("component-data-store", "data"),
    Input("app-theme-store", "data"),
    Input("checkbox-align-time", "value"),
)
def component_data_graph(ds, theme, align_time):
    if ds is None:
        return {}
    keys = list(ds["data_vars"].keys())

    # Formatting Unix timestamp (uts) to local timezone or relative time
    raw_x = ds["coords"]["uts"]["data"]

    if align_time and "relative" in align_time:
        start_t = raw_x[0] if len(raw_x) > 0 else 0
        formatted_x = []
        for t in raw_x:
            try:
                formatted_x.append(f"+{round(t - start_t, 1)}s")
            except Exception:
                formatted_x.append(t)
        x_title = "Relative Time (Seconds)"
    else:
        formatted_x = []
        for t in raw_x:
            try:
                formatted_x.append(
                    datetime.fromtimestamp(t, timezone.utc)
                    .astimezone()
                    .strftime("%Y-%m-%d %H:%M:%S")
                )
            except Exception:
                formatted_x.append(t)
        x_title = "Time (Local)"

    data = []
    for key in keys:
        y_raw = ds["data_vars"][key]["data"]
        is_multidimensional = False
        if len(y_raw) > 0 and isinstance(y_raw[0], (list, tuple)):
            is_multidimensional = True

        if is_multidimensional:
            max_len = max(
                len(item) for item in y_raw if isinstance(item, (list, tuple))
            )
            for i in range(max_len):
                sub_y = []
                for item in y_raw:
                    if isinstance(item, (list, tuple)) and i < len(item):
                        sub_y.append(item[i])
                    else:
                        sub_y.append(None)
                data.append(
                    {
                        "x": formatted_x,
                        "y": sub_y,
                        "name": f"{key}[{i}]",
                        "type": "scatter",
                        "mode": "lines+markers",
                    }
                )
        else:
            data.append(
                {
                    "x": formatted_x,
                    "y": y_raw,
                    "name": key,
                    "type": "scatter",
                    "mode": "lines+markers",
                }
            )

    layout = {
        "autosize": True,
        "uirevision": True,
        "template": "plotly_dark" if theme == "dark" else "plotly",
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"color": "#ffffff" if theme == "dark" else "#212529"},
        "xaxis": {
            "gridcolor": "rgba(255,255,255,0.08)"
            if theme == "dark"
            else "rgba(0,0,0,0.08)",
            "title": x_title,
            "tickangle": -30,
        },
        "yaxis": {
            "gridcolor": "rgba(255,255,255,0.08)"
            if theme == "dark"
            else "rgba(0,0,0,0.08)"
        },
        "margin": {"t": 30, "b": 80, "l": 50, "r": 20},
    }
    return {"data": data, "layout": layout}
