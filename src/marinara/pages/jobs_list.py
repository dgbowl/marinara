import logging

import dash
from dash import Input, Output, State, callback, dcc, html
from tomato import ketchup, tomato

from marinara.icons import get_icon
from marinara.utils import TOUT, format_obj, job_status_badge

logger = logging.getLogger(__name__)
dash.register_page(__name__, path="/jobs", title="Jobs")

layout = html.Div(
    className="dashboard-container",
    children=[
        html.Div(
            className="theme-header",
            children=[
                html.Div(
                    children=[
                        html.H2(
                            "Jobs",
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
                ),
                dcc.Link("+ New Job", href="/jobs/new", className="btn"),
            ],
        ),
        html.Div(
            id="tomato-list-jobs",
            className="text-secondary",
            children="Loading data...",
        ),
    ],
)


@callback(
    Output("tomato-list-jobs", "children"),
    Input("tomato-status", "n_clicks"),
    State("tomato-port", "data"),
)
def update_jobs_list(n_clicks, port):
    try:
        daemon_ret = tomato.status(stgrp="tomato", port=port, timeout=TOUT)
        if not daemon_ret.success:
            return html.Div(
                f"Tomato status error: {daemon_ret.msg}",
                className="text-secondary",
                style={"text-align": "center", "padding": "20px"},
            )
        ret = ketchup.status(daemon=daemon_ret.data, jobids=[])  # ty: ignore[invalid-argument-type]
        if not ret.success:
            if ret.msg == "job queue is empty":
                return html.Div(
                    "No active or historical jobs found.",
                    className="text-secondary",
                    style={"text-align": "center", "padding": "20px"},
                )
            logger.warning("ketchup.status returned failure: %s", ret.msg)
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

        jobs = {}
        for job in sorted(jobs_list, key=lambda j: j.id, reverse=True):
            # format_obj links each card's title to /jobs/<key>, so key on the id
            name = f"Job {job.id}" + (f" ({job.jobname})" if job.jobname else "")
            if job.completed_at:
                completed_at = str(job.completed_at).split(".")[0]
            else:
                completed_at = "-"
            jobs[str(job.id)] = {
                "name": name,
                "status": job.status,
                "submitted_at": str(job.submitted_at).split(".")[0],
                "completed_at": completed_at,
            }

        return format_obj(
            obj=jobs,
            headers=["Job", "Status", "Submitted At", "Completed At"],
            attrs=["name", "status", "submitted_at", "completed_at"],
            otype="jobs",
            port=port,
            formatters={"status": job_status_badge},
        )
    except Exception as e:
        logger.warning("Exception during update_jobs_list:", exc_info=e)
        return html.Div(
            f"Error loading jobs: {e!s}",
            className="text-secondary",
            style={"padding": "20px"},
        )
