from typing import Any

import dash
import pint
from dash import ALL, MATCH, Input, Output, State, callback
from tomato import passata

from marinara import utils
from marinara.utils import TOUT


def periodic_data_store_update():
    # Data Store Updater
    @callback(
        Output({"type": "data-store", "index": MATCH}, "data"),
        Input("interval", "n_intervals"),
        State("tomato-port", "data"),
        State({"type": "data-store", "index": MATCH}, "data"),
        State({"type": "data-store", "index": MATCH}, "id"),
    )
    def periodic_data_store_update(
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


def attr_display_val_update():
    # Keeps a read-only attribute's displayed value in sync with its
    # periodically-refreshed attr-val store, with rounding (per #50).
    @callback(
        Output({"type": "attr-display", "index": MATCH}, "value"),
        Input({"type": "attr-val", "index": MATCH}, "data"),
    )
    def attr_display_val_update(val: Any) -> str:
        if isinstance(val, float):
            val = round(val, 3)
        return str(val)


def attr_apply_btn_update():
    # Change style of attr-apply-btn when attr-input does not match attr-val
    @callback(
        Output({"type": "attr-apply-btn", "index": MATCH}, "class"),
        Input({"type": "attr-val", "index": MATCH}, "data"),
        Input({"type": "attr-input", "index": MATCH}, "value"),
    )
    def attr_apply_btn_update(val: Any, input: str) -> str:
        if (isinstance(val, (float, int)) and float(input) == val) or input == str(val):
            return "attr-apply-btn"
        else:
            return "attr-apply-btn-danger"


def attr_input_action_update_value():
    # Input handler for read-write attribute updates via Apply button
    @callback(
        Output({"type": "attr-input", "index": MATCH}, "value"),
        Input({"type": "attr-apply-btn", "index": MATCH}, "n_clicks"),
        State({"type": "attr-input", "index": MATCH}, "value"),
        State({"type": "attr-input", "index": MATCH}, "id"),
        State("tomato-port", "data"),
        prevent_initial_call=True,
    )
    def attr_input_action_update_value(
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


def periodic_status_store_update():
    @callback(
        Output({"type": "status-store", "index": MATCH}, "data"),
        Input("interval", "n_intervals"),
        State("tomato-port", "data"),
        State({"type": "status-store", "index": MATCH}, "data"),
        State({"type": "status-store", "index": MATCH}, "id"),
    )
    def periodic_status_store_update(
        _: int,
        port: int,
        odata: bool,
        id: dict,
    ) -> bool | dash.NoUpdate:
        cname = id["index"]
        status_ret = passata.status(port=port, name=cname, timeout=TOUT)
        if status_ret.success and status_ret.data is not None:
            running = utils.is_component_running(status_ret.data)
        else:
            running = False
        if odata == running:
            return dash.no_update
        return running


def attr_input_disable_status():
    @callback(
        Output({"type": "attr-input", "index": ALL}, "disabled", allow_duplicate=True),
        Input({"type": "status-store", "index": MATCH}, "data"),
        Input({"type": "status-store", "index": MATCH}, "id"),
        State({"type": "attr-param", "index": ALL}, "data"),
        State({"type": "attr-param", "index": ALL}, "id"),
        prevent_initial_call=True,
    )
    def attr_input_disable_status(
        status: bool,
        id: dict,
        attrs: dict,
        aids: dict,
    ) -> list[bool | dash.NoUpdate]:
        ret = []
        for aid, attr in zip(aids, attrs):
            cname, _ = aid["index"].split("/")
            if cname != id["index"]:
                ret.append(dash.no_update)
                continue
            disable = not attr["rw"] or status
            ret.append(disable)
        return ret


def badge_update():
    @callback(
        Output({"type": "badge", "index": MATCH}, "children"),
        Output({"type": "badge", "index": MATCH}, "className"),
        Input({"type": "status-store", "index": MATCH}, "data"),
    )
    def badge_update(
        status: bool,
    ) -> tuple[str, str]:
        status_badge_class = (
            "badge badge-success" if status else "badge badge-secondary"
        )
        status_badge_text = "RUNNING" if status else "STOPPED"

        return status_badge_text, status_badge_class
