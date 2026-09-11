"""Standalone tests for is_component_running, covering both
driverinterface_2_1 (plain dict) and driverinterface_3_0 (Status object)
shapes, without needing a real driver of either version installed.
"""

from types import SimpleNamespace

from marinara.utils import is_component_running


def test_running_dict_true():
    """driverinterface_2_1 style: plain dict with running=True."""
    assert is_component_running({"running": True}) is True


def test_running_dict_false():
    """driverinterface_2_1 style: plain dict with running=False."""
    assert is_component_running({"running": False}) is False


def test_running_dict_missing_key():
    """driverinterface_2_1 style: no running key at all defaults to False."""
    assert is_component_running({}) is False


def test_running_status_state_meas():
    """driverinterface_3_0 style: state=meas counts as running."""
    status = SimpleNamespace(connected=True, state="meas", can_submit=False)
    assert is_component_running(status) is True


def test_running_status_state_task():
    """driverinterface_3_0 style: state=task counts as running."""
    status = SimpleNamespace(connected=True, state="task", can_submit=False)
    assert is_component_running(status) is True


def test_running_status_state_idle():
    """driverinterface_3_0 style: state=idle does not count as running."""
    status = SimpleNamespace(connected=True, state="idle", can_submit=True)
    assert is_component_running(status) is False


def test_running_status_state_stop():
    """driverinterface_3_0 style: state=stop does not count as running."""
    status = SimpleNamespace(connected=True, state="stop", can_submit=False)
    assert is_component_running(status) is False


def test_running_status_state_none_connected():
    """driverinterface_3_0 style: state=None falls back to connected=True."""
    status = SimpleNamespace(connected=True, state=None, can_submit=False)
    assert is_component_running(status) is True


def test_running_status_state_none_disconnected():
    """driverinterface_3_0 style: state=None falls back to connected=False."""
    status = SimpleNamespace(connected=False, state=None, can_submit=False)
    assert is_component_running(status) is False
