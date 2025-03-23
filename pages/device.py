import dash
from dash import html

dash.register_page(__name__, path_template="/device/<port>/<name>")


def layout(port=None, name=None, **_):
    return html.Div(f"The user requested device {name=}")
