import logging
from typing import Any, Optional, Union
import pint
from dash import dcc, html
import tomato
import zmq

logger = logging.getLogger(__name__)

PORT = 1234
TOUT = 1000
CTXT = zmq.Context()
kwargs = dict(timeout=TOUT, context=CTXT)


def get_field(obj: Any, key: str, default: Any = None) -> Any:
    """Safely gets a field from an object (attribute or dict) or returns default."""
    if hasattr(obj, key):
        val = getattr(obj, key)
        return val if val is not None else default
    elif isinstance(obj, dict):
        val = obj.get(key, default)
        return val if val is not None else default
    return default


import math
import numpy as np


def clean_value(val: Any) -> Any:
    """Coerces Pint Quantity objects, numpy types, NaNs, and collections to standard JSON-serializable primitives."""
    if val is None:
        return ""

    if hasattr(val, "m"):
        val = val.m

    if isinstance(val, np.ndarray):
        if val.size == 1:
            val = val.item()
        elif val.size == 0:
            return ""
        else:
            val = val.tolist()

    if hasattr(val, "item") and callable(val.item):
        try:
            val = val.item()
        except Exception as e:
            logger.error("Failed to convert scalar value: %s", e)

    if isinstance(val, (float, np.floating)):
        if math.isnan(val) or math.isinf(val):
            return ""
        return float(val)

    if isinstance(val, (int, np.integer)):
        return int(val)

    if isinstance(val, (str, bool)):
        return val

    if isinstance(val, (list, tuple)):
        return [clean_value(x) for x in val]

    if isinstance(val, dict):
        return {str(k): clean_value(v) for k, v in val.items()}

    try:
        return str(val)
    except Exception as e:
        logger.warning("Failed to stringify value %s: %s", val, e)
        return ""


def clean_data(d: Any) -> Any:
    """Recursively cleans values in dictionaries, lists, and tuples."""
    if isinstance(d, dict):
        return {k: clean_data(v) for k, v in d.items()}
    elif isinstance(d, (list, tuple)):
        return [clean_data(v) for v in d]
    else:
        return clean_value(d)


def get_unit_str(units: Optional[Union[str, Any]]) -> str:
    """Formats unit names for human-friendly display using Pint."""
    if not units:
        return ""
    try:
        q = pint.Quantity(1, units)
        return f"{q.units:~H}"
    except pint.UndefinedUnitError:
        return str(units)
    except Exception as e:
        logger.error("Error parsing unit '%s': %s", units, e)
        return str(units)


def format_constraint(val: Any, base_unit: str) -> str:
    """Formats constraint values (min/max) with their respective units."""
    if val is None:
        return ""
    if hasattr(val, "m") and hasattr(val, "units"):
        if base_unit:
            try:
                val = val.to(base_unit)
            except Exception as e:
                logger.error(
                    "Failed to convert constraint %s to base_unit %s: %s",
                    val,
                    base_unit,
                    e,
                )
        mag = clean_value(val)
        u_str = get_unit_str(val.units)
        return f"{mag} {u_str}" if u_str else str(mag)
    else:
        mag = clean_value(val)
        u_str = get_unit_str(base_unit)
        return f"{mag} {u_str}" if u_str else str(mag)


def format_obj(
    obj: dict[str, Any],
    headers: list[str],
    attrs: list[str],
    otype: str,
    port: int,
) -> html.Div:
    """Renders a grid of UI cards displaying metadata for devices, drivers, components, or pipelines."""
    if not obj:
        return html.Div(
            "No registered elements found.",
            className="text-secondary",
            style={"text-align": "center", "padding": "20px"},
        )

    cards = []
    for k, v in obj.items():
        name_str = str(k)

        path_type = otype
        if otype == "device":
            path_type = "devices"
        elif otype == "driver":
            path_type = "drivers"

        if otype in ["pipelines", "components"]:
            title_el = dcc.Link(
                name_str,
                href=f"/{path_type}/{port}/{name_str}",
                style={
                    "font-size": "18px",
                    "font-weight": "700",
                    "text-decoration": "none",
                    "color": "var(--accent-color)",
                },
            )
        else:
            title_el = html.Span(
                name_str,
                style={
                    "font-size": "18px",
                    "font-weight": "700",
                    "color": "var(--accent-color)",
                },
            )

        metadata_items = []
        for header_label, attr in zip(headers, attrs):
            if attr in ("name", "capabilities"):
                continue
            val = get_field(v, attr, "")
            if isinstance(val, (list, tuple, set)):
                val_str = ", ".join(str(x) for x in val)
            else:
                val_str = str(val)

            metadata_items.append(
                html.Div(
                    children=[html.Strong(f"{header_label}: "), html.Span(val_str)],
                    style={"margin-right": "35px"},
                )
            )

        details_row = html.Div(
            children=metadata_items,
            style={
                "display": "flex",
                "flex-wrap": "wrap",
                "margin-bottom": "10px",
                "font-size": "14px",
                "gap": "10px",
            },
        )

        card_children = [
            html.Div(
                children=[title_el],
                style={
                    "display": "flex",
                    "align-items": "center",
                    "margin-bottom": "15px",
                },
            ),
            details_row,
        ]

        if "capabilities" in attrs:
            cap_val = get_field(v, "capabilities", [])
            if cap_val:
                cap_str = (
                    ", ".join(str(x) for x in cap_val)
                    if isinstance(cap_val, (list, set, tuple))
                    else str(cap_val)
                )
            else:
                cap_str = "None"

            card_children.append(
                html.Div(
                    children=[
                        html.Div(
                            "Capabilities Info",
                            style={
                                "font-weight": "600",
                                "font-size": "14px",
                                "margin-top": "15px",
                                "border-bottom": "1px solid var(--border-color)",
                                "padding-bottom": "5px",
                                "margin-bottom": "10px",
                            },
                        ),
                        html.Div(
                            cap_str,
                            className="text-secondary",
                            style={"font-size": "13px"},
                        ),
                    ]
                )
            )

        cards.append(
            html.Div(
                className="card",
                style={"margin-bottom": "20px", "padding": "20px"},
                children=card_children,
            )
        )

    container_class = "card-grid" if otype == "components" else None
    return html.Div(cards, className=container_class)


def get_tomato_status(port: int) -> Optional[Any]:
    """Fetches full status data object from tomato daemon on specified port."""
    try:
        ret = tomato.status(stgrp="tomato", port=port, **kwargs)
        if not ret.success:
            return None
        return ret.data
    except Exception as e:
        logger.error("Failed to query tomato status on port %s: %s", port, e)
        return None


def ensure_drivers_registered(daemon: Any) -> None:
    """Automatically registers components on all connected drivers if needed."""
    if not daemon or not hasattr(daemon, "drvs"):
        return
    for drv_name, drv in daemon.drvs.items():
        drv_port = get_field(drv, "port")
        if drv_port:
            try:
                s = CTXT.socket(zmq.REQ)
                s.setsockopt(zmq.RCVTIMEO, 500)
                s.connect(f"tcp://127.0.0.1:{drv_port}")
                s.send_pyobj({"cmd": "register"})
                s.recv_pyobj()
                s.close()
            except Exception as e:
                logger.debug(
                    "Driver auto-register ping to %s on port %s failed: %s",
                    drv_name,
                    drv_port,
                    e,
                )
