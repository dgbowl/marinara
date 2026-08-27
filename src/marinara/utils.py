import dataclasses
import logging
import math
import numpy as np
import zmq
from dash import html, dcc
import tomato
from typing import Any, Union, Optional
import pint

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


def clean_value(val: Any) -> Any:
    """
    Coerces Pint Quantity objects, numpy types, Pydantic models, dataclasses,
    and collections to standard JSON-serializable primitives.
    """
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

    if hasattr(val, "magnitude"):
        val = val.magnitude
    elif hasattr(val, "m"):
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
        except Exception:
            pass

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
        except Exception:
            pass

    return val


def clean_data(d: Any) -> Any:
    """Recursively cleans values in dictionaries, lists, and tuples."""
    if isinstance(d, dict):
        return {k: clean_data(v) for k, v in d.items()}
    elif isinstance(d, list):
        return [clean_data(v) for v in d]
    elif isinstance(d, tuple):
        return tuple(clean_data(v) for v in d)
    else:
        return clean_value(d)


# Keep clean_dict_values as alias for backward compatibility
clean_dict_values = clean_data


def get_unit_str(units: Optional[Union[str, Any]]) -> str:
    """Formats unit names for human-friendly display using Pint."""
    if units is None or units == "":
        return ""
    try:
        q = pint.Quantity(1, units)
        return f"{q.units:~H}"
    except Exception:
        return str(units)


def format_constraint(val: Any, base_unit: str) -> str:
    """
    Formats constraint values (min/max) with their respective units.

    If the constraint value is a Pint Quantity, it is formatted with its own units,
    trying to convert to the attribute's base unit first if compatible.
    Otherwise, it is formatted using the base unit.
    """
    if val is None:
        return ""
    if hasattr(val, "magnitude") and hasattr(val, "units"):
        if base_unit:
            try:
                # Convert to base_unit to keep it consistent if compatible
                val = val.to(base_unit)
            except Exception:
                pass
        mag = clean_value(val)
        u_str = get_unit_str(val.units)
        return f"{mag} {u_str}" if u_str else str(mag)
    else:
        mag = clean_value(val)
        u_str = get_unit_str(base_unit)
        return f"{mag} {u_str}" if u_str else str(mag)


def format_obj(obj, headers, attrs, otype, port):
    if not obj:
        return html.Div(
            "No registered elements found.",
            className="text-secondary",
            style={"text-align": "center", "padding": "20px"},
        )

    cards = []
    for k, v in obj.items():
        name_str = str(k)

        # Determine plurality/path type for links
        path_type = otype
        if otype == "device":
            path_type = "devices"
        elif otype == "driver":
            path_type = "drivers"

        # Title as a link to detail page (only for components and pipelines)
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

        # Build metadata elements
        metadata_items = []

        # We skip the first attribute (name) because it is the title
        for idx, attr in enumerate(attrs[1:]):
            header_label = headers[idx + 1]
            val = get_field(v, attr, "")
            if isinstance(val, list) or isinstance(val, tuple) or isinstance(val, set):
                val_str = ", ".join(str(x) for x in val)
            else:
                val_str = str(val)

            # Skip capabilities in metadata block (will render separately)
            if attr == "capabilities":
                continue

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

        # If there are capabilities, render them beautifully
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


def get_tomato_status(port):
    try:
        ret = tomato.status(stgrp="tomato", port=port, **kwargs)
        if not ret.success:
            return None
        return ret.data
    except Exception:
        return None
