import logging
from datetime import UTC, datetime
from pathlib import Path

import dash
import yaml
from dash import Input, Output, State, callback, ctx, dcc, html
from dash.exceptions import PreventUpdate
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
            className="card",
            children=[
                html.Button("Take Snapshot", id="job-snapshot-btn", className="btn"),
                html.Span(id="job-snapshot-result", style={"margin-left": "12px"}),
                dcc.Download(id="job-snapshot-download"),
            ],
        ),
        html.Div(
            id="job-detail-container",
            className="text-secondary",
            children="Loading job details...",
        ),
    ]


def detail_row(label: str, value) -> html.Div:
    return labeled_row(label, html.Span(str(value)), {"margin-bottom": "10px"})


def snapshot_path(job_id: int) -> Path:
    """
    Returns where ketchup.snapshot writes the snapshot of a job.

    ketchup.snapshot runs in this process and tomato resolves its relative
    "snapshot.<id>.nc" against the cwd, i.e. wherever marinara was launched from.
    """
    return Path(f"snapshot.{job_id}.nc").resolve()


def snapshot_link(job_id: int) -> html.Span | None:
    """Renders a download link (and age) for the job's snapshot, if it exists."""
    path = snapshot_path(job_id)
    if not path.is_file():
        return None
    # UTC, like the submitted/completed times tomato reports on this page.
    taken_at = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    return html.Span(
        [
            html.A(
                path.name,
                id="job-snapshot-link",
                className="entity-link",
                title=str(path),
            ),
            html.Span(
                f" (taken {taken_at:%Y-%m-%d %H:%M:%S} UTC)",
                className="text-secondary",
            ),
        ]
    )


# On page load, shows the link to an existing snapshot; on button click, first
# requests an up-to-date snapshot of the job's data from tomato. Either way, the
# snapshot file itself is only ever looked up by snapshot_path - tomato doesn't
# report where it wrote it.
@callback(
    Output("job-snapshot-result", "children"),
    Input("job-id-store", "data"),
    Input("job-snapshot-btn", "n_clicks"),
    State("tomato-port", "data"),
    running=[(Output("job-snapshot-btn", "disabled"), True, False)],
)
def update_job_snapshot(job_id, n_clicks, port):
    try:
        job_id_int = int(job_id)
    except (TypeError, ValueError):
        return html.Span(f"Invalid job id: {job_id!r}", className="text-secondary")

    error = None
    if ctx.triggered_id == "job-snapshot-btn":
        try:
            daemon_ret = tomato.status(stgrp="tomato", port=port, timeout=TOUT)
            if not daemon_ret.success:
                error = f"Tomato status error: {daemon_ret.msg}"
            else:
                ret = ketchup.snapshot(jobids=[job_id_int], daemon=daemon_ret.data)
                if not ret.success:
                    error = ret.msg
        except Exception as e:
            logger.warning("Exception during update_job_snapshot:", exc_info=e)
            error = f"Error creating snapshot: {e!s}"

    link = snapshot_link(job_id_int)
    if error is None:
        if link is None:
            return html.Span("No snapshot yet", className="text-secondary")
        return link
    error_el = html.Span(error, className="text-secondary")
    if link is None:
        return error_el
    # Keep any earlier snapshot reachable (and its age visible) next to the error.
    return html.Span([error_el, " · ", link])


@callback(
    Output("job-snapshot-download", "data"),
    Input("job-snapshot-link", "n_clicks"),
    State("job-id-store", "data"),
    prevent_initial_call=True,
)
def download_job_snapshot(n_clicks, job_id):
    if not n_clicks:
        raise PreventUpdate
    try:
        path = snapshot_path(int(job_id))
    except (TypeError, ValueError):
        raise PreventUpdate from None
    if not path.is_file():
        raise PreventUpdate
    return dcc.send_file(str(path))


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
