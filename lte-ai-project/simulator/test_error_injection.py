import pytest

from simulator.error_injector import ErrorInjector
from simulator.error_definitions import ErrorType

BASE_KPI = {
    "throughput": 100.0,
    "delay": 10.0,
    "packet_loss": 1.0,
    "rsrp": -70.0,
    "sinr": 20.0,
    "cell_load": 0.5,
    "handover_count": 2.0
}

ERROR_TYPES = [
    "congestion",
    "underutilization",
    "interference",
    "equipment_degradation",
    "jamming",
    "ddos",
    "weather",
    "handover_failure"
]


@pytest.mark.parametrize("error_type", ERROR_TYPES)
def test_error_effect_has_impact(error_type):
    injector = ErrorInjector()
    injector.clear_history()

    ev = injector.inject_error(error_type, cell_id=0, severity=0.7, start_time=0.0, duration=10.0)
    assert ev is not None

    out = injector.apply_error_effects(BASE_KPI.copy(), cell_id=0, current_time=0.0)
    assert out != BASE_KPI
    status = injector.get_status(current_time=0.0)
    assert status["active_errors"] == 1
    assert status["active_error_details"][0]["error_type"] == error_type


def test_error_injector_json_contains_error_type():
    injector = ErrorInjector()
    injector.clear_history()

    injector.inject_error("congestion", cell_id=1, severity=0.5, start_time=0.0, duration=5.0)
    status = injector.get_status(current_time=0.0)

    detail = status["active_error_details"][0]
    assert detail["error_type"] == "congestion"
    assert detail["cell_id"] == 1
    assert "severity" in detail
