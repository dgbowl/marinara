import logging
from datetime import datetime, timezone
from typing import Any, Optional
from dash import Patch
import xarray as xr
from marinara.utils import clean_data, clean_value

logger = logging.getLogger(__name__)

TIMESTEPS = 500
DEFAULT_MAX_POINTS = 50
DEFAULT_MAX_ARRAY_TRACES = 20


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
                for i, sub_val in enumerate(raw_val[:DEFAULT_MAX_ARRAY_TRACES]):
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

            # Only append if a new telemetry timestamp arrives
            if trace_data.get("x") and trace_data["x"][-1] == time_str:
                continue

            # Append new point in store and patch
            trace_data["x"].append(time_str)
            trace_data["y"].append(val)

            patch["data"][idx]["x"].append(time_str)
            patch["data"][idx]["y"].append(val)

            # FIFO eviction if size > max_points
            if len(trace_data["x"]) > max_points:
                trace_data["x"].pop(0)
                trace_data["y"].pop(0)
                try:
                    del patch["data"][idx]["x"][0]
                    del patch["data"][idx]["y"][0]
                except Exception as e:
                    logger.warning("Failed to evict point from patch: %s", e)

    return patch, clean_data(current_store)


def append_telemetry_dataset_dict(
    existing_data: Optional[dict[str, Any]],
    new_dataset: Any,
    max_points: int = TIMESTEPS,
) -> dict[str, Any]:
    """
    Appends the latest telemetry point(s) from an xarray.Dataset into an in-memory
    dictionary representation without costly Dataset reconstruction and merging.
    """
    if new_dataset is None:
        return existing_data if existing_data is not None else {}

    if not isinstance(new_dataset, xr.Dataset):
        logger.warning(
            "Expected xr.Dataset from telemetry query, got %s",
            type(new_dataset).__name__,
        )
        if hasattr(new_dataset, "to_dict"):
            new_dict = clean_data(new_dataset.to_dict())
        else:
            return existing_data if existing_data is not None else {}
    else:
        if "uts" not in new_dataset.coords:
            logger.warning("Telemetry dataset missing 'uts' coordinate")
            return existing_data if existing_data is not None else {}
        new_dict = clean_data(new_dataset.to_dict())

    # If first load, initialize with new_dict (sliced to max_points if needed)
    if not existing_data:
        if "coords" in new_dict and "uts" in new_dict["coords"]:
            uts_data = new_dict["coords"]["uts"].get("data", [])
            if len(uts_data) > max_points:
                new_dict["coords"]["uts"]["data"] = uts_data[-max_points:]
                for v_info in new_dict.get("data_vars", {}).values():
                    v_data = v_info.get("data", [])
                    if len(v_data) > max_points:
                        v_info["data"] = v_data[-max_points:]
                new_dict.setdefault("dims", {})["uts"] = len(
                    new_dict["coords"]["uts"]["data"]
                )
        return new_dict

    # Append new point(s) if not already present
    new_uts_list = new_dict.get("coords", {}).get("uts", {}).get("data", [])
    if not new_uts_list:
        return existing_data

    old_uts_list = (
        existing_data.setdefault("coords", {})
        .setdefault("uts", {})
        .setdefault("data", [])
    )
    old_uts_set = set(old_uts_list)

    existing_vars = existing_data.setdefault("data_vars", {})
    new_vars = new_dict.get("data_vars", {})

    # Copy over non-uts coordinates (e.g. freq, wavelength) if not present
    for c_name, c_info in new_dict.get("coords", {}).items():
        if c_name != "uts" and c_name not in existing_data["coords"]:
            existing_data["coords"][c_name] = c_info

    for idx, new_t in enumerate(new_uts_list):
        if new_t in old_uts_set:
            continue
        old_uts_list.append(new_t)
        old_uts_set.add(new_t)

        for v_name, v_info in new_vars.items():
            v_data = v_info.get("data", [])
            if idx < len(v_data):
                val = v_data[idx]
                if v_name not in existing_vars:
                    existing_vars[v_name] = {
                        "dims": v_info.get("dims", ("uts",)),
                        "attrs": v_info.get("attrs", {}),
                        "data": [val],
                    }
                else:
                    existing_vars[v_name].setdefault("data", []).append(val)

    # FIFO trim to max_points
    if len(old_uts_list) > max_points:
        existing_data["coords"]["uts"]["data"] = old_uts_list[-max_points:]
        for v_info in existing_vars.values():
            v_data = v_info.get("data", [])
            if len(v_data) > max_points:
                v_info["data"] = v_data[-max_points:]

    existing_data.setdefault("dims", {})["uts"] = len(
        existing_data["coords"]["uts"]["data"]
    )
    return existing_data
