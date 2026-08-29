import json

import dash
from dash import Input, Output, State, callback, html
from tomato import ketchup

from marinara.icons import get_icon
from marinara.utils import clean_data, kwargs

dash.register_page(__name__, path="/jobs", title="Jobs")

# Layout with only a single card for raw jobs data
layout = html.Div(
    className="dashboard-container",
    children=[
        html.Div(
            className="theme-header",
            children=[
                html.Div(
                    children=[
                        html.H2(
                            "Jobs Queue (Raw Data)",
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
            className="card",
            children=[
                html.Div(
                    id="tomato-list-jobs",
                    className="text-secondary",
                    style={"padding": "15px"},
                    children="Loading...",
                )
            ],
        ),
    ],
)


# Callback to render the full raw JSON of all jobs
@callback(
    Output("tomato-list-jobs", "children"),
    Input("tomato-status", "n_clicks"),
    State("tomato-port", "data"),
)
def update_jobs_list(n_clicks, port):
    try:
        ret = ketchup.status(port=port, verbosity=20, jobids=[], **kwargs)
        if not ret.success:
            if ret.msg == "job queue is empty":
                return html.Div(
                    "No active or historical jobs found.",
                    className="text-secondary",
                    style={"text-align": "center", "padding": "20px"},
                )
            return html.Div(
                f"No data found. Error: {ret.msg}",
                className="text-secondary",
                style={"text-align": "center", "padding": "20px"},
            )

        jobs_list = ret.data
        if not jobs_list:
            return html.Div(
                "No active or historical jobs found.",
                className="text-secondary",
                style={"text-align": "center", "padding": "20px"},
            )

        # Convert jobs list to list of clean dictionaries
        cleaned_jobs = []
        for job in jobs_list:
            v_dict = job.model_dump() if hasattr(job, "model_dump") else job
            cleaned_jobs.append(clean_data(v_dict))

        return html.Pre(
            json.dumps(cleaned_jobs, indent=2),
            style={
                "font-family": "monospace",
                "font-size": "13px",
                "overflow-x": "auto",
                "padding": "15px",
                "background-color": "rgba(0,0,0,0.01)",
                "border-radius": "6px",
                "margin": 0,
            },
        )
    except Exception as e:
        return html.Div(
            f"Error loading jobs: {e!s}",
            className="text-secondary",
            style={"padding": "20px"},
        )
