import importlib.metadata

import dash
from dash import html, dcc
from marinara.sidebar import create_sidebar

__version__ = importlib.metadata.version("marinara")

app = dash.Dash(
    __name__,
    use_pages=True,
    suppress_callback_exceptions=True,
    title="Marinara",
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
                create_sidebar(__version__),
                html.Div(
                    className="main-content-wrapper",
                    children=[html.Div(dash.page_container, className="page-content")],
                ),
            ],
        ),
    ],
)

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=8050)
