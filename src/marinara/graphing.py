import logging
from datetime import datetime, timezone
from typing import Any, Optional
from dash import Patch
from marinara.utils import clean_data, clean_value

logger = logging.getLogger(__name__)

DEFAULT_MAX_POINTS = 50


def build_base_figure(
    traces: list[dict[str, Any]],
    theme: str = "light",
    title: str = "",
) -> dict[str, Any]:
    """
    Builds a complete Plotly figure dictionary for initial rendering.

    Args:
        traces: List of trace dictionaries (with keys 'x', 'y', 'name', 'mode', etc.).
        theme: "dark" or "light".
        title: Optional plot title.

    Returns:
        Plotly figure dictionary.
    """
    is_dark = theme == "dark"
    return {
        "data": traces,
        "layout": {
            "title": title if title else None,
            "autosize": True,
            "template": "plotly_dark" if is_dark else "plotly",
            "paper_bgcolor": "rgba(0,0,0,0)",
            "plot_bgcolor": "rgba(0,0,0,0)",
            "font": {"color": "#ffffff" if is_dark else "#212529"},
            "margin": {"t": 35 if title else 15, "b": 90, "l": 50, "r": 15},
            "xaxis": {
                "gridcolor": "rgba(255,255,255,0.08)"
                if is_dark
                else "rgba(0,0,0,0.08)",
            },
            "yaxis": {
                "gridcolor": "rgba(255,255,255,0.08)"
                if is_dark
                else "rgba(0,0,0,0.08)",
            },
            "legend": {
                "orientation": "h",
                "x": 0.5,
                "y": -0.18,
                "xanchor": "center",
                "yanchor": "top",
            },
            "uirevision": True,
        },
    }


def format_timestamp(ts: Any) -> str:
    """Formats raw timestamp values to HH:MM:SS string."""
    cleaned_t = clean_value(ts)
    if isinstance(cleaned_t, (int, float)):
        try:
            return (
                datetime.fromtimestamp(cleaned_t, timezone.utc)
                .astimezone()
                .strftime("%H:%M:%S")
            )
        except Exception:
            return str(cleaned_t)
    return str(cleaned_t)


def extract_telemetry_points(ds_dict: dict[str, Any], cname: str) -> dict[str, tuple[str, Any]]:
    """
    Extracts the latest data point per variable from an xarray dataset dictionary.

    Returns:
        Dict mapping trace_key -> (formatted_time_str, cleaned_value)
    """
    points = {}
    if not ds_dict or "coords" not in ds_dict or "uts" not in ds_dict["coords"]:
        return points

    uts_list = ds_dict["coords"]["uts"].get("data", [])
    if not uts_list:
        return points

    last_idx = len(uts_list) - 1
    raw_time = uts_list[last_idx]
    time_str = format_timestamp(raw_time)

    for var_name, var_info in ds_dict.get("data_vars", {}).items():
        data_list = var_info.get("data", [])
        if last_idx < len(data_list):
            raw_val = data_list[last_idx]
            if isinstance(raw_val, (list, tuple)):
                for i, sub_val in enumerate(raw_val):
                    trace_key = f"{cname}/{var_name}[{i}]"
                    points[trace_key] = (time_str, clean_value(sub_val))
            else:
                trace_key = f"{cname}/{var_name}"
                points[trace_key] = (time_str, clean_value(raw_val))
    return points


def update_live_patch(
    current_store: Optional[dict[str, Any]],
    new_points: dict[str, tuple[str, Any]],
    theme: str = "light",
    max_points: int = DEFAULT_MAX_POINTS,
) -> tuple[Any, dict[str, Any]]:
    """
    Updates graph using dash.Patch() for partial property appending.

    If store or traces structure is missing, returns (full_figure_dict, updated_store).
    If traces exist, returns (dash.Patch(), updated_store).
    """
    if not current_store:
        current_store = {"traces": {}}

    store_traces = current_store.setdefault("traces", {})

    # Check if we need to initialize new traces
    need_full_rebuild = False
    for trace_key in new_points.keys():
        if trace_key not in store_traces:
            need_full_rebuild = True
            break

    if need_full_rebuild or not store_traces:
        # Build initial traces list
        traces = []
        for trace_key, (time_str, val) in new_points.items():
            if trace_key not in store_traces:
                store_traces[trace_key] = {"x": [time_str], "y": [val]}
            else:
                store_traces[trace_key]["x"].append(time_str)
                store_traces[trace_key]["y"].append(val)

            traces.append(
                {
                    "x": list(store_traces[trace_key]["x"]),
                    "y": list(store_traces[trace_key]["y"]),
                    "name": trace_key,
                    "type": "scatter",
                    "mode": "lines+markers",
                }
            )

        full_fig = build_base_figure(traces, theme=theme)
        return full_fig, clean_data(current_store)

    # Use dash.Patch for incremental updates
    patch = Patch()
    trace_keys_list = list(store_traces.keys())

    for trace_key, (time_str, val) in new_points.items():
        if trace_key in trace_keys_list:
            idx = trace_keys_list.index(trace_key)
            trace_data = store_traces[trace_key]

            # Append new point in store and patch
            trace_data["x"].append(time_str)
            trace_data["y"].append(val)

            patch["data"][idx]["x"].append(time_str)
            patch["data"][idx]["y"].append(val)

            # FIFO eviction if size > max_points
            if len(trace_data["x"]) > max_points:
                trace_data["x"].pop(0)
                trace_data["y"].pop(0)
                patch["data"][idx]["x"].delete(0)
                patch["data"][idx]["y"].delete(0)

    return patch, clean_data(current_store)
