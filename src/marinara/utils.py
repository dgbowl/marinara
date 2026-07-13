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
        # Determine plurality/path type for links
        path_type = otype
        if otype == "device":
            path_type = "devices"
            
        name_str = str(k)
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
            
        # The table headers and attrs excluding the first one (Name)
        table_headers = headers[1:]
        table_attrs = attrs[1:]
        
        # Determine table column class based on columns count
        col_class = "stgrp-5col" if len(table_headers) == 5 else "stgrp-3col" if len(table_headers) == 3 else ""
        
        row_cells = []
        for attr in table_attrs:
            val = get_field(v, attr, "")
            if isinstance(val, list) or isinstance(val, tuple) or isinstance(val, set):
                val_str = ", ".join(str(x) for x in val)
            else:
                val_str = str(val)
            row_cells.append(html.Td(val_str))
            
        table_el = html.Table(
            children=[
                html.Tr(children=[html.Th(h) for h in table_headers]),
                html.Tr(children=row_cells)
            ],
            className=f"stgrp {col_class}",
            style={"margin-top": "10px", "border": "1px solid var(--border-color)", "font-size": "13px"}
        )
        
        cards.append(
            html.Div(
                className="card",
                style={"margin-bottom": "20px", "padding": "20px"},
                children=[
                    html.Div(
                        children=[title_el],
                        style={"display": "flex", "align-items": "center", "margin-bottom": "15px"}
                    ),
                    table_el
                ]
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
