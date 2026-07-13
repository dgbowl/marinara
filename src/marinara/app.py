import dash
from dash import html, dcc, Output, Input, State, ALL

app = dash.Dash(__name__, use_pages=True, suppress_callback_exceptions=True, title="Marinara")

sidebar = html.Div(
    className="sidebar",
    children=[
        html.Div(
            className="sidebar-logo",
            children=[
                html.Span("🍅", style={"font-size": "26px"}),
                html.H3("marinara")
            ]
        ),
        html.Div(
            className="sidebar-menu",
            children=[
                dcc.Link([html.Span("📊", style={"margin-right": "10px"}), "Dashboard"], href="/", className="sidebar-link", id="link-dashboard"),
                dcc.Link([html.Span("🔄", style={"margin-right": "10px"}), "Pipelines"], href="/pipelines", className="sidebar-link", id="link-pipelines"),
                dcc.Link([html.Span("⚙️", style={"margin-right": "10px"}), "Drivers"], href="/drivers", className="sidebar-link", id="link-drivers"),
                dcc.Link([html.Span("🔌", style={"margin-right": "10px"}), "Devices"], href="/devices", className="sidebar-link", id="link-devices"),
                dcc.Link([html.Span("🧩", style={"margin-right": "10px"}), "Components"], href="/components", className="sidebar-link", id="link-components"),
                dcc.Link([html.Span("📋", style={"margin-right": "10px"}), "Jobs"], href="/jobs", className="sidebar-link", id="link-jobs"),
            ]
        ),
        html.Div(
            className="sidebar-footer",
            children=[
                # Row 1: System status and Theme toggle icon button
                html.Div(
                    children=[
                        html.Div(
                            className="system-status-container",
                            children=[
                                html.Span(className="status-dot"),
                                html.Span("System: Connected", style={"color": "#10b981", "font-weight": "600", "font-size": "13px"})
                            ]
                        ),
                        html.Button(
                            id="theme-toggle-btn",
                            children="🌙",
                            className="theme-toggle-btn",
                            style={
                                "background": "none",
                                "border": "none",
                                "font-size": "18px",
                                "cursor": "pointer",
                                "padding": "5px",
                                "display": "flex",
                                "align-items": "center",
                                "justify-content": "center"
                            }
                        )
                    ],
                    style={"display": "flex", "align-items": "center", "justify-content": "space-between", "width": "100%", "margin-bottom": "8px"}
                ),
                # Row 2: Port setter input only
                html.Div(
                    children=[
                        html.Span("Port:", style={"font-weight": "600", "font-size": "13px", "color": "var(--text-color)"}),
                        dcc.Input(
                            value=1234,
                            type="number",
                            id="tomato-port-setter",
                            className="port-input"
                        ),
                    ],
                    style={"display": "flex", "align-items": "center", "gap": "8px", "width": "100%"}
                ),
                html.Div("Tomato Port: 1234", className="text-secondary", id="sidebar-port-display", style={"font-size": "11px", "margin-top": "4px"})
            ],
            style={"padding": "12px 0", "border-top": "1px solid var(--border-color)", "display": "flex", "flex-direction": "column", "align-items": "flex-start"}
        )
    ]
)

app.layout = html.Div(
    id="app-container",
    children=[
        dcc.Location(id="url", refresh=False),
        dcc.Store(id="app-theme-store", storage_type="local", data="light"),
        dcc.Store(id="tomato-port", storage_type="local", data=1234),
        html.Div(
            className="main-layout",
            children=[
                sidebar,
                html.Div(
                    className="main-content-wrapper",
                    children=[
                        html.Div(
                            dash.page_container,
                            className="page-content"
                        )
                    ]
                )
            ]
        )
    ]
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
    Input("theme-toggle-btn", "n_clicks"),
    State("app-theme-store", "data"),
)
def toggle_theme(n_clicks, current_theme):
    if n_clicks is None:
        theme = current_theme or "light"
        icon = "🌙" if theme == "light" else "☀️"
        return theme, icon
        
    new_theme = "dark" if current_theme == "light" else "light"
    icon = "🌙" if new_theme == "light" else "☀️"
    return new_theme, icon

@app.callback(
    Output("tomato-port", "data"),
    Input("tomato-port-setter", "value")
)
def store_tomato_port(value):
    if value is None:
        return 1234
    return int(value)

@app.callback(
    Output("sidebar-port-display", "children"),
    Input("tomato-port", "data"),
    prevent_initial_call=True
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

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1")
