import dataclasses
import json
import logging
import math
from typing import Any, Optional, Union

from dash import dcc, html
import numpy as np
import pint
from tomato import passata, tomato
import zmq

logger = logging.getLogger(__name__)

PORT = 1234
TOUT = 1000
CTXT = zmq.Context()
kwargs = dict(timeout=TOUT, context=CTXT)


def clean_value(val: Any) -> Any:
    """Coerces Pint Quantity objects, numpy types, Pydantic models, dataclasses, NaNs, and collections to standard JSON-serializable primitives."""
    if val is None:
        return ""

    # Pydantic v2 check
    if hasattr(val, "model_dump") and callable(val.model_dump):
        try:
            return clean_value(val.model_dump())
        except Exception as e:
            logger.warning("Failed to model_dump value of type %s: %s", type(val).__name__, e)
            return str(val)

    # Pydantic v1 check
    if hasattr(val, "dict") and callable(val.dict) and not isinstance(val, dict):
        try:
            return clean_value(val.dict())
        except Exception as e:
            logger.warning("Failed to dict() value of type %s: %s", type(val).__name__, e)
            return str(val)

    # Dataclass check
    if dataclasses.is_dataclass(val) and not isinstance(val, type):
        try:
            return clean_value(dataclasses.asdict(val))
        except Exception as e:
            logger.warning("Failed to asdict dataclass of type %s: %s", type(val).__name__, e)
            return str(val)

    # Pint Quantity check
    if hasattr(val, "m"):
        val = val.m

    if isinstance(val, np.ndarray):
        if val.size == 1:
            val = val.item()
        elif val.size == 0:
            return ""
        else:
            return [clean_value(x) for x in val.tolist()]

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

    # General custom object with __dict__ check
    if hasattr(val, "__dict__") and not isinstance(val, (type, dict, list, tuple)):
        try:
            return clean_value(val.__dict__)
        except Exception as e:
            logger.warning("Failed to extract __dict__ from %s: %s", type(val).__name__, e)
            return str(val)

    try:
        return str(val)
    except Exception as e:
        logger.warning("Failed to stringify value of type %s: %s", type(val).__name__, e)
        return ""


def format_sigfig(val: Any, sigfigs: int = 3) -> str:
    """Formats floating-point numerical values to a specified number of significant figures while preserving integers, booleans, and other primitives."""
    if val is None or val == "":
        return ""
    if isinstance(val, bool):
        return str(val)
    if isinstance(val, (int, np.integer)):
        return str(val)
    if isinstance(val, (float, np.floating)):
        if math.isnan(val) or math.isinf(val):
            return ""
        if val == 0:
            return "0"
        return f"{val:.{sigfigs}g}"
    return str(val)


def format_attr_value(val: Any, sigfigs: int = 3) -> str:
    """Formats attribute values (primitives, dicts, lists) into safe strings for UI inputs and labels, limiting floating-point numbers to significant figures."""
    cleaned = clean_value(val)
    if isinstance(cleaned, (dict, list)):
        try:
            return json.dumps(cleaned)
        except Exception as e:
            logger.debug("json.dumps failed for cleaned value of type %s: %s", type(cleaned).__name__, e)
            return str(cleaned)
    if isinstance(cleaned, (float, np.floating)):
        return format_sigfig(cleaned, sigfigs=sigfigs)
    return str(cleaned) if cleaned is not None else ""


def parse_input_value(val: Any) -> Any:
    """Parses user string inputs from the UI into appropriate Python types (lists, dicts, numbers, booleans) if applicable."""
    if not isinstance(val, str):
        return val
    s = val.strip()
    if not s:
        return ""
    if s.lower() == "true":
        return True
    if s.lower() == "false":
        return False
    if s.startswith(("[", "{")):
        try:
            return json.loads(s)
        except Exception:
            try:
                import ast
                return ast.literal_eval(s)
            except Exception:
                pass
    return val




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
    """Formats constraint values (min/max) with their respective units, using 3 significant figures for floats."""
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
        mag_str = format_sigfig(mag)
        u_str = get_unit_str(val.units)
        return f"{mag_str} {u_str}" if u_str else str(mag_str)
    else:
        mag = clean_value(val)
        mag_str = format_sigfig(mag)
        u_str = get_unit_str(base_unit)
        return f"{mag_str} {u_str}" if u_str else str(mag_str)


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
            val = v.get(attr, "") if isinstance(v, dict) else getattr(v, attr, "")
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
            cap_val = (
                v.get("capabilities", [])
                if isinstance(v, dict)
                else getattr(v, "capabilities", [])
            )
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
        drv_port = (
            drv.get("port") if isinstance(drv, dict) else getattr(drv, "port", None)
        )
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


def fetch_component_state(port: int, name: str) -> dict[str, Any]:
    """
    Fetches the running status, attribute metadata, attribute values, and units for a component.
    Coerces all attribute values to Python literals via clean_value.

    Returns:
        Dict containing:
            'running': bool or status object/dict
            'attrs_dict': dict mapping attr_name -> metadata dict/object
            'attrs_vals': dict mapping attr_name -> cleaned Python literal value
            'attrs_units': dict mapping attr_name -> unit string or None
            'attrs_rw': dict mapping attr_name -> bool
    """
    try:
        status_ret = passata.status(**kwargs, port=port, name=name)
        if status_ret.success:
            if isinstance(status_ret.data, dict):
                running = status_ret.data.get("running", False)
            else:
                running = getattr(status_ret.data, "running", False)
        else:
            running = False
    except Exception as e:
        logger.warning(
            "Failed to fetch status for component %s on port %s: %s",
            name,
            port,
            e,
        )
        running = False

    try:
        attrs_ret = passata.attrs(**kwargs, port=port, name=name)
        attrs_dict = attrs_ret.data if (attrs_ret.success and attrs_ret.data) else {}
    except Exception as e:
        logger.warning(
            "Failed to fetch attributes for component %s on port %s: %s",
            name,
            port,
            e,
        )
        attrs_dict = {}

    try:
        avals_ret = passata.get_attrs(
            **kwargs, port=port, name=name, attrs=list(attrs_dict.keys())
        )
        avals_dict = avals_ret.data if (avals_ret.success and avals_ret.data) else {}
    except Exception as e:
        logger.warning(
            "Failed to fetch attribute values for component %s on port %s: %s",
            name,
            port,
            e,
        )
        avals_dict = {}

    init_attrs_vals = {}
    init_attrs_units = {}
    init_attrs_rw = {}

    for k, v in attrs_dict.items():
        val = avals_dict.get(k)
        unit = v.get("units") if isinstance(v, dict) else getattr(v, "units", None)
        is_rw = v.get("rw", False) if isinstance(v, dict) else getattr(v, "rw", False)
        init_attrs_vals[k] = clean_value(val)
        init_attrs_units[k] = unit
        init_attrs_rw[k] = bool(is_rw)

    return {
        "running": running,
        "attrs_dict": attrs_dict,
        "attrs_vals": init_attrs_vals,
        "attrs_units": init_attrs_units,
        "attrs_rw": init_attrs_rw,
    }


def parse_running_status(running: Any) -> tuple[bool, Optional[str], str, str]:
    """
    Parses component running status.

    Returns:
        tuple of (running_bool, technique_name, status_text, status_badge_class)
    """
    if isinstance(running, bool):
        running_bool = running
        technique_name = None
    else:
        running_bool = bool(running)
        if isinstance(running, dict):
            technique_name = running.get("technique_name")
        else:
            technique_name = getattr(running, "technique_name", None)

    status_badge_class = (
        "badge badge-success" if running_bool else "badge badge-secondary"
    )
    status_text = (
        f"RUNNING ({technique_name})"
        if technique_name
        else ("RUNNING" if running_bool else "STOPPED")
    )
    return running_bool, technique_name, status_text, status_badge_class

