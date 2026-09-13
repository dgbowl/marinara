from typing import Any

import dash
import pint
from dash import MATCH, Input, Output, State, callback
from tomato import passata

from marinara import utils
from marinara.utils import TOUT


def data_store_update():
    # Data Store Updater
    @callback(
        Output({"type": "data-store", "index": MATCH}, "data"),
        Input("interval", "n_intervals"),
        State("tomato-port", "data"),
        State({"type": "data-store", "index": MATCH}, "data"),
        State({"type": "data-store", "index": MATCH}, "id"),
    )
    def data_store_update(
        _: int,
        port: int,
        ds: dict,
        id: dict,
    ) -> dict | dash.NoUpdate:
        name = id["index"]
        ret = utils.update_datastore(port=port, name=name, datastore=ds)
        return ret


def periodic_attr_val_update():
    # Periodic updates for attr-val store values
    @callback(
        Output({"type": "attr-val", "index": MATCH}, "data"),
        Input("interval", "n_intervals"),
        State("tomato-port", "data"),
        State({"type": "attr-val", "index": MATCH}, "data"),
        State({"type": "attr-val", "index": MATCH}, "id"),
        prevent_initial_call=True,
    )
    def periodic_attr_val_update(
        _: int,
        port: int,
        old: Any,
        id: dict,
    ) -> Any | dash.NoUpdate:
        cname, attr = id["index"].split("/")
        new = utils.get_attrs_vals(port=port, name=cname, attrs=[attr]).get(attr)
        if isinstance(new, pint.Quantity):
            new = new.m
        if old == new:
            return dash.no_update
        return new


def update_readwrite_attr():
    # Change style of attr-apply-btn when attr-input does not match attr-val
    @callback(
        Output({"type": "attr-apply-btn", "index": MATCH}, "class"),
        Input({"type": "attr-val", "index": MATCH}, "data"),
        Input({"type": "attr-input", "index": MATCH}, "value"),
    )
    def update_readwrite_attr(val: Any, input: str) -> str:
        if (isinstance(val, (float, int)) and float(input) == val) or input == str(val):
            return "attr-apply-btn"
        else:
            return "attr-apply-btn-danger"


def set_component_attribute():
    # Input handler for read-write attribute updates via Apply button
    @callback(
        Output({"type": "attr-input", "index": MATCH}, "value"),
        Input({"type": "attr-apply-btn", "index": MATCH}, "n_clicks"),
        State({"type": "attr-input", "index": MATCH}, "value"),
        State({"type": "attr-input", "index": MATCH}, "id"),
        State("tomato-port", "data"),
        prevent_initial_call=True,
    )
    def set_component_attribute(
        _: int,
        value: str,
        id: dict[str, str],
        port: int,
    ) -> str:
        cname, attr = id["index"].split("/")
        passata.set_attr(port=port, name=cname, attr=attr, val=value, timeout=TOUT)
        val = utils.get_attrs_vals(port=port, name=cname, attrs=[attr]).get(attr)
        if isinstance(val, pint.Quantity):
            return str(val.m)
        else:
            return str(val)
