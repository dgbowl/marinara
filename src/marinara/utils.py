import logging
from typing import Any

import pint
import zmq
from dash import dcc, html
from tomato import passata

PORT = 1234
TOUT = 1000
CTXT = zmq.Context()
kwargs = {"timeout": TOUT, "context": CTXT}
logger = logging.getLogger(__name__)


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
    Coerces Pint Quantity objects and numpy types to standard serializable types.

    Sequential if/elif is avoided here because the conversions can be chained:
    1. If the value is a Pint Quantity, we extract its magnitude using .magnitude or .m.
    2. After this extraction, the resulting value might be a numpy type (like a numpy scalar).
       We then check if it has the .item() method to convert it to a standard Python scalar
       for proper JSON serialization in Dash's dcc.Store.
    """
    if hasattr(val, "magnitude"):
        val = val.magnitude
    elif hasattr(val, "m"):
        val = val.m

    if hasattr(val, "item") and callable(val.item):
        val = val.item()
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


def get_unit_str(units: str | Any | None) -> str:
    """Formats unit names for human-friendly display using Pint."""
    if units is None or units == "":
        return ""
    try:
        q = pint.Quantity(1, units)
        return f"{q.units:~H}"
    except (pint.errors.PintError, AssertionError):
        # Some unit strings (e.g. "#", "$") make pint raise a bare AssertionError
        return str(units)
    except TypeError as e:
        # A non-string units value (e.g. malformed driver metadata) raises TypeError
        logger.warning("Exception during get_unit_str:", exc_info=e)
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
            except pint.errors.DimensionalityError:
                logger.error("could not convert val '%s' to unit '%s'", val, base_unit)
        mag = clean_value(val)
        u_str = get_unit_str(val.units)
        return f"{mag} {u_str}" if u_str else str(mag)
    else:
        mag = clean_value(val)
        u_str = get_unit_str(base_unit)
        return f"{mag} {u_str}" if u_str else str(mag)


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


def format_obj(obj, headers, attrs, otype, port) -> html.Div:
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
            if isinstance(val, (list, tuple, set)):
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


def get_attrs_vals(port: int, name: str, attrs: list[str]) -> dict[str, Any]:
    ret = passata.get_attrs(**kwargs, port=port, name=name, attrs=attrs)  # ty: ignore[invalid-argument-type]
    if ret.success and ret.data is not None:
        vals: dict = ret.model_dump()["data"]
    else:
        vals = {}
    return vals


def pretty(val: Any) -> str:
    if isinstance(val, list):
        ret = f"[{pretty(val[0])},··· {pretty(val[-1])}] n={len(val)}"
    else:
        try:
            ret = f"{pint.Quantity(val):,.3~gP}"
        except TypeError:
            ret = str(val)
    return ret
