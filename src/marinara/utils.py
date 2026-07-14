import zmq
from dash import html, dcc
import tomato

PORT = 1234
TOUT = 1000
CTXT = zmq.Context()
kwargs = dict(timeout=TOUT, context=CTXT)

def get_field(obj, key, default=""):
    if hasattr(obj, key):
        val = getattr(obj, key)
        return val if val is not None else default
    elif isinstance(obj, dict):
        val = obj.get(key, default)
        return val if val is not None else default
    return default

def clean_value(val):
    if hasattr(val, "magnitude"):
        val = val.magnitude
    if hasattr(val, "m"):
        val = val.m
    if hasattr(val, "item") and callable(val.item):
        try:
            val = val.item()
        except Exception:
            pass
    return val

def clean_dict_values(d):
    if isinstance(d, dict):
        return {k: clean_dict_values(v) for k, v in d.items()}
    elif isinstance(d, list):
        return [clean_dict_values(v) for v in d]
    elif isinstance(d, tuple):
        return tuple(clean_dict_values(v) for v in d)
    else:
        return clean_value(d)

def format_obj(obj, headers, attrs, otype, port):
    if not obj:
        return html.Div("No registered elements found.", className="text-secondary", style={"text-align": "center", "padding": "20px"})
        
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
                style={"font-size": "18px", "font-weight": "700", "text-decoration": "none", "color": "var(--accent-color)"}
            )
        else:
            title_el = html.Span(
                name_str,
                style={"font-size": "18px", "font-weight": "700", "color": "var(--accent-color)"}
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
                    children=[
                        html.Strong(f"{header_label}: "),
                        html.Span(val_str)
                    ],
                    style={"margin-right": "35px"}
                )
            )
            
        details_row = html.Div(
            children=metadata_items,
            style={"display": "flex", "flex-wrap": "wrap", "margin-bottom": "10px", "font-size": "14px", "gap": "10px"}
        )
        
        card_children = [
            html.Div(
                children=[title_el],
                style={"display": "flex", "align-items": "center", "margin-bottom": "15px"}
            ),
            details_row
        ]
        
        # If there are capabilities, render them beautifully
        if "capabilities" in attrs:
            cap_val = get_field(v, "capabilities", [])
            if cap_val:
                cap_str = ", ".join(str(x) for x in cap_val) if isinstance(cap_val, (list, set, tuple)) else str(cap_val)
            else:
                cap_str = "None"
            
            card_children.append(
                html.Div(
                    children=[
                        html.Div(
                            "Capabilities Info",
                            style={"font-weight": "600", "font-size": "14px", "margin-top": "15px", "border-bottom": "1px solid var(--border-color)", "padding-bottom": "5px", "margin-bottom": "10px"}
                        ),
                        html.Div(
                            cap_str,
                            className="text-secondary",
                            style={"font-size": "13px"}
                        )
                    ]
                )
            )
            
        cards.append(
            html.Div(
                className="card",
                style={"margin-bottom": "20px", "padding": "20px"},
                children=card_children
            )
        )
        
    return html.Div(cards)



def get_tomato_status(port):
    try:
        ret = tomato.status(stgrp="tomato", port=port, **kwargs)
        if not ret.success:
            return None
        return ret.data
    except Exception:
        return None
