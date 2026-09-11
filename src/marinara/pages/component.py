import json
import logging
from typing import Any

import dash
import pint
from dash import ALL, MATCH, Input, Output, State, callback, dcc, html
from tomato import passata

from marinara import plotting
from marinara.utils import (
    TOUT,
    format_constraint,
    get_attrs_vals,
    get_unit_str,
    is_component_running,
    update_datastore,
)

logger = logging.getLogger(__name__)
dash.register_page(__name__, path_template="/components/<port>/<name>")


def triggered_pattern_index(ctx):
    """Extracts the "index" field from a pattern-matching Input's triggered id."""
    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
    return json.loads(trigger_id)["index"]


def layout(port: int, name: str, **_) -> list:
    port = int(port)

    # Safely fetch initial state of the component
    try:
        status_ret = passata.status(port=port, name=name, timeout=TOUT)
        running = is_component_running(status_ret.data) if status_ret.success else False
    except Exception as e:
        logger.warning("Exception during passata.status:", exc_info=e)
        running = False

    try:
        attrs_ret = passata.attrs(port=port, name=name, timeout=TOUT)
        if attrs_ret.success and attrs_ret.data is not None:
            attrs_dict = attrs_ret.data
        else:
            attrs_dict = {}
    except Exception as e:
        logger.warning("Exception during passata.attrs:", exc_info=e)
        attrs_dict = {}

    avals_dict = get_attrs_vals(port=port, name=name, attrs=list(attrs_dict))

    # Initialize store datasets
    init_attrs_vals = {}
    init_attrs_units = {}
    init_attrs_rw = {}

    for k, v in attrs_dict.items():
        val = avals_dict.get(k)
        init_attrs_vals[k] = str(val.m if isinstance(val, pint.Quantity) else val)
        init_attrs_units[k] = v.units
        init_attrs_rw[k] = v.rw

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
    status_badge_text = (
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
                        status_badge_text,
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
        unit_str = get_unit_str(v.units)
        val = init_attrs_vals.get(k)

        # Build widget based on read-write / options
        if v.rw:
            if v.options:
                control = dcc.Dropdown(
                    id={"type": "component-attr-input", "index": k},
                    options=sorted(v.options),
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
        constraints = []
        if v.minimum is not None:
            constraints.append(f"min: {format_constraint(v.minimum, v.units)}")
        if v.maximum is not None:
            constraints.append(f"max: {format_constraint(v.maximum, v.units)}")
        constraints_str = f" ({', '.join(constraints)})" if constraints else ""

        if v.rw:
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
                                "label": " Show elapsed time",
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
            # Rendered directly in the initial layout (rather than injected
            # later by a callback) so that other callbacks can target it as
            # an Input from the start, instead of referencing an id that
            # doesn't exist yet on first render.
            dcc.Checklist(
                id="component-graph-tab-checklist",
                options=[],
                value=["all"],
                inline=True,
                inputClassName="graph-tab-input",
                style={
                    "display": "flex",
                    "flex-wrap": "wrap",
                    "margin-bottom": "15px",
                },
            ),
            html.Div(
                id="component-data-graph-container",
                style={"min-height": "400px"},
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
        dcc.Store(id="component-graph-tab-store", data=["all"]),
        dcc.Store(id="component-graph-units-store", data=None),
        dcc.Store(id="custom-graphs-list-store", data=[]),
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
def periodic_attrs_update(
    _: int,
    port: int,
    name: str,
    current_vals: dict[str, Any],
    units_dict: dict[str, Any],
) -> tuple[dict[str, Any], str, str]:
    try:
        status_ret = passata.status(port=port, name=name, timeout=TOUT)
        running = is_component_running(status_ret.data) if status_ret.success else False
    except Exception as e:
        logger.warning("Exception during passata.status:", exc_info=e)
        running = False

    avals_dict = get_attrs_vals(port=port, name=name, attrs=list(current_vals))

    new_vals = {}
    for k in current_vals:
        new_vals[k] = avals_dict.get(k)

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
    status_badge_text = (
        f"RUNNING ({task_name})"
        if task_name
        else ("RUNNING" if running_bool else "STOPPED")
    )

    return new_vals, status_badge_text, status_badge_class


# UI displays updates from Stores
@callback(
    Output({"type": "component-attr-readonly", "index": MATCH}, "children"),
    Input("component-attrs-vals-store", "data"),
    State({"type": "component-attr-readonly", "index": MATCH}, "id"),
    prevent_initial_call=True,
)
def update_readonly_attr(vals: dict[str, Any], id: dict[str, str]) -> str:
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
def set_component_attribute(
    n_clicks: int, value: str, id: dict[str, str], port: int, name: str
) -> Any | dash.NoUpdate:
    if n_clicks is None:
        return dash.no_update
    k = id["index"]
    ret = passata.set_attr(port=port, name=name, attr=k, val=value, timeout=TOUT)
    if ret.success:
        return ret.data
    # If set_attr returned success=False, fetch current value to revert
    current = get_attrs_vals(port=port, name=name, attrs=[k]).get(k)
    return current


# Data Store Updater
@callback(
    Output("component-data-store", "data"),
    State("tomato-port-store", "data"),
    State("component-name-store", "data"),
    State("component-data-store", "data"),
    Input("component-interval", "n_intervals"),
)
def component_data_update(
    port: int, name: str, data: dict | None, _: int
) -> dict | dash.NoUpdate | None:
    return update_datastore(port=port, name=name, datastore=data)


def group_by_unit(ds: dict) -> dict[str, list[str]]:
    """Groups data_var keys by their pint-normalized unit label ("" bucket for
    unitless vars), so equivalent units (e.g. "s" and "sec") share one tab."""
    groups = {}
    for key in ds["data_vars"]:
        raw_unit: str = ds["data_vars"][key].get("attrs", {}).get("units", "")
        label = get_unit_str(raw_unit)
        groups.setdefault(label, []).append(key)
    return groups


def unit_tab_id(label: str) -> str:
    """Encodes a unit label as a graph-tab token, namespaced so it can never
    collide with the "all" sentinel."""
    return f"unit:{label}"


def unit_tab_label(tab: str) -> str:
    """Decodes a unit-tab token (as produced by unit_tab_id) back to its label."""
    return tab.removeprefix("unit:")


# Tracks the set of distinct unit labels present in the data. Only changes
# (and so only triggers a tab-bar rebuild) when that set actually changes,
# instead of on every ~2s data poll - which would otherwise reset the
# just-rendered buttons' n_clicks and risk clobbering the active tab.
@callback(
    Output("component-graph-units-store", "data"),
    Input("component-data-store", "data"),
    State("component-graph-units-store", "data"),
)
def update_available_units(
    ds: dict | None, current_labels: list[str] | None
) -> list[str] | None | dash.NoUpdate:
    if ds is None:
        return dash.no_update if current_labels is None else None
    # Deterministic order: units alphabetically, unitless variables last
    labels = sorted(group_by_unit(ds), key=lambda u: (u == "", u))
    if labels == current_labels:
        return dash.no_update
    return labels


# Renders the "All" / per-unit tab picker's options as a checklist styled
# to look like tab pills (see .dash-options-list-option / .graph-tab-input in
# assets/main.css). A native multi-select control reports its complete
# checked set on every change, so - unlike the button + n_clicks +
# ctx.triggered scheme this replaced - there is no per-click delta
# bookkeeping and no ambiguity about click order. The checklist itself
# lives in the initial layout (see layout()), so only its `options` need
# updating here, not the whole component.
@callback(
    Output("component-graph-tab-checklist", "options"),
    Input("component-graph-units-store", "data"),
)
def render_graph_tabs(group_labels: list[str] | None) -> list[dict[str, str]]:
    if group_labels is None:
        return []
    ret = [{"label": "All", "value": "all"}]
    for label in group_labels:
        ret.append({"label": label or "Unitless", "value": unit_tab_id(label)})
    return ret


# Tracks which tabs (All, or one-or-more units) are currently selected.
# "All" is exclusive: checking it drops every unit; checking a unit while
# "All" was checked drops "All". Also prunes any selected unit whose label
# has dropped out of the live data.
@callback(
    Output("component-graph-tab-store", "data"),
    Output("component-graph-tab-checklist", "value"),
    Input("component-graph-tab-checklist", "value"),
    Input("component-graph-units-store", "data"),
    State("component-graph-tab-store", "data"),
    prevent_initial_call=True,
)
def update_active_graph_tab(
    checked: list[str],
    group_labels: list[str] | None,
    previous_tabs: list[str],
) -> tuple[list[str] | dash.NoUpdate, list[str] | dash.NoUpdate]:
    if "all" in checked and "all" not in previous_tabs:
        active_tabs = ["all"]
    elif "all" in checked and len(checked) > 1:
        active_tabs = [t for t in checked if t != "all"]
    else:
        active_tabs = list(checked) or ["all"]

    if group_labels is not None:
        valid = {unit_tab_id(label) for label in group_labels} | {"all"}
        active_tabs = [t for t in active_tabs if t in valid]
    active_tabs = active_tabs or ["all"]

    store_update = dash.no_update if active_tabs == previous_tabs else active_tabs
    checklist_update = dash.no_update if active_tabs == checked else active_tabs
    return store_update, checklist_update


# Renders the Data Graph widget's shells: one dcc.Graph per active unit tab.
# Only rebuilds when the *set* of active tabs changes (adding/removing a
# unit-tab), not on every ~2s data poll - the figure data itself is filled in
# separately by render_component_data_graph below, which can patch existing
# traces in place instead of losing zoom/pan on every tick.
@callback(
    Output("component-data-graph-container", "children"),
    Input("component-graph-tab-store", "data"),
    State("app-theme-store", "data"),
)
def render_component_data_graph_shells(
    active_tabs: list[str] | None,
    theme: str,
) -> list[dcc.Graph]:
    active_tabs = active_tabs or ["all"]
    # Shrink each graph when several are stacked so more fit on screen at once,
    # and give stacked graphs extra breathing room so one graph's legend
    # doesn't crowd against the next graph's title.
    graph_height = "400px" if len(active_tabs) <= 1 else "280px"
    graph_gap = "15px" if len(active_tabs) <= 1 else "40px"
    return [
        dcc.Graph(
            id={"type": "component-data-graph", "index": tab},
            # Seeded so Patch() has a figure to apply onto
            figure=plotting.empty_figure("Waiting for data...", theme),
            style={"height": graph_height, "margin-bottom": graph_gap},
            responsive=True,
        )
        for tab in active_tabs
    ]


# Layout only - traces are patched separately below to preserve zoom/pan
@callback(
    Output(
        {"type": "component-data-graph", "index": MATCH}, "figure", allow_duplicate=True
    ),
    Input("app-theme-store", "data"),
    Input("checkbox-align-time", "value"),
    Input("component-graph-tab-store", "data"),
    State("component-data-store", "data"),
    State({"type": "component-data-graph", "index": MATCH}, "id"),
    prevent_initial_call="initial_duplicate",
)
def render_component_data_graph_layout(
    theme: str,
    align_time: list[str],
    active_tabs: list[str],
    ds: dict | None,
    graph_id: dict[str, str],
) -> dict | dash.Patch:
    active_tabs = active_tabs or ["all"]
    tab = graph_id["index"]

    if ds is None:
        return plotting.empty_figure("Waiting for data...", theme)

    if tab == "all":
        has_data = bool(ds["data_vars"])
        y_title = "Value"
    else:
        label = unit_tab_label(tab)
        has_data = bool(group_by_unit(ds).get(label))
        y_title = label or "Value"

    if not has_data:
        return plotting.empty_figure("No data for this tab", theme)

    relative = bool(align_time and "relative" in align_time)
    _, x_title = plotting.format_timeseries_x([], relative=relative)
    layout = plotting.build_layout(
        theme,
        x_title=x_title,
        y_title=y_title,
        xaxis_extra={"tickangle": -30},
        # Legend sits above the plot rather than below: with rotated x-axis
        # tick labels, a bottom-anchored legend collides with the axis title
        # (Plotly positions the title right after the tick labels, so a
        # fixed y-fraction legend can land on the same line as the title).
        showlegend=True,
        legend={
            "orientation": "h",
            "x": 0.5,
            "y": 1.18,
            "xanchor": "center",
            "yanchor": "bottom",
        },
        margin={"t": 60 if len(active_tabs) <= 1 else 90, "b": 90, "l": 50, "r": 20},
    )
    patch = dash.Patch()
    patch["layout"] = layout
    return patch


# Traces only - layout handled above
@callback(
    Output(
        {"type": "component-data-graph", "index": MATCH}, "figure", allow_duplicate=True
    ),
    Input("component-data-store", "data"),
    State("checkbox-align-time", "value"),
    State({"type": "component-data-graph", "index": MATCH}, "id"),
    State({"type": "component-data-graph", "index": MATCH}, "figure"),
    prevent_initial_call="initial_duplicate",
)
def render_component_data_graph_traces(
    ds: dict | None,
    align_time: list[str],
    graph_id: dict[str, str],
    prev_figure: dict | None,
) -> dash.Patch:
    patch = dash.Patch()
    if ds is None:
        patch["data"] = []
        return patch

    tab = graph_id["index"]
    relative = bool(align_time and "relative" in align_time)

    if tab == "all":
        y_vars = list(ds["data_vars"])
    else:
        y_vars = group_by_unit(ds).get(unit_tab_label(tab), [])

    traces = plotting.build_traces(ds, "uts", y_vars, relative=relative)
    return plotting.patch_traces(prev_figure, traces)


# Manages adding and removing custom graphs
@callback(
    Output("custom-graphs-list-store", "data"),
    Input("add-graph-btn", "n_clicks"),
    Input({"type": "custom-graph-remove-btn", "index": ALL}, "n_clicks"),
    State("custom-graphs-list-store", "data"),
    prevent_initial_call=True,
)
def manage_custom_graphs(
    add_clicks: int, remove_clicks: int, active_ids: list[int]
) -> list[int]:
    ctx = dash.callback_context
    if not ctx.triggered:
        return active_ids

    trigger_id = ctx.triggered[0]["prop_id"]

    if "add-graph-btn" in trigger_id:
        next_id = max(active_ids, default=0) + 1
        return active_ids + [next_id]
    else:
        try:
            remove_idx = triggered_pattern_index(ctx)
            return [i for i in active_ids if i != remove_idx]
        except Exception as e:
            logger.warning("Exception during manage_custom_graphs:", exc_info=e)
            return active_ids


# Each card owns a {"type": "component-custom-graph", "index": i} store for its metadata
@callback(
    Output("custom-graphs-container", "children"),
    Input("custom-graphs-list-store", "data"),
    State({"type": "component-custom-graph", "index": ALL}, "id"),
    State({"type": "component-custom-graph", "index": ALL}, "data"),
    State("component-data-store", "data"),
    State("app-theme-store", "data"),
)
def render_graphs_list(
    active_ids: list[int],
    meta_ids: list[dict[str, int]],
    meta_values: list[dict],
    ds: dict | None,
    theme: str,
) -> html.Div | list[html.Div]:
    if len(active_ids) == 0:
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

    vars_list = sorted(ds.get("data_vars", {})) if ds else []
    vars_options = [{"label": v, "value": v} for v in vars_list]
    coords_options = [{"label": "Time(uts)", "value": "uts"}]

    meta_by_id = {m["index"]: v for m, v in zip(meta_ids, meta_values)}

    graphs_layouts = []
    for i in active_ids:
        meta = meta_by_id.get(i) or {}

        title_val = meta.get("title") or f"Custom Graph #{i}"
        yvar_val = meta.get("y_vars") or []
        options_val = meta.get("options") or ["lines"]

        card = html.Div(
            id={"type": "custom-graph-card", "index": i},
            children=[
                dcc.Store(id={"type": "component-custom-graph", "index": i}, data=meta),
                html.Div(
                    children=[
                        dcc.Input(
                            id={"type": "custom-graph-title-input", "index": i},
                            value=title_val,
                            type="text",
                            placeholder=f"Custom Graph #{i}",
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
                                    options=coords_options,
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
                                    options=vars_options,
                                    value=yvar_val,
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
                                    ],
                                    value=options_val,
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
                    # Seeded so Patch() has a figure to apply onto
                    figure=plotting.empty_figure(
                        "Select variables above to view custom plot", theme
                    ),
                    style={"height": "400px"},
                    responsive=True,
                ),
            ],
            className="card component-data",
            style={"margin-bottom": "20px"},
        )
        graphs_layouts.append(card)

    return graphs_layouts


# List-store Input only detects add/remove and bails, ignoring Dash's stale mount echo
@callback(
    Output({"type": "component-custom-graph", "index": MATCH}, "data"),
    Input({"type": "custom-graph-title-input", "index": MATCH}, "value"),
    Input({"type": "custom-graph-y-selector", "index": MATCH}, "value"),
    Input({"type": "custom-graph-options", "index": MATCH}, "value"),
    Input("custom-graphs-list-store", "data"),
    State({"type": "component-custom-graph", "index": MATCH}, "data"),
    prevent_initial_call=True,
)
def update_custom_graph_meta(
    title: str | None,
    y_vars: list[str] | None,
    options: list[str] | None,
    active_ids: list[int],
    current_data: dict,
) -> dict:
    ctx = dash.callback_context
    if not ctx.triggered or any(
        "custom-graphs-list-store" in t["prop_id"] for t in ctx.triggered
    ):
        return current_data
    return {"title": title, "y_vars": y_vars or [], "options": options or []}


@callback(
    Output({"type": "custom-graph-x-selector", "index": MATCH}, "options"),
    Output({"type": "custom-graph-y-selector", "index": MATCH}, "options"),
    Input("component-data-store", "data"),
)
def populate_dynamic_selectors(ds: dict | None) -> tuple[list[dict], list[dict]]:
    if ds is None:
        return [], []
    vars_list = sorted(ds.get("data_vars", {}))
    coords_list = sorted(ds.get("coords", {}))
    y_options = [{"label": v, "value": v} for v in vars_list]
    x_options = [{"label": "Time (uts)", "value": "uts"}]
    for coord in coords_list:
        if coord != "uts":
            x_options.append({"label": coord, "value": coord})
    return x_options, y_options


# Layout only - traces are patched separately below
@callback(
    Output({"type": "custom-graph", "index": MATCH}, "figure", allow_duplicate=True),
    Input({"type": "custom-graph-x-selector", "index": MATCH}, "value"),
    Input({"type": "custom-graph-y-selector", "index": MATCH}, "value"),
    Input("app-theme-store", "data"),
    State("component-data-store", "data"),
    prevent_initial_call="initial_duplicate",
)
def render_custom_graph_layout(
    x_var: str,
    y_var: str | list[str],
    theme: str,
    ds: dict | None,
) -> dict | dash.Patch:
    y_vars = [y_var] if isinstance(y_var, str) else y_var or []
    if ds is None or not x_var or len(y_vars) == 0:
        return plotting.empty_figure(
            "Select variables above to view custom plot", theme
        )

    consistent, msg = plotting.dims_consistency(x_var, y_vars, ds)
    if not consistent:
        return plotting.empty_figure(msg, theme)

    # Empty list is fine - only used for the title, not actual formatting
    _, x_title = plotting.format_timeseries_x([])

    if len(y_vars) == 1:
        y_title = y_vars[0]
    elif len(y_vars) > 1:
        y_title = "Selected Variables"
    else:
        y_title = "Value"

    layout = plotting.build_layout(
        theme, x_title=x_title, y_title=y_title, uirevision=f"{x_var}-{y_var}"
    )
    patch = dash.Patch()
    patch["layout"] = layout
    return patch


# Traces only - layout handled above
@callback(
    Output({"type": "custom-graph", "index": MATCH}, "figure", allow_duplicate=True),
    Input("component-data-store", "data"),
    Input({"type": "custom-graph-options", "index": MATCH}, "value"),
    State({"type": "custom-graph-x-selector", "index": MATCH}, "value"),
    State({"type": "custom-graph-y-selector", "index": MATCH}, "value"),
    State({"type": "custom-graph", "index": MATCH}, "figure"),
    prevent_initial_call="initial_duplicate",
)
def render_custom_graph_traces(
    ds: dict | None,
    options_val: list[str],
    x_var: str,
    y_var: str | list[str],
    prev_figure: dict | None,
) -> dash.Patch:
    y_vars = [y_var] if isinstance(y_var, str) else y_var or []
    patch = dash.Patch()
    if ds is None or not x_var or len(y_vars) == 0:
        patch["data"] = []
        return patch

    consistent, _ = plotting.dims_consistency(x_var, y_vars, ds)
    if not consistent:
        return patch

    connect_lines = "lines" in options_val
    mode = "lines+markers" if connect_lines else "markers"

    traces = plotting.build_traces(ds, x_var, y_vars, mode)
    return plotting.patch_traces(prev_figure, traces)


@callback(
    Output({"type": "custom-graph-options", "index": MATCH}, "value"),
    Input({"type": "custom-graph-x-selector", "index": MATCH}, "value"),
    Input({"type": "custom-graph-y-selector", "index": MATCH}, "value"),
    prevent_initial_call=True,
)
def auto_configure_graph_options(
    x_var: str, y_var: str | list[str]
) -> list[str] | dash.NoUpdate:
    # Non-"uts" means this is Dash's stale mount echo, not a real change
    if x_var != "uts":
        return dash.no_update
    return ["lines"]
