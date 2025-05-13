import dash
from dash import html, dcc

app = dash.Dash(__name__, use_pages=True, suppress_callback_exceptions=True)
app.layout = html.Div(dash.page_container)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
    # app.run(debug=True)
