from app.diagnosis import (
    clear_timing,
    collect_timing,
    diagnosis_record,
    get_timing,
    route_timer,
    step_timer,
)


def test_route_timer_records_elapsed():
    with route_timer("test_route"):
        pass
    records = get_timing("test_route")
    assert len(records) == 1
    assert records[0]["name"] == "test_route"
    assert isinstance(records[0]["elapsed_ms"], (int, float))
    assert records[0]["elapsed_ms"] >= 0
    # Cleanup
    clear_timing("test_route")


def test_step_timer_records_nested_step():
    with route_timer("test_with_steps"):
        with step_timer("test_with_steps", "step_a"):
            pass
        with step_timer("test_with_steps", "step_b"):
            pass
    records = get_timing("test_with_steps")
    assert len(records) == 1
    assert len(records[0]["steps"]) == 2
    assert records[0]["steps"][0]["step"] == "step_a"
    assert records[0]["steps"][1]["step"] == "step_b"
    clear_timing("test_with_steps")


def test_collect_timing_adds_record():
    collect_timing("collect_test", 42.5)
    records = get_timing("collect_test")
    assert len(records) == 1
    assert records[0]["elapsed_ms"] == 42.5
    clear_timing("collect_test")


def test_collect_timing_with_step_appends_to_last():
    collect_timing("step_test", 10.0)
    collect_timing("step_test", 20.0, step="inner_step")
    records = get_timing("step_test")
    assert len(records) == 1
    assert len(records[0]["steps"]) == 1
    assert records[0]["steps"][0]["step"] == "inner_step"
    clear_timing("step_test")


def test_get_timing_without_name_returns_all():
    with route_timer("route_one"):
        pass
    with route_timer("route_two"):
        pass
    all_records = get_timing()
    names = {r["name"] for r in all_records}
    assert "route_one" in names
    assert "route_two" in names
    clear_timing()


def test_clear_timing_removes_specific():
    with route_timer("keep_me"):
        pass
    with route_timer("remove_me"):
        pass
    clear_timing("remove_me")
    records = get_timing("remove_me")
    assert len(records) == 0
    records = get_timing("keep_me")
    assert len(records) == 1
    clear_timing()


def test_diagnosis_record_returns_structured_dict():
    record = diagnosis_record(
        issue="Dashboard slow",
        expected="Loads in <1s",
        observed="Takes 5s",
        environment="Railway",
        root_cause="Breeze REST call blocks",
        chosen_fix="Add Redis-first read path",
    )
    assert record["issue"] == "Dashboard slow"
    assert record["expected"] == "Loads in <1s"
    assert record["observed"] == "Takes 5s"
    assert record["environment"] == "Railway"
    assert record["root_cause"] == "Breeze REST call blocks"
    assert record["chosen_fix"] == "Add Redis-first read path"


def test_route_timer_caps_at_100_records():
    for i in range(110):
        with route_timer("capped_route"):
            pass
    records = get_timing("capped_route")
    assert len(records) == 100
    clear_timing("capped_route")
