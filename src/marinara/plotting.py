import logging
from datetime import UTC, datetime

from dash import Patch

logger = logging.getLogger(__name__)


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


def build_1d(
    x: list,
    y: list,
    t: list,
    mode: str,
    x_var: str,
    y_var: str,
    prefix: str | None = None,
) -> dict:
    return {
        "x": t if x_var == "uts" else x,
        "y": y,
        "mode": mode,
        "type": "scatter",
        "marker": {"size": 8, "opacity": 0.8},
        "hovertemplate": f"{x_var}: %{{x}}<br>{y_var}: %{{y}}",
        "name": y_var if prefix is None else f"{prefix}/{y_var}",
    }


def build_2d(
    x: list,
    y: list,
    z: list[list],
    x_var: str,
    y_var: str,
    z_var: str,
    prefix: str | None = None,
) -> dict:
    return {
        "x": x,
        "y": y,
        "z": z,
        "type": "heatmap",
        "hovertemplate": f"{x_var}: %{{x}}<br>{y_var}: %{{y}}<br>{z_var}: %{{z}}",
        "name": y_var if prefix is None else f"{prefix}/{z_var}",
    }


def build_err(times, name) -> dict:
    return {
        "type": "scatter",
        "x": [times[0], times[-1]],
        "y": ["", ""],
        "mode": "text",
        "visible": "legendonly",
        "name": f"{name} (Incompatible dims)",
    }


def build_traces(
    ds: dict,
    x_var: str,
    y_vars: list[str],
    mode: str = "lines+markers",
    relative: bool = False,
    prefix: str | None = None,
) -> list[dict]:
    """Builds Plotly scatter traces for the given data_var keys, exploding
    multidimensional variables into one named sub-trace per index. `prefix`
    namespaces trace names (e.g. by component name) for call sites that plot
    several datasets together, where the same variable name could otherwise
    collide across datasets."""
    x = ds["coords"][x_var]["data"]
    times, _ = format_timeseries_x(ds["coords"]["uts"]["data"], relative=relative)

    traces = []
    for y_name in y_vars:
        y = ds["data_vars"][y_name]["data"]
        y_dims = ds["data_vars"][y_name]["dims"]

        if len(y_dims) == 1:
            traces.append(build_1d(x, y, times, mode, x_var, y_name, prefix))
        elif len(y_dims) == 2 and x_var != "uts":
            traces.append(build_1d(x, y[-1], times, mode, x_var, y_name, prefix))
        elif len(y_dims) == 2 and len(y_vars) > 1:
            traces.append(build_err(times, y_name))
            logger.warning(
                "Cannot plot multiple variables %s together with a heatmap: %s",
                y_vars,
                y_name,
            )
        elif len(y_dims) == 2:
            # figure out axis order
            if y_dims.index("uts") == 0:
                z_var = y_dims[1]
                y_d = ds["coords"][z_var]["data"]
                z_d = [i for i in zip(*y)]
            else:
                z_var = y_dims[0]
                y_d = ds["coords"][z_var]["data"]
                z_d = y
            traces.append(build_2d(times, y_d, z_d, x_var, y_name, z_var))
        elif len(y_dims) > 2:
            traces.append(build_err(times, y_name))
            logger.warning(
                "Cannot plot multi-dimensional (%s) variable: %s", y_dims, y_name
            )
        else:
            continue
    return traces


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


def patch_traces(prev_figure: dict | None, traces: list[dict]) -> Patch:
    """Patches existing traces' fields in place when possible, instead of
    resetting the user's zoom/pan on every live-data poll; returns a full
    replacement trace list only when necessary. Two cases can be patched: the
    trace set is unchanged, or new traces were simply appended (e.g. a new
    variable or component started reporting) while the existing ones kept
    their order and identity - anything else (a trace removed, reordered, or
    renamed) redraws. Only ever touches the figure's `data` key - `layout` is
    a separate concern, updated by its own callback on selector changes."""
    prev_data = (prev_figure or {}).get("data") or []
    prev_names = [trace.get("name") for trace in prev_data]
    new_names = [trace.get("name") for trace in traces]

    patch = Patch()
    if not prev_names or new_names[: len(prev_names)] != prev_names:
        patch["data"] = traces
        return patch

    for i, trace in enumerate(traces[: len(prev_names)]):
        # Patch every field, not just x/y - a same-named trace can still
        # change mode/hovertemplate/etc. between polls (e.g. the custom
        # graph's "connect lines" toggle).
        for key, value in trace.items():
            patch["data"][i][key] = value
    for trace in traces[len(prev_names) :]:
        patch["data"].append(trace)
    return patch


def dims_consistency(x_var: str, y_vars: list[str], ds: dict) -> tuple[bool, str]:
    for y_name in y_vars:
        y_dims = ds["data_vars"][y_name]["dims"]
        if x_var not in y_dims:
            return (
                False,
                f"The selected X axis variable {x_var!r} "
                + f"is not a coordinate of the Y axis variable {y_name!r}. "
                + f"Select an X axis variable out of: {y_dims!r}.",
            )
    return True, ""
