import ctypes
import json
import logging
import os
import sys
from collections.abc import Callable
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

import dash
import pint
from dash import dcc, html
from tomato import passata
from tomato.driverinterface_3_0 import Attr, Status

PORT = 1234
TOUT = 1000
logger = logging.getLogger(__name__)


def is_component_running(status: dict | Status) -> bool:
    """
    Returns whether a component is actively running, supporting both the
    driverinterface_2_1 dict-based status (with a plain "running" key) and the
    driverinterface_3_0 Status object (with "state" and "connected" fields).
    """
    if isinstance(status, dict):
        return bool(status.get("running", False))
    else:
        return status.state in {"meas", "task"}


def triggered_pattern_index(ctx):
    """Extracts the "index" field from a pattern-matching Input's triggered id."""
    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
    return json.loads(trigger_id)["index"]


def get_unit_str(units: str | None) -> str:
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


def format_constraint(val: Any, base_unit: str | None) -> str:
    """
    Formats constraint values (min/max) with their respective units.

    If the constraint value is a Pint Quantity, it is formatted with its own units,
    trying to convert to the attribute's base unit first if compatible.
    Otherwise, it is formatted using the base unit.
    """
    if val is None:
        return ""
    if isinstance(val, pint.Quantity):
        if base_unit:
            try:
                # Convert to base_unit to keep it consistent if compatible
                val = val.to(base_unit)
            except pint.errors.DimensionalityError:
                logger.error("could not convert val '%s' to unit '%s'", val, base_unit)
        mag = val.m
        u_str = get_unit_str(val.units)
        return f"{mag} {u_str}" if u_str else str(mag)
    else:
        mag = val
        u_str = get_unit_str(base_unit)
        return f"{mag} {u_str}" if u_str else str(mag)


def format_obj(
    obj: dict,
    headers,
    attrs,
    otype,
    port,
    formatters: dict[str, Callable[[Any], Any]] | None = None,
    full_width_attrs: list[str] | None = None,
    align_columns: bool = False,
) -> html.Div:
    if not obj:
        return html.Div(
            "No registered elements found.",
            className="text-secondary",
            style={"text-align": "center", "padding": "20px"},
        )

    full_width = set(full_width_attrs or [])
    # align_columns puts items on a grid, where full_width_attrs span the whole row
    if align_columns:
        item_style = {"min-width": "0", "overflow-wrap": "anywhere"}
        row_style = {
            "display": "grid",
            "grid-template-columns": "repeat(auto-fill, minmax(240px, 1fr))",
            "gap": "10px 35px",
            "align-items": "baseline",
        }
    else:
        item_style = {"margin-right": "35px"}
        row_style = {"display": "flex", "flex-wrap": "wrap", "gap": "10px"}

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
                className="entity-link",
                style={
                    "font-size": "18px",
                    "font-weight": "700",
                },
            )
        else:
            # Not a link, so use the plain text color instead of the accent color
            title_el = html.Span(
                name_str,
                style={
                    "font-size": "18px",
                    "font-weight": "700",
                    "color": "var(--text-color)",
                },
            )

        # Build metadata elements
        metadata_items = []

        # We skip the first attribute (name) because it is the title
        for idx, attr in enumerate(attrs[1:]):
            header_label = headers[idx + 1]
            val = v.get(attr, "")
            if isinstance(val, (list, tuple, set)):
                val_str = ", ".join(str(x) for x in val)
            else:
                val_str = str(val)

            # Skip capabilities in metadata block (will render separately)
            if attr == "capabilities":
                continue

            formatter = (formatters or {}).get(attr)
            val_el = formatter(val) if formatter else html.Span(val_str)
            style = (
                {**item_style, "grid-column": "1 / -1"}
                if attr in full_width
                else item_style
            )
            metadata_items.append(
                html.Div(
                    children=[html.Strong(f"{header_label}: "), val_el], style=style
                )
            )

        details_row = html.Div(
            children=metadata_items,
            style={**row_style, "margin-bottom": "10px", "font-size": "14px"},
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
            cap_val = v["capabilities"]
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
    ret = passata.get_attrs(port=port, name=name, attrs=attrs, timeout=TOUT)
    if ret.success and ret.data is not None:
        vals: dict = ret.model_dump()["data"]
    else:
        vals = {}
    return vals


def pretty(val: Any, prec: bool = True) -> str:
    if isinstance(val, list):
        ret = f"[{pretty(val[0], False)},··· {pretty(val[-1], False)}] n={len(val)}"
    else:
        try:
            if prec:
                ret = f"{pint.Quantity(val):.5~gP}"
            else:
                ret = f"{pint.Quantity(val):.3~gP}"
        except (TypeError, pint.UndefinedUnitError):
            ret = str(val)
    return ret


def update_datastore(
    port: int,
    name: str,
    datastore: dict,
    cap: int | None = None,
) -> dict | dash.NoUpdate:
    ret = passata.get_last_data(port=port, name=name, timeout=TOUT)
    logger.debug("ret=%s", str(ret))
    if not ret.success:
        return dash.no_update
    if ret.data is None:
        logger.warning("passata.get_last_data returned no data, erasing data store")
        return {}

    ndata = ret.data.to_dict()
    logger.debug("ndata=%s", str(ndata))
    # Simply return data if first load.
    if "coords" not in datastore:
        return ndata
    # Do not update if timestamp is already present.
    uts = ndata["coords"]["uts"]["data"][0]
    if uts in datastore["coords"]["uts"]["data"]:
        return dash.no_update
    # Go through data_vars and append last datapoint.
    datastore["coords"]["uts"]["data"].append(uts)
    for k, v in ndata["data_vars"].items():
        datastore["data_vars"][k]["data"].append(v["data"][0])
    datastore["dims"]["uts"] = len(datastore["coords"]["uts"]["data"])
    if cap is not None and datastore["dims"]["uts"] > cap:
        overflow = datastore["dims"]["uts"] - cap
        datastore["coords"]["uts"]["data"] = datastore["coords"]["uts"]["data"][
            overflow:
        ]
        for v in datastore["data_vars"].values():
            v["data"] = v["data"][overflow:]
        datastore["dims"]["uts"] = cap
    logger.debug("datastore=%s", str(datastore))
    return datastore


def is_relative_path(path: str | None) -> bool:
    """Whether path is non-empty and absolute on neither Windows nor POSIX."""
    path = (path or "").strip()
    return bool(path) and not (
        PureWindowsPath(path).is_absolute() or PurePosixPath(path).is_absolute()
    )


def list_drives() -> list[str]:
    """Lists the Windows drive roots; empty elsewhere."""
    if sys.platform != "win32":
        return []
    mask = ctypes.windll.kernel32.GetLogicalDrives()
    return [f"{chr(65 + i)}:\\" for i in range(26) if mask >> i & 1]


def is_dir_entry(entry: os.DirEntry) -> bool:
    try:
        return entry.is_dir()
    except OSError:
        return False


def list_subfolders(path: str) -> tuple[list[tuple[str, str]], str | None]:
    """Returns ([(label, full path)], error); an empty path lists the drives."""
    if not path:
        return [(d, d) for d in list_drives()], None
    try:
        with os.scandir(path) as it:
            names = [e.name for e in it if is_dir_entry(e)]
    except OSError as e:
        return [], str(e)
    return [(n, os.path.join(path, n)) for n in sorted(names, key=str.lower)], None


def start_folder(path: str | None) -> str:
    """Nearest existing folder of path, else the home folder."""
    path = (path or "").strip()
    if path and not is_relative_path(path):
        path = os.path.normpath(path)
        while not os.path.isdir(path):
            parent = os.path.dirname(path)
            if parent == path:
                break
            path = parent
        if os.path.isdir(path):
            return path
    return str(Path.home())


def parent_folder(path: str | None) -> str | None:
    """Parent of path; a Windows drive root has the drive list ("") as its parent."""
    if not path:
        return path
    parent = os.path.dirname(path)
    if parent != path:
        return parent
    return "" if sys.platform == "win32" else path


def object_from_attrs(
    cname: str,
    aname: str,
    attr: Attr,
    value: str,
) -> dcc.Dropdown | dcc.Input:
    if attr.rw:
        if attr.options is not None:
            obj = dcc.Dropdown(
                id={"type": "attr-input", "index": f"{cname}/{aname}"},
                options=sorted(attr.options),
                value=value,
                clearable=False,
                className="attr-control mutable-input",
            )
        else:
            obj = dcc.Input(
                id={"type": "attr-input", "index": f"{cname}/{aname}"},
                debounce=True,
                value=value,
                type="text",
                className="attr-control mutable-input",
            )
    else:
        obj = dcc.Input(
            id={"type": "attr-display", "index": f"{cname}/{aname}"},
            value=value,
            disabled=True,
            className="attr-control immutable-input",
        )
    return obj


def get_constraint_str(attr: Attr):
    constraints = []
    if attr.minimum is not None:
        constraints.append(f"min: {format_constraint(attr.minimum, attr.units)}")
    if attr.maximum is not None:
        constraints.append(f"man: {format_constraint(attr.maximum, attr.units)}")
    return f" ({', '.join(constraints)})" if constraints else ""


def create_header(otype: str, oname: str, badge: html.Div | None = None) -> html.Div:
    header = html.Div(
        children=[
            html.Div(
                children=[
                    dcc.Link(
                        f"← Back to {otype.capitalize()}s",
                        href=f"/{otype}s",
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
                        f"{otype.capitalize()}: {oname}",
                        className="inline",
                        style={"margin": 0, "font-size": "22px"},
                    ),
                    badge if badge is not None else html.Div(),
                ],
                style={"display": "flex", "align-items": "center"},
            )
        ],
        className="theme-header",
    )

    return html.Div(
        children=[header],
        className="header-wrapper",
    )


def build_attr_rows(attrs: dict[str, Attr], avals: dict[str, Any], cname: str) -> list:
    attr_rows = []
    for aname, attr in attrs.items():
        raw_val = avals.get(aname)
        val = raw_val.m if isinstance(raw_val, pint.Quantity) else raw_val
        control = object_from_attrs(cname, aname, attr, str(val))

        unit_str = get_unit_str(attr.units)
        constraints_str = get_constraint_str(attr)

        attr_val_store = dcc.Store(
            id={"type": "attr-val", "index": f"{cname}/{aname}"},
            data=val,
        )
        attr_param_store = dcc.Store(
            id={"type": "attr-param", "index": f"{cname}/{aname}"},
            data=attr.model_dump(
                include={"rw", "units", "options", "status"}, mode="json"
            ),
        )

        if attr.rw:
            apply_btn = html.Button(
                "Apply",
                id={"type": "attr-apply-btn", "index": f"{cname}/{aname}"},
                className="attr-apply-btn",
            )
        else:
            apply_btn = html.Div(className="attr-apply-btn")

        attr_rows.append(
            html.Div(
                children=[
                    html.Div(f"{aname}:", className="attr-label"),
                    control,
                    apply_btn,
                    html.Span(f" {unit_str}{constraints_str}", className="attr-unit"),
                    attr_val_store,
                    attr_param_store,
                ],
                className="attr-row",
            )
        )
    return attr_rows
