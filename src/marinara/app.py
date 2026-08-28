import importlib.metadata

import dash
from dash import Input, Output, State, dcc, html

from marinara.icons import get_icon

try:
    __version__ = importlib.metadata.version("marinara")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.1"

app = dash.Dash(
    __name__,
    use_pages=True,
    suppress_callback_exceptions=True,
    title="Marinara",
)

sidebar = html.Div(
    id="app-sidebar",
    className="sidebar",
    children=[
        html.Div(
            className="sidebar-logo",
            children=[
                dcc.Link(
                    children=[
                        get_icon("tomato", size=26),
                        html.H3("marinara", id="sidebar-logo-text"),
                    ],
                    href="/",
                    style={
                        "display": "flex",
                        "align-items": "center",
                        "gap": "12px",
                        "flex-grow": "1",
                        "text-decoration": "none",
                        "color": "inherit",
                    },
                ),
                html.Button(
                    id="sidebar-toggle-btn",
                    children=get_icon("chevron-left", size=18),
                    className="sidebar-toggle-btn",
                    style={
                        "background": "none",
                        "border": "none",
                        "color": "var(--sidebar-text)",
                        "cursor": "pointer",
                        "padding": "5px",
                        "display": "flex",
                        "align-items": "center",
                        "justify-content": "center",
                    },
                ),
            ],
            style={
                "display": "flex",
                "align-items": "center",
                "justify-content": "space-between",
                "width": "100%",
            },
        ),
        html.Div(
            className="sidebar-menu",
            children=[
                dcc.Link(
                    [
                        get_icon("dashboard", size=16),
                        html.Span("Dashboard", className="sidebar-link-text"),
                    ],
                    href="/",
                    className="sidebar-link",
                    id="link-dashboard",
                ),
                dcc.Link(
                    [
                        get_icon("pipelines", size=16),
                        html.Span("Pipelines", className="sidebar-link-text"),
                    ],
                    href="/pipelines",
                    className="sidebar-link",
                    id="link-pipelines",
                ),
                dcc.Link(
                    [
                        get_icon("drivers", size=16),
                        html.Span("Drivers", className="sidebar-link-text"),
                    ],
                    href="/drivers",
                    className="sidebar-link",
                    id="link-drivers",
                ),
                dcc.Link(
                    [
                        get_icon("devices", size=16),
                        html.Span("Devices", className="sidebar-link-text"),
                    ],
                    href="/devices",
                    className="sidebar-link",
                    id="link-devices",
                ),
                dcc.Link(
                    [
                        get_icon("components", size=16),
                        html.Span("Components", className="sidebar-link-text"),
                    ],
                    href="/components",
                    className="sidebar-link",
                    id="link-components",
                ),
                dcc.Link(
                    [
                        get_icon("jobs", size=16),
                        html.Span("Jobs", className="sidebar-link-text"),
                    ],
                    href="/jobs",
                    className="sidebar-link",
                    id="link-jobs",
                ),
            ],
        ),
        html.Div(
            className="sidebar-footer",
            children=[
                # Row 1: System status and Theme toggle icon button
                html.Div(
                    id="sidebar-footer-row1",
                    children=[
                        html.Div(
                            className="system-status-container",
                            children=[
                                html.Span(className="status-dot"),
                                html.Span(
                                    "System: Connected",
                                    className="system-status-text",
                                    style={
                                        "color": "#10b981",
                                        "font-weight": "600",
                                        "font-size": "13px",
                                    },
                                ),
                            ],
                        ),
                        html.Button(
                            id="theme-toggle-btn",
                            children=get_icon("moon", size=18),
                            className="theme-toggle-btn",
                            style={
                                "background": "none",
                                "border": "none",
                                "font-size": "18px",
                                "cursor": "pointer",
                                "padding": "5px",
                                "display": "flex",
                                "align-items": "center",
                                "justify-content": "center",
                            },
                        ),
                    ],
                    style={
                        "display": "flex",
                        "align-items": "center",
                        "justify-content": "space-between",
                        "width": "100%",
                        "margin-bottom": "8px",
                    },
                ),
                # Row 2: Port setter input only
                html.Div(
                    className="sidebar-footer-row2",
                    children=[
                        html.Span(
                            "Port:",
                            style={
                                "font-weight": "600",
                                "font-size": "13px",
                                "color": "var(--text-color)",
                            },
                        ),
                        dcc.Input(
                            value=str(1234),
                            type="text",
                            id="tomato-port-setter",
                            className="port-input",
                            debounce=True,
                        ),
                    ],
                    style={
                        "display": "flex",
                        "align-items": "center",
                        "gap": "8px",
                        "width": "100%",
                    },
                ),
                html.Div(
                    children=[
                        html.Span("Tomato Port: 1234", id="sidebar-port-display"),
                        html.Span(
                            f"v{__version__}",
                            style={"margin-left": "auto", "opacity": "0.7"},
                        ),
                    ],
                    className="text-secondary",
                    style={
                        "font-size": "11px",
                        "margin-top": "4px",
                        "display": "flex",
                        "justify-content": "space-between",
                        "width": "100%",
                        "padding-right": "8px",
                    },
                ),
            ],
            style={
                "padding": "12px 0",
                "border-top": "1px solid var(--border-color)",
                "display": "flex",
                "flex-direction": "column",
                "align-items": "flex-start",
            },
        ),
    ],
)

app.layout = html.Div(
    id="app-container",
    children=[
        dcc.Location(id="url", refresh=False),
        dcc.Store(id="app-theme-store", storage_type="local", data="light"),
        dcc.Store(id="tomato-port", storage_type="local", data=1234),
        dcc.Store(id="sidebar-state-store", storage_type="local", data="expanded"),
        html.Div(
            className="main-layout",
            children=[
                sidebar,
                html.Div(
                    className="main-content-wrapper",
                    children=[html.Div(dash.page_container, className="page-content")],
                ),
            ],
        ),
    ],
)


@app.callback(
    Output("app-container", "className"),
    Input("app-theme-store", "data"),
)
def update_theme_class(theme):
    if theme == "dark":
        return "dark-theme"
    return "light-theme"


@app.callback(
    Output("app-theme-store", "data"),
    Output("theme-toggle-btn", "children"),
    Output("theme-toggle-btn", "title"),
    Input("theme-toggle-btn", "n_clicks"),
    State("app-theme-store", "data"),
)
def toggle_theme(n_clicks, current_theme):
    if n_clicks is None:
        theme = current_theme or "light"
        icon = (
            get_icon("moon", size=18) if theme == "light" else get_icon("sun", size=18)
        )
        tooltip = "Dark Mode" if theme == "light" else "Light Mode"
        return theme, icon, tooltip

    new_theme = "dark" if current_theme == "light" else "light"
    icon = (
        get_icon("moon", size=18) if new_theme == "light" else get_icon("sun", size=18)
    )
    tooltip = "Dark Mode" if new_theme == "light" else "Light Mode"
    return new_theme, icon, tooltip


@app.callback(Output("tomato-port", "data"), Input("tomato-port-setter", "value"))
def store_tomato_port(value):
    if value is None:
        return 1234
    try:
        return int(value)
    except ValueError:
        return 1234


@app.callback(
    Output("sidebar-port-display", "children"),
    Input("tomato-port", "data"),
    prevent_initial_call=True,
)
def update_sidebar_port(port):
    if port is None:
        return "Tomato Port: 1234"
    return f"Tomato Port: {port}"


@app.callback(
    Output("link-dashboard", "className"),
    Output("link-pipelines", "className"),
    Output("link-drivers", "className"),
    Output("link-devices", "className"),
    Output("link-components", "className"),
    Output("link-jobs", "className"),
    Input("url", "pathname"),
)
def update_sidebar_active_classes(pathname):
    classes = ["sidebar-link"] * 6
    if pathname == "/":
        classes[0] = "sidebar-link active"
    elif pathname.startswith("/pipelines"):
        classes[1] = "sidebar-link active"
    elif pathname.startswith("/drivers") or pathname.startswith("/driver"):
        classes[2] = "sidebar-link active"
    elif pathname.startswith("/devices") or pathname.startswith("/device"):
        classes[3] = "sidebar-link active"
    elif pathname.startswith("/components") or pathname.startswith("/component"):
        classes[4] = "sidebar-link active"
    elif pathname.startswith("/jobs"):
        classes[5] = "sidebar-link active"
    return tuple(classes)


@app.callback(
    Output("sidebar-state-store", "data"),
    Input("sidebar-toggle-btn", "n_clicks"),
    State("sidebar-state-store", "data"),
)
def toggle_sidebar_state(n_clicks, current_state):
    if n_clicks is None or n_clicks == 0:
        return current_state or "expanded"
    return "collapsed" if current_state == "expanded" else "expanded"


@app.callback(
    Output("app-sidebar", "className"),
    Output("sidebar-toggle-btn", "children"),
    Output("sidebar-toggle-btn", "title"),
    Input("sidebar-state-store", "data"),
)
def apply_sidebar_state(state):
    if state == "collapsed":
        return (
            "sidebar collapsed",
            get_icon("chevron-right", size=18),
            "Open the sidebar",
        )
    return "sidebar", get_icon("chevron-left", size=18), "Close the sidebar"


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=8050)
