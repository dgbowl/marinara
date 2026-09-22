import base64
import getpass
import logging
import os
import tempfile

import dash
import yaml
from dash import ALL, MATCH, Input, Output, State, callback, dcc, html
from dgbowl_schemas.tomato.payload_2_2 import Payload
from pydantic import ValidationError
from tomato import ketchup, tomato

from marinara.icons import get_icon
from marinara.utils import (
    TOUT,
    breadcrumb_parts,
    is_relative_path,
    list_subfolders,
    parent_folder,
    start_folder,
    triggered_pattern_index,
)

logger = logging.getLogger(__name__)
# order=0: dash.page_registry is checked in registry order, and without it
# job.py's "/jobs/<id>" template (module "job" sorts before "new_job") would
# match "/jobs/new" first, treating "new" as an id.
dash.register_page(__name__, path="/jobs/new", order=0, title="New Job")


layout = html.Div(
    className="dashboard-container",
    children=[
        html.Div(
            className="theme-header",
            children=[
                html.Div(
                    children=[
                        dcc.Link(
                            "← Back to Jobs",
                            href="/jobs",
                            className="btn",
                            style={"margin-right": "20px"},
                        ),
                        html.H2(
                            "New Job",
                            className="inline",
                            style={"margin": 0, "font-size": "22px"},
                        ),
                    ],
                    style={"display": "flex", "align-items": "center"},
                ),
            ],
        ),
        dcc.Tabs(
            id="new-job-tabs",
            value="new-payload",
            colors={
                "border": "var(--border-color)",
                "primary": "var(--accent-color)",
                "background": "var(--card-bg)",
            },
            style={"margin-bottom": "20px"},
            children=[
                dcc.Tab(
                    label="New Payload",
                    value="new-payload",
                    children=[
                        html.Div(
                            className="card",
                            children=[
                                html.H3("Pipeline & Sample", style={"margin-top": 0}),
                                html.Div(
                                    className="attr-row",
                                    children=[
                                        html.Div("Pipeline:", className="attr-label"),
                                        dcc.Dropdown(
                                            id="new-job-pipeline-dropdown",
                                            className="attr-control",
                                            clearable=False,
                                        ),
                                    ],
                                ),
                                html.Div(
                                    className="attr-row",
                                    children=[
                                        html.Div(
                                            "Sample Identifier:",
                                            className="attr-label",
                                        ),
                                        dcc.Input(
                                            id="new-job-sample-identifier",
                                            type="text",
                                            className="attr-control",
                                        ),
                                    ],
                                ),
                                html.Div(
                                    className="attr-row",
                                    children=[
                                        html.Div("", className="attr-label"),
                                        dcc.Checklist(
                                            id="new-job-sample-is-parent",
                                            options=[
                                                {
                                                    "label": " Sample is parent",
                                                    "value": "parent",
                                                }
                                            ],
                                            value=["parent"],
                                        ),
                                    ],
                                ),
                            ],
                        ),
                        html.Div(
                            className="card",
                            children=[
                                html.Div(
                                    children=[
                                        html.H3("Method", style={"margin": 0}),
                                        html.Button(
                                            "+ Add Task",
                                            id="new-job-add-task-btn",
                                            className="btn-success",
                                            style={"margin-left": "auto"},
                                        ),
                                    ],
                                    style={
                                        "display": "flex",
                                        "align-items": "center",
                                        "margin-bottom": "20px",
                                        "border-bottom": "1px solid var(--border-color)",
                                        "padding-bottom": "10px",
                                    },
                                ),
                                html.Div(id="new-job-tasks-container"),
                            ],
                        ),
                    ],
                ),
                dcc.Tab(
                    label="Select Payload",
                    value="select-payload",
                    children=[
                        html.Div(
                            className="card",
                            children=[
                                html.H3("Upload Payload", style={"margin-top": 0}),
                                dcc.Upload(
                                    id="new-job-payload-upload",
                                    children=html.Div(
                                        ["Drag and drop or ", html.A("select a file")]
                                    ),
                                    accept=".yml,.yaml,.json",
                                    style={
                                        "border": "1px dashed var(--border-color)",
                                        "border-radius": "var(--radius)",
                                        "padding": "30px",
                                        "text-align": "center",
                                        "cursor": "pointer",
                                    },
                                ),
                                html.Div(
                                    id="new-job-upload-status",
                                    style={"margin-top": "10px"},
                                ),
                            ],
                        ),
                        html.Div(
                            className="card",
                            children=[
                                html.H3("Sample", style={"margin-top": 0}),
                                html.Div(
                                    className="attr-row",
                                    children=[
                                        html.Div(
                                            "Sample Identifier:",
                                            className="attr-label",
                                        ),
                                        dcc.Input(
                                            id="new-job-upload-sample-identifier",
                                            type="text",
                                            className="attr-control",
                                        ),
                                    ],
                                ),
                                html.Div(
                                    className="attr-row",
                                    children=[
                                        html.Div("", className="attr-label"),
                                        dcc.Checklist(
                                            id="new-job-upload-sample-is-parent",
                                            options=[
                                                {
                                                    "label": " Sample is parent",
                                                    "value": "parent",
                                                }
                                            ],
                                            value=["parent"],
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        ),
        html.Div(
            className="card",
            children=[
                html.H3("Job Settings", style={"margin-top": 0}),
                html.Div(
                    className="attr-row",
                    children=[
                        html.Div("Job Name:", className="attr-label"),
                        dcc.Input(
                            id="new-job-name",
                            type="text",
                            className="attr-control",
                            placeholder="optional",
                        ),
                    ],
                ),
                html.Div(
                    className="attr-row",
                    children=[
                        html.Div("Output Path:", className="attr-label"),
                        dcc.Input(
                            id="new-job-output-path",
                            type="text",
                            className="attr-control attr-control-wide",
                            debounce=True,
                            placeholder="defaults to tomato's working directory",
                        ),
                        html.Button(
                            "Browse",
                            id="new-job-browse-btn",
                            className="btn attr-btn",
                        ),
                    ],
                ),
                html.Div(id="new-job-output-path-warning"),
            ],
        ),
        html.Div(
            className="card",
            children=[
                html.H3("YAML Preview", style={"margin-top": 0}),
                html.Pre(
                    id="new-job-yaml-preview",
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
                html.Button(
                    "Submit Job",
                    id="new-job-submit-btn",
                    style={"padding": "10px 20px", "margin-top": "15px"},
                ),
                html.Div(id="new-job-submit-result", className="submit-result"),
            ],
        ),
        html.Div(
            id="new-job-folder-modal",
            className="modal-overlay",
            hidden=True,
            children=[
                html.Div(
                    className="card modal-card",
                    children=[
                        html.H3("Select Output Folder", style={"margin-top": 0}),
                        html.Div(
                            id="new-job-folder-current", className="folder-current"
                        ),
                        html.Div(id="new-job-folder-list", className="folder-list"),
                        html.Div(
                            className="modal-actions",
                            children=[
                                html.Button(
                                    "↑ Up",
                                    id="new-job-folder-up-btn",
                                    className="btn",
                                ),
                                html.Button(
                                    "Cancel",
                                    id="new-job-folder-cancel-btn",
                                    className="btn btn-danger",
                                ),
                                html.Button(
                                    "Select this folder",
                                    id="new-job-folder-select-btn",
                                    className="btn btn-success",
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        ),
        dcc.Store(id="new-job-folder-cwd", data=None),
        dcc.Store(id="new-job-tasks-list-store", data=[]),
        dcc.Store(id="new-job-roles-store", data={}),
        dcc.Store(id="new-job-components-store", data={}),
        dcc.Store(id="new-job-pipelines-store", data={}),
        dcc.Store(id="new-job-uploaded-payload-store", data=None),
    ],
)


# Populates the pipeline dropdown, component capabilities, and each pipeline's
# role -> component_name mapping on page load / port change
@callback(
    Output("new-job-pipeline-dropdown", "options"),
    Output("new-job-components-store", "data"),
    Output("new-job-pipelines-store", "data"),
    Input("tomato-port", "data"),
)
def populate_new_job_options(port):
    try:
        cfg_ret = tomato.status(stgrp="tomato", port=port, timeout=TOUT)
        cmps_ret = tomato.status(stgrp="components", port=port, timeout=TOUT)
        pipelines = (
            cfg_ret.data.devicefile.pipelines
            if cfg_ret.success and cfg_ret.data is not None
            else {}
        )
        components = (
            cmps_ret.data if cmps_ret.success and cmps_ret.data is not None else {}
        )
        # capabilities is a set, which dcc.Store can't JSON-serialize as-is
        components = {
            cname: {**cmp, "capabilities": sorted(cmp.get("capabilities") or [])}
            for cname, cmp in components.items()
        }
        pipelines_roles = {
            name: dict(pip.components) for name, pip in pipelines.items()
        }
        return sorted(pipelines), components, pipelines_roles
    except Exception as e:
        logger.warning("Exception during populate_new_job_options:", exc_info=e)
        return [], {}, {}


# Resolves the selected pipeline's role -> component_name mapping from the store
# populated above, rather than re-querying the daemon
@callback(
    Output("new-job-roles-store", "data"),
    Input("new-job-pipeline-dropdown", "value"),
    State("new-job-pipelines-store", "data"),
    prevent_initial_call=True,
)
def select_new_job_pipeline(pipeline_name, pipelines_roles):
    if not pipeline_name:
        return {}
    return (pipelines_roles or {}).get(pipeline_name, {})


# Refreshes every existing task card's role options when the pipeline changes,
# clearing any role that isn't valid for the newly selected pipeline. This in
# turn feeds update_new_job_technique_options (below), which reacts to each
# role dropdown's value and refreshes that task's technique options too.
@callback(
    Output({"type": "new-job-role-dropdown", "index": ALL}, "options"),
    Output({"type": "new-job-role-dropdown", "index": ALL}, "value"),
    Input("new-job-roles-store", "data"),
    State({"type": "new-job-role-dropdown", "index": ALL}, "value"),
)
def refresh_new_job_role_options(roles, current_values):
    roles = roles or {}
    options = sorted(roles)
    values = [v if v in roles else None for v in current_values]
    return [options] * len(current_values), values


# Parses an uploaded payload file and seeds the Select Payload tab's sample fields from it
@callback(
    Output("new-job-uploaded-payload-store", "data"),
    Output("new-job-upload-status", "children"),
    Output("new-job-upload-sample-identifier", "value"),
    Output("new-job-upload-sample-is-parent", "value"),
    Input("new-job-payload-upload", "contents"),
    State("new-job-payload-upload", "filename"),
    prevent_initial_call=True,
)
def parse_uploaded_payload(contents, filename):
    try:
        _, content_string = contents.split(",", 1)
        decoded = base64.b64decode(content_string).decode("utf-8")
        payload_dict = yaml.safe_load(decoded)
        if not isinstance(payload_dict, dict):
            raise TypeError("file does not contain a payload mapping")
    except Exception as e:
        logger.warning("Exception during parse_uploaded_payload:", exc_info=e)
        return (
            None,
            html.Div(f"Could not parse {filename!r}: {e}", className="attr-error"),
            dash.no_update,
            dash.no_update,
        )

    sample = payload_dict.get("sample") or {}
    is_parent = ["parent"] if sample.get("sample_is_parent", True) else []
    return (
        payload_dict,
        html.Div(f"Loaded {filename!r}.", className="text-secondary"),
        sample.get("identifier"),
        is_parent,
    )


# Manages adding and removing task cards
@callback(
    Output("new-job-tasks-list-store", "data"),
    Input("new-job-add-task-btn", "n_clicks"),
    Input({"type": "new-job-task-remove-btn", "index": ALL}, "n_clicks"),
    State("new-job-tasks-list-store", "data"),
    prevent_initial_call=True,
)
def manage_new_job_tasks(add_clicks, remove_clicks, active_ids):
    ctx = dash.callback_context
    if not ctx.triggered:
        return active_ids

    trigger_id = ctx.triggered[0]["prop_id"]

    if "new-job-add-task-btn" in trigger_id:
        next_id = max(active_ids, default=0) + 1
        return active_ids + [next_id]
    else:
        try:
            remove_idx = triggered_pattern_index(ctx)
            return [i for i in active_ids if i != remove_idx]
        except Exception as e:
            logger.warning("Exception during manage_new_job_tasks:", exc_info=e)
            return active_ids


def task_card(i, meta, roles, components):
    role_val = meta.get("component_role")
    technique_val = meta.get("technique_name")
    cname = roles.get(role_val) if role_val else None
    capabilities = (
        (components.get(cname) or {}).get("capabilities", []) if cname else []
    )

    return html.Div(
        id={"type": "new-job-task-card", "index": i},
        className="card",
        children=[
            dcc.Store(id={"type": "new-job-task-meta", "index": i}, data=meta),
            html.Div(
                children=[
                    html.H4(f"Task {i}", style={"margin": 0}),
                    html.Button(
                        "Remove",
                        id={"type": "new-job-task-remove-btn", "index": i},
                        className="btn-danger btn-sm",
                        style={"margin-left": "auto"},
                    ),
                ],
                style={
                    "display": "flex",
                    "align-items": "center",
                    "border-bottom": "1px solid var(--border-color)",
                    "padding-bottom": "10px",
                    "margin-bottom": "15px",
                },
            ),
            html.Div(
                className="attr-row",
                children=[
                    html.Div("Component Role:", className="attr-label"),
                    dcc.Dropdown(
                        id={"type": "new-job-role-dropdown", "index": i},
                        className="attr-control",
                        options=sorted(roles),
                        value=role_val,
                        clearable=False,
                    ),
                ],
            ),
            html.Div(
                className="attr-row",
                children=[
                    html.Div("Technique:", className="attr-label"),
                    dcc.Dropdown(
                        id={"type": "new-job-technique-dropdown", "index": i},
                        className="attr-control",
                        options=sorted(capabilities),
                        value=technique_val,
                        clearable=False,
                    ),
                ],
            ),
            html.Div(
                className="attr-row",
                children=[
                    html.Div("Max Duration (s):", className="attr-label"),
                    dcc.Input(
                        id={"type": "new-job-max-duration", "index": i},
                        className="attr-control",
                        type="number",
                        value=meta.get("max_duration"),
                    ),
                ],
            ),
            html.Div(
                className="attr-row",
                children=[
                    html.Div("Sampling Interval (s):", className="attr-label"),
                    dcc.Input(
                        id={"type": "new-job-sampling-interval", "index": i},
                        className="attr-control",
                        type="number",
                        value=meta.get("sampling_interval"),
                    ),
                ],
            ),
            html.Div(
                "Task Params:", className="attr-label", style={"margin-bottom": "6px"}
            ),
            dcc.Textarea(
                id={"type": "new-job-task-params", "index": i},
                value=meta.get("task_params_text", ""),
                placeholder="key: value\nother_key: other_value",
                style={
                    "width": "100%",
                    "min-height": "80px",
                    "font-family": "monospace",
                    "font-size": "13px",
                    "box-sizing": "border-box",
                },
            ),
        ],
        style={"margin-bottom": "20px"},
    )


# Renders one card per task id, seeding fields from each task's own meta store
@callback(
    Output("new-job-tasks-container", "children"),
    Input("new-job-tasks-list-store", "data"),
    State({"type": "new-job-task-meta", "index": ALL}, "id"),
    State({"type": "new-job-task-meta", "index": ALL}, "data"),
    State("new-job-roles-store", "data"),
    State("new-job-components-store", "data"),
)
def render_new_job_tasks(active_ids, meta_ids, meta_values, roles, components):
    if not active_ids:
        return html.Div(
            "No tasks added. Click '+ Add Task' above to create one.",
            style={
                "text-align": "center",
                "padding": "30px",
                "color": "gray",
                "font-style": "italic",
                "border": "1px dashed var(--border-color)",
                "border-radius": "var(--radius)",
            },
        )

    roles = roles or {}
    components = components or {}
    meta_by_id = {m["index"]: v for m, v in zip(meta_ids, meta_values)}

    return [
        task_card(i, meta_by_id.get(i) or {}, roles, components)
        for i in sorted(active_ids)
    ]


# Commits a task card's own fields into its meta store; ignores the list-store's own stale mount echo
@callback(
    Output({"type": "new-job-task-meta", "index": MATCH}, "data"),
    Input({"type": "new-job-role-dropdown", "index": MATCH}, "value"),
    Input({"type": "new-job-technique-dropdown", "index": MATCH}, "value"),
    Input({"type": "new-job-max-duration", "index": MATCH}, "value"),
    Input({"type": "new-job-sampling-interval", "index": MATCH}, "value"),
    Input({"type": "new-job-task-params", "index": MATCH}, "value"),
    Input("new-job-tasks-list-store", "data"),
    State({"type": "new-job-task-meta", "index": MATCH}, "data"),
    prevent_initial_call=True,
)
def update_new_job_task_meta(
    role,
    technique,
    max_duration,
    sampling_interval,
    task_params_text,
    active_ids,
    current_data,
):
    ctx = dash.callback_context
    if not ctx.triggered or any(
        "new-job-tasks-list-store" in t["prop_id"] for t in ctx.triggered
    ):
        return current_data
    return {
        "component_role": role,
        "technique_name": technique,
        "max_duration": max_duration,
        "sampling_interval": sampling_interval,
        "task_params_text": task_params_text or "",
    }


# Refreshes a task's technique options when its component_role changes
@callback(
    Output({"type": "new-job-technique-dropdown", "index": MATCH}, "options"),
    Output({"type": "new-job-technique-dropdown", "index": MATCH}, "value"),
    Input({"type": "new-job-role-dropdown", "index": MATCH}, "value"),
    State("new-job-roles-store", "data"),
    State("new-job-components-store", "data"),
    State({"type": "new-job-technique-dropdown", "index": MATCH}, "value"),
    prevent_initial_call=True,
)
def update_new_job_technique_options(role, roles, components, current_technique):
    cname = (roles or {}).get(role) if role else None
    capabilities = (
        (components or {}).get(cname, {}).get("capabilities", []) if cname else []
    )
    value = current_technique if current_technique in capabilities else None
    return sorted(capabilities), value


def build_method(tasks_meta):
    """Parses each task's meta dict into a method-task dict; raises ValueError with a
    task-scoped message if task_params isn't valid YAML/a mapping."""
    method = []
    for i, meta in enumerate(tasks_meta):
        meta = meta or {}
        task_params_text = (meta.get("task_params_text") or "").strip()
        if task_params_text:
            try:
                task_params = yaml.safe_load(task_params_text)
            except yaml.YAMLError as e:
                raise ValueError(f"Task {i + 1}: invalid task_params — {e}") from e
            if not isinstance(task_params, dict):
                raise ValueError(f"Task {i + 1}: task_params must be key: value pairs")
        else:
            task_params = {}
        method.append(
            {
                "component_role": meta.get("component_role"),
                "technique_name": meta.get("technique_name"),
                "max_duration": meta.get("max_duration"),
                "sampling_interval": meta.get("sampling_interval"),
                "task_params": task_params,
            }
        )
    return method


def validate_form(sample_id, method):
    """Raises ValueError with a user-facing message for the first missing field."""
    if not (sample_id or "").strip():
        raise ValueError("Sample identifier is required.")
    if not method:
        raise ValueError("Add at least one task.")
    for i, task in enumerate(method):
        if not task["component_role"] or not task["technique_name"]:
            raise ValueError(f"Task {i + 1}: select a component role and a technique.")
        if task["max_duration"] is None or task["sampling_interval"] is None:
            raise ValueError(f"Task {i + 1}: set max duration and sampling interval.")


def assemble_payload_dict(sample_id, is_parent, method, output_path=None, user=None):
    """Builds the payload_2_2-shaped dict shared by the YAML preview and submit callbacks."""
    payload_dict = {
        "version": "2.2",
        "sample": {
            "identifier": sample_id,
            "sample_is_parent": bool(is_parent and "parent" in is_parent),
        },
        "method": method,
    }
    output_path = (output_path or "").strip()
    if output_path:
        payload_dict["settings"] = {"output": {"path": output_path}}
    if user:
        payload_dict["user"] = {"identifier": user}
    return payload_dict


def apply_uploaded_overrides(payload_dict, sample_id, is_parent, output_path=None, user=None):
    """Overlays the Select Payload tab's sample/output path/user onto an uploaded payload dict."""
    payload_dict = dict(payload_dict or {})
    payload_dict["sample"] = {
        "identifier": sample_id,
        "sample_is_parent": bool(is_parent and "parent" in is_parent),
    }
    output_path = (output_path or "").strip()
    if output_path:
        payload_dict["settings"] = {"output": {"path": output_path}}
    if user:
        payload_dict["user"] = {"identifier": user}
    return payload_dict


RELATIVE_PATH_MSG = "Output path must be absolute (tomato resolves relative paths against its own working directory)."


# Flags a relative output path, which submit_new_job rejects
@callback(
    Output("new-job-output-path-warning", "children"),
    Input("new-job-output-path", "value"),
)
def warn_relative_output_path(output_path):
    if not is_relative_path(output_path):
        return None
    return html.Div(RELATIVE_PATH_MSG, className="attr-error")


# Sets the picker's folder (None = closed); selecting also writes the output path
@callback(
    Output("new-job-folder-cwd", "data"),
    Output("new-job-output-path", "value"),
    Input("new-job-browse-btn", "n_clicks"),
    Input("new-job-folder-up-btn", "n_clicks"),
    Input("new-job-folder-select-btn", "n_clicks"),
    Input("new-job-folder-cancel-btn", "n_clicks"),
    Input({"type": "new-job-folder-entry", "index": ALL}, "n_clicks"),
    State("new-job-output-path", "value"),
    State("new-job-folder-cwd", "data"),
    prevent_initial_call=True,
)
def navigate_folder_picker(browse, up, select, cancel, entries, output_path, cwd):
    ctx = dash.callback_context
    value = ctx.triggered[0]["value"] if ctx.triggered else None
    # ignore triggers that carry no click (None or the ALL list)
    if not value or isinstance(value, list):
        return dash.no_update, dash.no_update

    trigger = ctx.triggered_id
    if trigger == "new-job-browse-btn":
        return start_folder(output_path), dash.no_update
    if trigger == "new-job-folder-cancel-btn":
        return None, dash.no_update
    if trigger == "new-job-folder-select-btn" and cwd:
        return None, cwd
    if trigger == "new-job-folder-up-btn":
        return parent_folder(cwd), dash.no_update
    if isinstance(trigger, dict) and os.path.isdir(trigger["index"]):
        return trigger["index"], dash.no_update
    return dash.no_update, dash.no_update


# Shows the picker while a folder is set and lists its subfolders
@callback(
    Output("new-job-folder-modal", "hidden"),
    Output("new-job-folder-current", "children"),
    Output("new-job-folder-list", "children"),
    Output("new-job-folder-up-btn", "disabled"),
    Output("new-job-folder-select-btn", "disabled"),
    Input("new-job-folder-cwd", "data"),
)
def render_folder_list(cwd):
    if cwd is None:
        return True, "", [], True, True

    folders, err = list_subfolders(cwd)
    if err:
        children = html.Div(err, className="folder-message folder-message-error")
    elif not folders:
        children = html.Div("No subfolders.", className="folder-message text-secondary")
    else:
        children = [
            html.Button(
                [get_icon("folder", size=15), html.Span(label)],
                id={"type": "new-job-folder-entry", "index": full},
                className="folder-entry",
            )
            for label, full in folders
        ]

    if cwd:
        # Each crumb reuses the same folder-entry pattern id as the list buttons
        # above, so navigate_folder_picker's existing click handling covers it too.
        current = []
        for i, (label, full) in enumerate(breadcrumb_parts(cwd)):
            if i:
                current.append(html.Span("›", className="breadcrumb-sep"))
            current.append(
                html.Button(
                    label,
                    id={"type": "new-job-folder-entry", "index": full},
                    className="breadcrumb-entry",
                )
            )
    else:
        current = html.Span("This PC")

    at_top = not cwd or parent_folder(cwd) == cwd
    return False, current, children, at_top, not cwd or bool(err)


# Renders a best-effort live preview of the effective payload as YAML, for whichever tab is active
@callback(
    Output("new-job-yaml-preview", "children"),
    Input("new-job-tabs", "value"),
    Input("new-job-sample-identifier", "value"),
    Input("new-job-sample-is-parent", "value"),
    Input({"type": "new-job-task-meta", "index": ALL}, "data"),
    Input("new-job-uploaded-payload-store", "data"),
    Input("new-job-upload-sample-identifier", "value"),
    Input("new-job-upload-sample-is-parent", "value"),
    Input("new-job-output-path", "value"),
)
def render_new_job_yaml_preview(
    tab,
    sample_id,
    is_parent,
    tasks_meta,
    uploaded,
    up_sample_id,
    up_is_parent,
    output_path,
):
    if tab == "select-payload":
        if not uploaded:
            return "# Upload a payload file to preview it here."
        payload_dict = apply_uploaded_overrides(
            uploaded, up_sample_id, up_is_parent, output_path
        )
    else:
        try:
            method = build_method(tasks_meta)
        except ValueError as e:
            method = [{"<error>": str(e)}]
        payload_dict = assemble_payload_dict(sample_id, is_parent, method, output_path)
    return yaml.safe_dump(payload_dict, sort_keys=False)


# Builds and submits the job via ketchup, after validating against payload_2_2.Payload
@callback(
    Output("new-job-submit-result", "children"),
    Input("new-job-submit-btn", "n_clicks"),
    State("new-job-tabs", "value"),
    State("new-job-sample-identifier", "value"),
    State("new-job-sample-is-parent", "value"),
    State({"type": "new-job-task-meta", "index": ALL}, "data"),
    State("new-job-uploaded-payload-store", "data"),
    State("new-job-upload-sample-identifier", "value"),
    State("new-job-upload-sample-is-parent", "value"),
    State("new-job-name", "value"),
    State("new-job-output-path", "value"),
    State("tomato-port", "data"),
    prevent_initial_call=True,
)
def submit_new_job(
    n_clicks,
    tab,
    sample_id,
    is_parent,
    tasks_meta,
    uploaded,
    up_sample_id,
    up_is_parent,
    jobname,
    output_path,
    port,
):
    if tab == "select-payload":
        if not uploaded:
            return html.Div(
                "Upload a payload file first.",
                className="text-secondary",
                style={"text-align": "center", "padding": "20px"},
            )
        if not (up_sample_id or "").strip():
            return html.Div(
                "Sample identifier is required.",
                className="text-secondary",
                style={"text-align": "center", "padding": "20px"},
            )
        payload_dict = apply_uploaded_overrides(
            uploaded, up_sample_id, up_is_parent, output_path, user=getpass.getuser()
        )
    else:
        try:
            method = build_method(tasks_meta)
            validate_form(sample_id, method)
        except ValueError as e:
            return html.Div(
                str(e),
                className="text-secondary",
                style={"text-align": "center", "padding": "20px"},
            )
        payload_dict = assemble_payload_dict(
            sample_id, is_parent, method, output_path, user=getpass.getuser()
        )

    if is_relative_path(output_path):
        return html.Div(
            RELATIVE_PATH_MSG,
            className="text-secondary",
            style={"text-align": "center", "padding": "20px"},
        )

    try:
        payload = Payload(**payload_dict)
    except ValidationError as e:
        problems = "; ".join(
            f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors()
        )
        return html.Div(
            f"Invalid payload: {problems}",
            className="text-secondary",
            style={"text-align": "center", "padding": "20px"},
        )

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as tmp:
            yaml.safe_dump(payload.model_dump(mode="json"), tmp)
            tmp_path = tmp.name

        daemon_ret = tomato.status(stgrp="tomato", port=port, timeout=TOUT)
        if not daemon_ret.success:
            return html.Div(
                f"Tomato status error: {daemon_ret.msg}",
                className="text-secondary",
                style={"text-align": "center", "padding": "20px"},
            )

        ret = ketchup.submit(
            payload=tmp_path, jobname=jobname or None, daemon=daemon_ret.data
        )
        if not ret.success:
            return html.Div(
                f"Submit failed: {ret.msg}",
                className="text-secondary",
                style={"text-align": "center", "padding": "20px"},
            )
        return html.Div(
            f"Job submitted successfully (jobid {ret.data.id}).",
            className="badge badge-success",
            style={"padding": "10px"},
        )
    except Exception as e:
        logger.warning("Exception during submit_new_job:", exc_info=e)
        return html.Div(
            f"Error submitting job: {e!s}",
            className="text-secondary",
            style={"padding": "20px"},
        )
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
