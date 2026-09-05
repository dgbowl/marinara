import logging

import dash
from dash import Input, Output, State, callback, html
from tomato import tomato

from marinara.icons import get_icon
from marinara.utils import format_obj, kwargs

logger = logging.getLogger(__name__)
dash.register_page(__name__, path="/components", title="Components")

layout = html.Div(
    className="dashboard-container",
    children=[
        html.Div(
            className="theme-header",
            children=[
                html.Div(
                    children=[
                        html.H2(
                            "Components",
                            className="inline",
                            style={"margin": 0, "font-size": "22px"},
                        ),
                        html.Button(
                            get_icon("refresh", size=14, stroke_width=2.5),
                            id="tomato-status",
                            className="btn-reload",
                            title="Reload status data",
                        ),
                    ],
                    style={"display": "flex", "align-items": "center"},
                )
            ],
        ),
        html.Div(
            id="tomato-list-components",
            className="text-secondary",
            children="Loading data...",
        ),
    ],
)


@callback(
    Output("tomato-list-components", "children"),
    Input("tomato-status", "n_clicks"),
    State("tomato-port", "data"),
)
def update_components(n_clicks: int, port: int) -> html.Div:
    try:
        ret = tomato.status(stgrp="tomato", port=port, **kwargs)
        if not ret.success:
            logger.warning("tomato.status returned failure: %s", ret.msg)
            return html.Div(
                f"No data found. Error: {ret.msg}. Please check the reload button above.",
                className="text-secondary",
                style={"text-align": "center", "padding": "20px"},
            )
        cmps_ret = tomato.status(stgrp="components", port=port, **kwargs)
        cmps = cmps_ret.data if cmps_ret.success else {}
        # Live components data only has name/driver/device/capabilities.
        # address/channel come from the static config; role comes from
        # scanning which pipeline uses each component under which role.
        static_cmps = ret.data.devicefile.components
        role_lookup = {}
        for pipn in ret.data.devicefile.pipelines.values():
            for role, cname in pipn.components.items():
                role_lookup[cname] = role
        for cname, cval in cmps.items():
            static = static_cmps.get(cname)
            if static:
                cval["address"] = static.address
                cval["channel"] = static.channel
            cval["role"] = role_lookup.get(cname, "")
        return format_obj(
            obj=cmps,
            headers=[
                "Component Name",
                "Driver",
                "Address",
                "Channel",
                "Role",
                "Capabilities",
            ],
            attrs=["name", "driver", "address", "channel", "role", "capabilities"],
            otype="components",
            port=port,
        )
    except Exception as e:
        logger.warning("Exception during update_components:", exc_info=e)
        return html.Div(
            f"Error loading components: {e!s}",
            className="text-secondary",
            style={"padding": "20px"},
        )
