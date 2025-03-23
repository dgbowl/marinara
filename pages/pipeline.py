import dash
from dash import html

dash.register_page(__name__, path_template="/pipelines/<port>/<name>")


def layout(port=None, name=None, **_):
    return html.Div(f"The user requested pipeline {name=}")
