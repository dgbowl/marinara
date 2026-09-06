import logging
from collections.abc import Generator
from datetime import UTC, datetime

import xarray as xr
from dash import Patch

from marinara.utils import clean_data

logger = logging.getLogger(__name__)


def merge_and_cap(
    existing_ds_dict: dict | None, new_ds: xr.Dataset, cap: int, dim: str = "uts"
) -> dict:
    """Merges a newly-polled xarray Dataset into the existing store dict (or
    starts fresh if None), then trims to the last `cap` rows along `dim`.
    Returns already-cleaned (JSON-safe) data - callers don't need to run
    clean_data on the result again."""
    if existing_ds_dict is None:
        merged = new_ds
    else:
        odata = xr.Dataset.from_dict(existing_ds_dict)
        # Pin explicitly: xarray's defaults for these are changing in a
        # future release (join outer->exact, compat no_conflicts->override),
        # and this merge relies on the current outer/no_conflicts behavior
        # to combine datasets whose `dim` coordinate keeps growing.
        merged = xr.merge([odata, new_ds], join="outer", compat="no_conflicts")
    if merged.sizes[dim] > cap:
        merged = merged.isel({dim: slice(-cap, None)})
    return clean_data(merged.to_dict())


def format_timeseries_x(
    raw_x: list, relative: bool = False, compact: bool = False
) -> tuple[list, str]:
    """Returns (formatted_x, x_axis_title) for a uts coordinate array.
    `compact` selects a short HH:MM:SS format instead of a full date, for
    small multi-series widgets where a full timestamp would crowd the axis."""
    formatted_x = []
    if relative:
        start_t = raw_x[0] if len(raw_x) > 0 else 0
        for t in raw_x:
            try:
                formatted_x.append(f"+{round(t - start_t, 1)}s")
            except Exception as e:
                logger.warning("Exception during time formatting:", exc_info=e)
                formatted_x.append(t)
        return formatted_x, "Relative Time (Seconds)"

    fmt = "%H:%M:%S" if compact else "%Y-%m-%d %H:%M:%S"
    for t in raw_x:
        try:
            formatted_x.append(
                datetime.fromtimestamp(t, UTC).astimezone().strftime(fmt)
            )
        except Exception as e:
            logger.warning("Exception during time formatting:", exc_info=e)
            formatted_x.append(t)
    return formatted_x, "Time (Local)"


def iter_series(key: str, y_raw: list) -> Generator[tuple[str, list]]:
    """Yields (name, y_values) pairs for a data_var, exploding multidimensional
    variables into one named sub-series per index (key[0], key[1], ...)."""
    if not (len(y_raw) > 0 and isinstance(y_raw[0], (list, tuple))):
        yield key, y_raw
        return

    max_len = max(len(item) for item in y_raw if isinstance(item, (list, tuple)))
    for i in range(max_len):
        sub_y = [
            item[i] if isinstance(item, (list, tuple)) and i < len(item) else None
            for item in y_raw
        ]
        yield f"{key}[{i}]", sub_y


def build_traces(
    ds: dict, keys: list[str], formatted_x: list, prefix: str | None = None
) -> list[dict]:
    """Builds Plotly scatter traces for the given data_var keys, exploding
    multidimensional variables into one named sub-trace per index. `prefix`
    namespaces trace names (e.g. by component name) for call sites that plot
    several datasets together, where the same variable name could otherwise
    collide across datasets."""
    data = []
    for key in keys:
        y_raw: list = ds["data_vars"][key]["data"]
        for name, y_vals in iter_series(key, y_raw):
            trace_name = f"{prefix}/{name}" if prefix else name
            data.append(
                {
                    "x": formatted_x,
                    "y": y_vals,
                    "name": trace_name,
                    "type": "scatter",
                    "mode": "lines+markers",
                }
            )
    return data


def theme_plot_colors(theme: str) -> dict:
    """Shared Plotly template/background/font settings driven by the light/dark theme."""
    is_dark = theme == "dark"
    return {
        "template": "plotly_dark" if is_dark else "plotly",
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"color": "#ffffff" if is_dark else "#212529"},
    }


def theme_gridcolor(theme: str) -> str:
    return "rgba(255,255,255,0.08)" if theme == "dark" else "rgba(0,0,0,0.08)"


def empty_figure(message: str, theme: str) -> dict:
    """Placeholder figure for 'select a pipeline' / 'offline' / 'no data' states."""
    return {
        "layout": {
            "autosize": True,
            "xaxis": {"visible": False},
            "yaxis": {"visible": False},
            "annotations": [
                {
                    "text": message,
                    "xref": "paper",
                    "yref": "paper",
                    "showarrow": False,
                    "font": {"size": 16, "color": "gray"},
                }
            ],
            **theme_plot_colors(theme),
        }
    }


def build_layout(
    theme: str,
    x_title: str | None = None,
    y_title: str | None = None,
    xaxis_extra: dict | None = None,
    yaxis_extra: dict | None = None,
    **overrides,
) -> dict:
    """Shared theme-aware layout dict. `overrides` replace top-level keys
    (margin, legend, uirevision, showlegend, ...); `xaxis_extra`/`yaxis_extra`
    merge into the axis dicts instead of replacing them wholesale."""
    xaxis = {"gridcolor": theme_gridcolor(theme)}
    if x_title:
        xaxis["title"] = x_title
    if xaxis_extra:
        xaxis.update(xaxis_extra)

    yaxis = {"gridcolor": theme_gridcolor(theme)}
    if y_title:
        yaxis["title"] = y_title
    if yaxis_extra:
        yaxis.update(yaxis_extra)

    layout = {
        "autosize": True,
        "uirevision": True,
        **theme_plot_colors(theme),
        "xaxis": xaxis,
        "yaxis": yaxis,
        "legend": {
            "orientation": "h",
            "x": 0.5,
            "y": -0.18,
            "xanchor": "center",
            "yanchor": "top",
        },
        "margin": {"t": 30, "b": 80, "l": 50, "r": 20},
    }
    layout.update(overrides)
    return layout


def patch_or_redraw(
    prev_figure: dict | None, traces: list[dict], layout: dict
) -> dict | Patch:
    """Patches existing traces' fields (and the layout) in place when possible,
    instead of resetting the user's zoom/pan on every live-data poll; returns
    a full new figure only when necessary. Two cases can be patched: the
    trace set is unchanged, or new traces were simply appended (e.g. a new
    variable or component started reporting) while the existing ones kept
    their order and identity - anything else (a trace removed, reordered, or
    renamed) redraws."""
    prev_data = (prev_figure or {}).get("data") or []
    prev_names = [trace.get("name") for trace in prev_data]
    new_names = [trace.get("name") for trace in traces]

    if not prev_names or new_names[: len(prev_names)] != prev_names:
        return {"data": traces, "layout": layout}

    patch = Patch()
    for i, trace in enumerate(traces[: len(prev_names)]):
        # Patch every field, not just x/y - a same-named trace can still
        # change mode/hovertemplate/etc. between polls (e.g. the custom
        # graph's "connect lines" toggle).
        for key, value in trace.items():
            patch["data"][i][key] = value
    for trace in traces[len(prev_names) :]:
        patch["data"].append(trace)
    patch["layout"] = layout
    return patch
