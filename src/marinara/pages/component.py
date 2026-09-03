import logging
from datetime import UTC, datetime

import dash
import xarray as xr
from dash import ALL, MATCH, Input, Output, State, callback, dcc, html
from tomato import passata

from marinara.utils import (
    clean_data,
    clean_value,
    format_constraint,
    get_field,
    get_unit_str,
    kwargs,
)

logger = logging.getLogger(__name__)
dash.register_page(__name__, path_template="/components/<port>/<name>")


def layout(port: int, name: str, **_):
    port = int(port)

    # Safely fetch initial state of the component
    try:
        status_ret = passata.status(**kwargs, port=port, name=name)
        running = status_ret.data["running"] if status_ret.success else False
    except Exception as e:
        logger.warning("Exception during passata.status:", exc_info=e)
        running = False

    try:
        attrs_ret = passata.attrs(**kwargs, port=port, name=name)
        attrs_dict = attrs_ret.data if attrs_ret.success else {}
    except Exception as e:
        logger.warning("Exception during passata.attrs:", exc_info=e)
        attrs_dict = {}

    try:
        avals_ret = passata.get_attrs(
            **kwargs, port=port, name=name, attrs=list(attrs_dict.keys())
        )
        avals_dict = avals_ret.data if avals_ret.success else {}
    except Exception as e:
        logger.warning("Exception during passata.get_attrs:", exc_info=e)
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
                    options=sorted(options),
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

    custom_graphs_header = html.Div(
        children=[
            html.H3("Custom Graphs", style={"margin": 0}),
            html.Button(
                "+ Add Graph",
                id="add-graph-btn",
                className="btn",
                style={
                    "margin-left": "auto",
                    "background-color": "#10b981",
                    "color": "white",
                    "border": "none",
                    "padding": "8px 16px",
                    "border-radius": "4px",
                    "cursor": "pointer",
                    "font-weight": "600",
                },
            ),
        ],
        style={
            "display": "flex",
            "align-items": "center",
            "margin-bottom": "20px",
            "border-bottom": "1px solid var(--border-color)",
            "padding-bottom": "10px",
            "margin-top": "20px",
        },
    )

    layout_children = [
        # Dashboard Stores
        dcc.Store(id="tomato-port-store", data=port),
        dcc.Store(id="component-name-store", data=name),
        dcc.Store(id="component-data-store", data=None),
        dcc.Store(id="component-attrs-vals-store", data=init_attrs_vals),
        dcc.Store(id="component-attrs-units-store", data=init_attrs_units),
        dcc.Store(id="component-attrs-rw-store", data=init_attrs_rw),
        dcc.Store(id="custom-graphs-list-store", data=[1]),
        dcc.Store(id="custom-graphs-counter-store", data=2),
        dcc.Store(id="custom-graphs-titles-store", data={}),
        dcc.Interval(id="component-interval", interval=2000),
        header,
        # Row 1: Attributes & Controls (Left) and Data Graph (Right)
        html.Div(
            children=[attrs_card, graph_card],
            className="component-grid",
            style={"margin-bottom": "20px"},
        ),
        # Row 2: Custom Graphs Section
        custom_graphs_header,
        html.Div(id="custom-graphs-container"),
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
        logger.warning("Exception during passata.status:", exc_info=e)
        running = False

    try:
        avals_ret = passata.get_attrs(
            **kwargs, port=port, name=name, attrs=list(current_vals.keys())
        )
        avals_dict = avals_ret.data if avals_ret.success else {}
    except Exception as e:
        logger.warning("Exception during passata.get_attrs:", exc_info=e)
        avals_dict = {}

    new_vals = {}
    for k in current_vals:
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
        logger.warning("Exception during passata.get_attrs:", exc_info=e)
        try:
            current = passata.get_attrs(
                **kwargs, port=port, name=name, attrs=[k]
            ).data.get(k)
            return clean_value(current)
        except Exception as e:
            logger.warning("Exception during passata.get_attrs:", exc_info=e)
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
        logger.warning("Exception during component_data_update:", exc_info=e)
        return data


# Plotly Graph Constructor with Local Time and Theme support
@callback(
    Output("component-data-graph", "figure"),
    Input("component-data-store", "data"),
    Input("app-theme-store", "data"),
    Input("checkbox-align-time", "value"),
)
def component_data_graph(ds, theme, align_time):
    if ds is None or True:
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
            except Exception as e:
                logger.warning("Exception during time formatting:", exc_info=e)
                formatted_x.append(t)
        x_title = "Relative Time (Seconds)"
    else:
        formatted_x = []
        for t in raw_x:
            try:
                formatted_x.append(
                    datetime.fromtimestamp(t, UTC)
                    .astimezone()
                    .strftime("%Y-%m-%d %H:%M:%S")
                )
            except Exception as e:
                logger.warning("Exception during time formatting:", exc_info=e)
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
        "legend": {
            "orientation": "h",
            "x": 0.5,
            "y": -0.22,
            "xanchor": "center",
            "yanchor": "top",
        },
        "margin": {"t": 30, "b": 100, "l": 50, "r": 20},
    }
    return {"data": data, "layout": layout}


# Manages adding and removing custom graphs
@callback(
    Output("custom-graphs-list-store", "data"),
    Output("custom-graphs-counter-store", "data"),
    Input("add-graph-btn", "n_clicks"),
    Input({"type": "custom-graph-remove-btn", "index": ALL}, "n_clicks"),
    State("custom-graphs-list-store", "data"),
    State("custom-graphs-counter-store", "data"),
    prevent_initial_call=True,
)
def manage_graphs(add_clicks, remove_clicks, active_ids, next_id):
    ctx = dash.callback_context
    if not ctx.triggered:
        return active_ids, next_id

    trigger_id = ctx.triggered[0]["prop_id"]

    if "add-graph-btn" in trigger_id:
        new_ids = active_ids + [next_id]
        return new_ids, next_id + 1
    else:
        import json

        try:
            trigger_info = json.loads(trigger_id.split(".")[0])
            remove_idx = trigger_info["index"]
            new_ids = [i for i in active_ids if i != remove_idx]
            return new_ids, next_id
        except Exception as e:
            logger.warning("Exception during manage_graphs:", exc_info=e)
            return active_ids, next_id


# Renders the dynamic custom graphs container children
@callback(
    Output("custom-graphs-container", "children"),
    Input("custom-graphs-list-store", "data"),
    State("custom-graphs-titles-store", "data"),
    State("component-data-store", "data"),
)
def render_graphs_list(active_ids, titles_dict, ds):
    if not active_ids:
        return html.Div(
            "No custom graphs added. Click '+ Add Graph' above to create one.",
            style={
                "text-align": "center",
                "padding": "30px",
                "color": "gray",
                "font-style": "italic",
                "border": "1px dashed var(--border-color)",
                "border-radius": "var(--radius)",
                "margin-top": "15px",
            },
        )

    titles_dict = titles_dict or {}
    vars_list = sorted(ds.get("data_vars", {}).keys()) if ds else []
    coords_list = [{"label": "Time (uts)", "value": "uts"}]

    graphs_layouts = []
    for idx, i in enumerate(active_ids):
        display_number = idx + 1
        graph_id_str = str(i)

        # Stored title or dynamic fallback based on display position
        title_val = titles_dict.get(graph_id_str, f"Custom Graph #{display_number}")

        card = html.Div(
            id={"type": "custom-graph-card", "index": i},
            children=[
                html.Div(
                    children=[
                        dcc.Input(
                            id={"type": "custom-graph-title-input", "index": i},
                            value=title_val,
                            type="text",
                            placeholder=f"Custom Graph #{display_number}",
                            className="custom-graph-title-input",
                            style={
                                "font-size": "16px",
                                "font-weight": "700",
                                "border": "none",
                                "border-bottom": "1px dashed var(--border-color)",
                                "background": "transparent",
                                "color": "var(--text-color)",
                                "padding": "2px 5px",
                                "width": "50%",
                                "outline": "none",
                            },
                        ),
                        html.Button(
                            "Remove",
                            id={"type": "custom-graph-remove-btn", "index": i},
                            className="btn",
                            style={
                                "margin-left": "auto",
                                "background-color": "#ef4444",
                                "color": "white",
                                "border": "none",
                                "padding": "4px 12px",
                                "border-radius": "4px",
                                "cursor": "pointer",
                                "font-size": "12px",
                                "font-weight": "600",
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
                # Dropdowns for X and Y selection
                html.Div(
                    children=[
                        html.Div(
                            children=[
                                html.Label(
                                    "X Axis Variable:",
                                    style={
                                        "font-weight": "600",
                                        "font-size": "13px",
                                        "margin-bottom": "5px",
                                        "display": "block",
                                        "color": "var(--text-color)",
                                    },
                                ),
                                dcc.Dropdown(
                                    id={"type": "custom-graph-x-selector", "index": i},
                                    options=coords_list,
                                    placeholder="Select variable",
                                    style={"width": "100%"},
                                ),
                            ],
                            style={"flex": "1", "min-width": "150px"},
                        ),
                        html.Div(
                            children=[
                                html.Label(
                                    "Y Axis Variables:",
                                    style={
                                        "font-weight": "600",
                                        "font-size": "13px",
                                        "margin-bottom": "5px",
                                        "display": "block",
                                        "color": "var(--text-color)",
                                    },
                                ),
                                dcc.Dropdown(
                                    id={"type": "custom-graph-y-selector", "index": i},
                                    options=[
                                        {"label": v, "value": v} for v in vars_list
                                    ],
                                    multi=True,
                                    placeholder="Select variables",
                                    style={"width": "100%"},
                                ),
                            ],
                            style={"flex": "2", "min-width": "250px"},
                        ),
                        html.Div(
                            children=[
                                html.Label(
                                    "Graph Options:",
                                    style={
                                        "font-weight": "600",
                                        "font-size": "13px",
                                        "margin-bottom": "5px",
                                        "display": "block",
                                        "color": "var(--text-color)",
                                    },
                                ),
                                dcc.Checklist(
                                    id={"type": "custom-graph-options", "index": i},
                                    options=[
                                        {
                                            "label": " Connect points (Lines)",
                                            "value": "lines",
                                        },
                                        {"label": " Sort by X-Axis", "value": "sort"},
                                    ],
                                    value=["lines"],
                                    labelStyle={
                                        "display": "inline-block",
                                        "margin-right": "15px",
                                        "font-size": "13px",
                                        "color": "var(--text-color)",
                                    },
                                    style={"padding": "6px 0"},
                                ),
                            ],
                            style={"flex": "1.5", "min-width": "250px"},
                        ),
                    ],
                    style={
                        "display": "flex",
                        "gap": "15px",
                        "flex-wrap": "wrap",
                        "margin-bottom": "20px",
                    },
                ),
                dcc.Graph(
                    id={"type": "custom-graph", "index": i},
                    style={"height": "400px"},
                    responsive=True,
                ),
            ],
            className="card component-data",
            style={"margin-bottom": "20px"},
        )
        graphs_layouts.append(card)

    return graphs_layouts


# Persists custom titles to the custom-graphs-titles-store when changed
@callback(
    Output("custom-graphs-titles-store", "data"),
    Input({"type": "custom-graph-title-input", "index": ALL}, "value"),
    State("custom-graphs-titles-store", "data"),
    prevent_initial_call=True,
)
def update_graph_titles(title_values, current_titles):
    ctx = dash.callback_context
    if not ctx.triggered:
        return current_titles

    new_titles = current_titles if current_titles else {}
    inputs_list = ctx.inputs_list[0]

    for inp, val in zip(inputs_list, title_values):
        graph_id = str(inp["id"]["index"])
        if val is not None:
            new_titles[graph_id] = val

    return new_titles


# Updates options of dynamic selectors as data streams in
@callback(
    Output({"type": "custom-graph-x-selector", "index": MATCH}, "options"),
    Output({"type": "custom-graph-y-selector", "index": MATCH}, "options"),
    Input("component-data-store", "data"),
)
def populate_dynamic_selectors(ds):
    if ds is None:
        return [], []
    vars_list = sorted(ds.get("data_vars", {}).keys())
    y_options = [{"label": v, "value": v} for v in vars_list]
    coords_list = sorted(ds.get("coords", {}).keys())
    x_options = [{"label": "Time (uts)", "value": "uts"}]
    for coord in coords_list:
        if coord != "uts":
            x_options.append({"label": coord, "value": coord})
    return x_options, y_options


# Renders custom graphs dynamically based on selected variables and options
@callback(
    Output({"type": "custom-graph", "index": MATCH}, "figure"),
    Input({"type": "custom-graph-x-selector", "index": MATCH}, "value"),
    Input({"type": "custom-graph-y-selector", "index": MATCH}, "value"),
    Input({"type": "custom-graph-options", "index": MATCH}, "value"),
    Input("component-data-store", "data"),
    Input("app-theme-store", "data"),
)
def render_custom_graph(x_var, y_var, options_val, ds, theme):
    y_vars = [y_var] if isinstance(y_var, str) else y_var
    if ds is None or not x_var or not y_vars:
        return {
            "layout": {
                "xaxis": {"visible": False},
                "yaxis": {"visible": False},
                "annotations": [
                    {
                        "text": "Select variables above to view custom plot",
                        "xref": "paper",
                        "yref": "paper",
                        "showarrow": False,
                        "font": {"size": 16, "color": "gray"},
                    }
                ],
                "paper_bgcolor": "rgba(0,0,0,0)",
                "plot_bgcolor": "rgba(0,0,0,0)",
                "template": "plotly_dark" if theme == "dark" else "plotly",
            }
        }

    # Fetch X data
    raw_x = ds["coords"][x_var]["data"]
    if x_var == "uts":
        x_data = []
        for t in raw_x:
            try:
                x_data.append(
                    datetime.fromtimestamp(t, UTC)
                    .astimezone()
                    .strftime("%Y-%m-%d %H:%M:%S")
                )
            except Exception as e:
                logger.warning("Exception during time formatting:", exc_info=e)
                x_data.append(t)
        x_title = "Time (Local)"
    else:
        x_data = raw_x
        x_title = x_var

    # Process selected Y variables
    if isinstance(y_var, str):
        y_vars = [y_var]
    else:
        y_vars = y_var

    # Consistency check
    for y_name in y_vars:
        y_dims = ds["data_vars"][y_name]["dims"]
        if x_var not in y_dims:
            return {
                "layout": {
                    "xaxis": {"visible": False},
                    "yaxis": {"visible": False},
                    "annotations": [
                        {
                            "text": f"The selected X axis variable {x_var!r} "
                            f"is not a coordinate of the Y axis variable {y_name!r}. "
                            f"Select an X axis variable out of: {y_dims!r}.",
                            "xref": "paper",
                            "yref": "paper",
                            "showarrow": False,
                            "font": {"size": 16, "color": "gray"},
                        }
                    ],
                    "paper_bgcolor": "rgba(0,0,0,0)",
                    "plot_bgcolor": "rgba(0,0,0,0)",
                    "template": "plotly_dark" if theme == "dark" else "plotly",
                }
            }

    # Format timestamps for hover text
    raw_uts = ds.get("coords", {}).get("uts", {}).get("data", [])
    formatted_times = []
    for t in raw_uts:
        try:
            formatted_times.append(
                datetime.fromtimestamp(t, UTC)
                .astimezone()
                .strftime("%Y-%m-%d %H:%M:%S")
            )
        except Exception as e:
            logger.warning("Exception during time formatting:", exc_info=e)
            formatted_times.append(str(t))

    # Handle sorting and lines connection options
    options_val = options_val or []
    connect_lines = "lines" in options_val
    sort_x = "sort" in options_val
    mode = "lines+markers" if connect_lines else "markers"

    fig_data = []
    y_titles = []

    for y_name in y_vars:
        y_raw = ds["data_vars"][y_name]["data"]
        y_dims = ds["data_vars"][y_name]["dims"]
        y_titles.append(y_name)

        # Simple 1-D plot
        if len(y_dims) == 1:
            fig_data.append(
                {
                    "x": x_data,
                    "y": y_raw,
                    "mode": mode,
                    "type": "scatter",
                    "marker": {"size": 8, "opacity": 0.8},
                    "hovertext": formatted_times,
                    "hovertemplate": "<b>Time: %{hovertext}</b><br>"
                    + f"{x_title}: %{{x}}<br>{y_name}: %{{y}}<extra></extra>",
                    "name": y_name,
                }
            )
        # Simple 1-D plot of the last datapoint
        elif len(y_dims) == 2 and x_var != "uts":
            fig_data.append(
                {
                    "x": x_data,
                    "y": y_raw[-1],
                    "mode": mode,
                    "type": "scatter",
                    "marker": {"size": 8, "opacity": 0.8},
                    "hovertext": formatted_times,
                    "hovertemplate": "<b>Time: %{hovertext}</b><br>"
                    + f"{x_title}: %{{x}}<br>{y_name}: %{{y}}<extra></extra>",
                    "name": y_name,
                }
            )
        elif len(y_dims) == 2:
            # figure out axis order
            if y_dims.index("uts") == 0:
                x_d = x_data
                y_d = ds["coords"][y_dims[1]]["data"]
                z_d = [i for i in zip(*y_raw)]
            else:
                x_d = ds["coords"][y_dims[0]]["data"]
                y_d = x_data
                z_d = y_raw

            fig_data.append(
                {
                    "x": x_d,
                    "y": y_d,
                    "z": z_d,
                    "type": "heatmap",
                    "hovertext": formatted_times,
                    "hovertemplate": "<b>Time: %{hovertext}</b><br>"
                    + f"{x_title}: %{{x}}<br>{y_name}: %{{y}}<extra></extra>",
                    "name": y_name,
                }
            )
        else:
            continue

    if len(y_titles) == 1:
        y_title = y_titles[0]
    elif len(y_titles) > 1:
        y_title = "Selected Variables"
    else:
        y_title = "Value"

    layout = {
        "autosize": True,
        "uirevision": f"{x_var}-{y_var}",
        "template": "plotly_dark" if theme == "dark" else "plotly",
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"color": "#ffffff" if theme == "dark" else "#212529"},
        "xaxis": {
            "gridcolor": "rgba(255,255,255,0.08)"
            if theme == "dark"
            else "rgba(0,0,0,0.08)",
            "title": x_title,
        },
        "yaxis": {
            "gridcolor": "rgba(255,255,255,0.08)"
            if theme == "dark"
            else "rgba(0,0,0,0.08)",
            "title": y_title,
        },
        "legend": {
            "orientation": "h",
            "x": 0.5,
            "y": -0.18,
            "xanchor": "center",
            "yanchor": "top",
        },
        "margin": {"t": 30, "b": 80, "l": 50, "r": 20},
    }

    return {"data": fig_data, "layout": layout}


# Auto-configures custom graph options dynamically based on selected axes
@callback(
    Output({"type": "custom-graph-options", "index": MATCH}, "value"),
    Input({"type": "custom-graph-x-selector", "index": MATCH}, "value"),
    Input({"type": "custom-graph-y-selector", "index": MATCH}, "value"),
    State({"type": "custom-graph-options", "index": MATCH}, "value"),
    prevent_initial_call=True,
)
def auto_configure_graph_options(x_var, y_var, current_options):
    if x_var == "uts" or (isinstance(y_var, list) and "uts" in y_var) or y_var == "uts":
        return ["lines"]
    return []
