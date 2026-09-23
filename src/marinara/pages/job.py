import logging

import dash
import yaml
from dash import Input, Output, State, callback, dcc, html
from tomato import ketchup, tomato

from marinara.utils import TOUT, create_header, job_status_badge, labeled_row

logger = logging.getLogger(__name__)
dash.register_page(__name__, path_template="/jobs/<id>")


def layout(id: str, **_) -> list[html.Div | dcc.Store]:
    return [
        create_header("job", id),
        dcc.Store(id="job-id-store", data=id),
        # Kept outside job-detail-container, which update_job_detail regenerates
        # every second - a result shown there would get wiped within a second.
        html.Div(
            children=[
                html.Button("Take Snapshot", id="job-snapshot-btn", className="btn"),
                html.Span(id="job-snapshot-result", style={"margin-left": "12px"}),
            ],
            style={"margin-bottom": "20px"},
        ),
        html.Div(
            id="job-detail-container",
            className="text-secondary",
            children="Loading job details...",
        ),
    ]


def detail_row(label: str, value) -> html.Div:
    return labeled_row(label, html.Span(str(value)), {"margin-bottom": "10px"})


# Requests an up-to-date snapshot of the job's data from tomato; the resulting
# "snapshot.<id>.nc" lands in the cwd of the ketchup process (i.e. wherever
# marinara was launched from), and tomato doesn't report that path back, so we
# can only surface its message.
@callback(
    Output("job-snapshot-result", "children"),
    Input("job-snapshot-btn", "n_clicks"),
    State("tomato-port", "data"),
    State("job-id-store", "data"),
    prevent_initial_call=True,
)
def take_job_snapshot(n_clicks, port, job_id):
    try:
        job_id_int = int(job_id)
    except (TypeError, ValueError):
        return html.Span(f"Invalid job id: {job_id!r}", className="text-secondary")

    try:
        daemon_ret = tomato.status(stgrp="tomato", port=port, timeout=TOUT)
        if not daemon_ret.success:
            return html.Span(
                f"Tomato status error: {daemon_ret.msg}", className="text-secondary"
            )
        ret = ketchup.snapshot(jobids=[job_id_int], daemon=daemon_ret.data)
        className = "badge badge-success" if ret.success else "text-secondary"
        return html.Span(ret.msg, className=className)
    except Exception as e:
        logger.warning("Exception during take_job_snapshot:", exc_info=e)
        return html.Span(f"Error creating snapshot: {e!s}", className="text-secondary")


@callback(
    Output("job-detail-container", "children"),
    Input("interval", "n_intervals"),
    State("tomato-port", "data"),
    State("job-id-store", "data"),
)
def update_job_detail(n_intervals, port, job_id):
    try:
        job_id_int = int(job_id)
    except (TypeError, ValueError):
        return html.Div(f"Invalid job id: {job_id!r}", className="text-secondary")

    try:
        daemon_ret = tomato.status(stgrp="tomato", port=port, timeout=TOUT)
        if not daemon_ret.success:
            return html.Div(
                f"Tomato status error: {daemon_ret.msg}",
                className="text-secondary",
                style={"text-align": "center", "padding": "20px"},
            )
        ret = ketchup.status(daemon=daemon_ret.data, jobids=[job_id_int])  # ty: ignore[invalid-argument-type]
        if not ret.success or not ret.data:
            return html.Div(
                f"Job {job_id} not found.",
                className="text-secondary",
                style={"text-align": "center", "padding": "20px"},
            )

        job = ret.data[0]
        payload = job.payload
        sample = payload.sample
        techniques = sorted({task.technique_name for task in payload.method})

        overview_card = html.Div(
            className="card",
            style={"margin-bottom": "20px", "padding": "20px"},
            children=[
                html.Div(
                    children=[job_status_badge(job.status)],
                    style={"margin-bottom": "15px"},
                ),
                html.Div(
                    children=[
                        detail_row("Sample", sample.identifier),
                        detail_row("Technique(s)", ", ".join(techniques) or "-"),
                        detail_row("Submitted At", str(job.submitted_at).split(".")[0]),
                        detail_row(
                            "Completed At",
                            str(job.completed_at).split(".")[0]
                            if job.completed_at
                            else "-",
                        ),
                        detail_row("Result Path", job.respath or "-"),
                    ],
                    style={"display": "flex", "flex-wrap": "wrap"},
                ),
            ],
        )

        payload_card = html.Div(
            className="card",
            style={"padding": "20px"},
            children=[
                html.H3("Payload", style={"margin-top": 0}),
                html.Pre(
                    yaml.safe_dump(payload.model_dump(mode="json"), sort_keys=False),
                    style={
                        "font-family": "monospace",
                        "font-size": "13px",
                        "overflow-x": "auto",
                        "padding": "15px",
                        "background-color": "rgba(0,0,0,0.01)",
                        "border-radius": "6px",
                        "margin": 0,
                    },
                ),
            ],
        )

        return html.Div([overview_card, payload_card])
    except Exception as e:
        logger.warning("Exception during update_job_detail:", exc_info=e)
        return html.Div(
            f"Error loading job: {e!s}",
            className="text-secondary",
            style={"padding": "20px"},
        )
