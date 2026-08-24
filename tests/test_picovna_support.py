import dataclasses
import os
import sys
import unittest
from typing import Optional
import numpy as np
from pydantic import BaseModel

sys.path.insert(0, os.path.abspath("src"))

# Mock dash.register_page so page modules can be imported without Dash app context
import dash
dash.register_page = lambda *args, **kwargs: None

from marinara.utils import (
    clean_value,
    format_attr_value,
    clean_data,
    parse_input_value,
    parse_running_status,
    fetch_component_state,
)
from marinara.graphing import extract_telemetry_points, DEFAULT_MAX_ARRAY_TRACES
from marinara.pages.component import component_data_graph


class MockSweep(BaseModel):
    start: float
    stop: float
    points: Optional[int] = None
    step: Optional[float] = None


class MockNestedModel(BaseModel):
    name: str
    sweep: MockSweep
    m: Optional[str] = "magnitude_field"


@dataclasses.dataclass
class MockDataclass:
    frequency: float
    channels: list[int]


class MockCustomClass:
    def __init__(self, x: int, y: str):
        self.x = x
        self.y = y


class MockQuantity:
    def __init__(self, magnitude, units="Hz"):
        self.m = magnitude
        self.units = units


class TestPicoVNASupport(unittest.TestCase):
    def test_clean_value_pydantic_v2(self):
        sweep = MockSweep(start=5.5e9, stop=7.5e9, points=10001)
        cleaned = clean_value(sweep)
        self.assertIsInstance(cleaned, dict)
        self.assertEqual(cleaned["start"], 5500000000.0)
        self.assertEqual(cleaned["stop"], 7500000000.0)
        self.assertEqual(cleaned["points"], 10001)
        self.assertEqual(cleaned["step"], "")

    def test_clean_value_nested_pydantic(self):
        nested = MockNestedModel(
            name="test_vna",
            sweep=MockSweep(start=1.0e9, stop=2.0e9, points=501),
            m="should_not_be_treated_as_quantity_magnitude",
        )
        cleaned = clean_value(nested)
        self.assertIsInstance(cleaned, dict)
        self.assertEqual(cleaned["name"], "test_vna")
        self.assertIsInstance(cleaned["sweep"], dict)
        self.assertEqual(cleaned["sweep"]["start"], 1000000000.0)
        self.assertEqual(cleaned["m"], "should_not_be_treated_as_quantity_magnitude")

    def test_clean_value_dataclass(self):
        dc = MockDataclass(frequency=100.5, channels=[1, 2, 3])
        cleaned = clean_value(dc)
        self.assertIsInstance(cleaned, dict)
        self.assertEqual(cleaned["frequency"], 100.5)
        self.assertEqual(cleaned["channels"], [1, 2, 3])

    def test_clean_value_custom_class(self):
        obj = MockCustomClass(x=42, y="test")
        cleaned = clean_value(obj)
        self.assertIsInstance(cleaned, dict)
        self.assertEqual(cleaned["x"], 42)
        self.assertEqual(cleaned["y"], "test")

    def test_clean_value_quantity(self):
        q = MockQuantity(magnitude=25.4, units="degC")
        cleaned = clean_value(q)
        self.assertEqual(cleaned, 25.4)

    def test_clean_value_numpy(self):
        arr1 = np.array([10.5])
        self.assertEqual(clean_value(arr1), 10.5)

        arr2 = np.array([1, 2, 3])
        self.assertEqual(clean_value(arr2), [1, 2, 3])

        arr_empty = np.array([])
        self.assertEqual(clean_value(arr_empty), "")

    def test_format_attr_value(self):
        self.assertEqual(format_attr_value(None), "")
        self.assertEqual(format_attr_value(42), "42")
        self.assertEqual(format_attr_value("hello"), "hello")

        sweep = MockSweep(start=5.5e9, stop=7.5e9, points=10001)
        fmt = format_attr_value([sweep])
        self.assertIsInstance(fmt, str)
        self.assertIn("5500000000", fmt)
        self.assertIn('"points": 10001', fmt)

    def test_parse_input_value(self):
        self.assertEqual(parse_input_value(""), "")
        self.assertEqual(parse_input_value(140), 140)
        self.assertEqual(parse_input_value("140"), "140")
        self.assertEqual(parse_input_value("true"), True)
        self.assertEqual(parse_input_value("FALSE"), False)
        
        # JSON list of dicts
        raw_json = '[{"start": 5.5e9, "stop": 7.5e9, "points": 10001}]'
        parsed = parse_input_value(raw_json)
        self.assertIsInstance(parsed, list)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["start"], 5500000000.0)
        self.assertEqual(parsed[0]["points"], 10001)

        # Python literal syntax (single quotes)
        raw_py = "[{'start': 1000.0, 'stop': 2000.0, 'step': 10.0}]"
        parsed_py = parse_input_value(raw_py)
        self.assertIsInstance(parsed_py, list)
        self.assertEqual(parsed_py[0]["start"], 1000.0)

    def test_component_data_graph_spectral(self):
        mock_ds = {
            "coords": {
                "uts": {"data": [1787000000.0]},
                "freq": {"data": [5.5e9 + i * 200000 for i in range(10001)], "attrs": {"units": "Hz"}},
            },
            "data_vars": {
                "Re(S11)": {"data": [[0.61 + i * 0.00001 for i in range(10001)]]},
                "temperature": {"data": [40.7]},
            },
        }

        fig = component_data_graph(mock_ds, "dark", [])
        traces = fig.get("data", [])
        self.assertEqual(len(traces), 2)

        # Spectrum trace
        spec_trace = traces[0]
        self.assertEqual(spec_trace["name"], "Re(S11) (latest spectrum)")
        self.assertEqual(len(spec_trace["x"]), 10001)
        self.assertEqual(len(spec_trace["y"]), 10001)

        # Time trace
        time_trace = traces[1]
        self.assertEqual(time_trace["name"], "temperature")
        self.assertEqual(len(time_trace["x"]), 1)

        # Check axis title
        layout = fig.get("layout", {})
        self.assertIn("Frequency", layout.get("xaxis", {}).get("title", ""))

    def test_component_data_graph_generic_spectral_coord(self):
        mock_ds = {
            "coords": {
                "uts": {"data": [1787000000.0]},
                "wavelength": {"data": [400 + i * 2 for i in range(100)], "attrs": {"units": "nm"}},
            },
            "data_vars": {
                "intensity": {"data": [[10.0 + i * 0.1 for i in range(100)]]},
            },
        }

        fig = component_data_graph(mock_ds, "light", [])
        traces = fig.get("data", [])
        self.assertEqual(len(traces), 1)
        self.assertEqual(traces[0]["name"], "intensity (latest spectrum)")
        self.assertEqual(len(traces[0]["x"]), 100)
        self.assertIn("Wavelength", fig.get("layout", {}).get("xaxis", {}).get("title", ""))

    def test_component_data_graph_multidimensional_capped(self):
        # Multi-dimensional data without spectral coordinate should cap at DEFAULT_MAX_ARRAY_TRACES
        mock_ds = {
            "coords": {
                "uts": {"data": [1787000000.0, 1787000010.0]},
            },
            "data_vars": {
                "multi_channel": {"data": [[i for i in range(100)], [i + 1 for i in range(100)]]},
            },
        }

        fig = component_data_graph(mock_ds, "dark", [])
        traces = fig.get("data", [])
        self.assertEqual(len(traces), DEFAULT_MAX_ARRAY_TRACES)

    def test_extract_telemetry_points_capped(self):
        mock_ds = {
            "coords": {
                "uts": {"data": [1787000000.0]},
            },
            "data_vars": {
                "huge_array": {"data": [[i for i in range(5000)]]},
                "scalar_val": {"data": [123.45]},
            },
        }

        points = extract_telemetry_points(mock_ds, "comp1")
        self.assertEqual(len(points), DEFAULT_MAX_ARRAY_TRACES + 1)
        self.assertIn("comp1/scalar_val", points)
        self.assertIn("comp1/huge_array[0]", points)
        self.assertIn(f"comp1/huge_array[{DEFAULT_MAX_ARRAY_TRACES - 1}]", points)
        self.assertNotIn(f"comp1/huge_array[{DEFAULT_MAX_ARRAY_TRACES}]", points)


    def test_parse_running_status(self):
        # Bool false
        running_bool, tech_name, text, badge = parse_running_status(False)
        self.assertFalse(running_bool)
        self.assertIsNone(tech_name)
        self.assertEqual(text, "STOPPED")
        self.assertEqual(badge, "badge badge-secondary")

        # Bool true
        running_bool, tech_name, text, badge = parse_running_status(True)
        self.assertTrue(running_bool)
        self.assertIsNone(tech_name)
        self.assertEqual(text, "RUNNING")
        self.assertEqual(badge, "badge badge-success")

        # Dict with technique_name
        running_bool, tech_name, text, badge = parse_running_status(
            {"technique_name": "frequency_sweep"}
        )
        self.assertTrue(running_bool)
        self.assertEqual(tech_name, "frequency_sweep")
        self.assertEqual(text, "RUNNING (frequency_sweep)")
        self.assertEqual(badge, "badge badge-success")

        # Object with technique_name
        class MockStatusObj:
            technique_name = "vna_calibration"

        running_bool, tech_name, text, badge = parse_running_status(MockStatusObj())
        self.assertTrue(running_bool)
        self.assertEqual(tech_name, "vna_calibration")
        self.assertEqual(text, "RUNNING (vna_calibration)")
        self.assertEqual(badge, "badge badge-success")


if __name__ == "__main__":
    unittest.main()
