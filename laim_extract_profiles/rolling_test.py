"""Profile ноды последовательных непересекающихся test-окон."""

from __future__ import annotations

from datetime import timedelta

from .profile_v2 import (
    build_selection,
    fail,
    parse_date,
    parse_json_object,
    same_identity,
    validate_selection,
)


TEST_MIN_TRACES = 500


def _is_connected(value) -> bool:
    return value is not None and not (isinstance(value, str) and not value.strip())


def _exact_nonnegative_int(value, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        fail(f"{name} должен быть целым неотрицательным числом")
    return value


def _checked_gate_report(value, previous: dict) -> tuple[str, int]:
    report = parse_json_object(value, "previous_gate_report")
    if report.get("schema_version") != 2:
        fail("previous_gate_report.schema_version должен быть 2")
    for field in ("selection_id", "run_id"):
        if report.get(field) != previous[field]:
            fail(
                f"previous_gate_report.{field} не совпадает с "
                f"previous_test_selection.{field}"
            )

    minimum = _exact_nonnegative_int(
        report.get("min_traces"), "previous_gate_report.min_traces"
    )
    if minimum != TEST_MIN_TRACES:
        fail(
            "previous_gate_report.min_traces должен быть "
            f"{TEST_MIN_TRACES}, получено: {minimum}"
        )
    monitoring = report.get("monitoring")
    if not isinstance(monitoring, dict):
        fail("previous_gate_report.monitoring должен быть object")
    traces = _exact_nonnegative_int(
        monitoring.get("traces"), "previous_gate_report.monitoring.traces"
    )
    problems = report.get("problems")
    if not isinstance(problems, list) or any(
        not isinstance(problem, str) for problem in problems
    ):
        fail("previous_gate_report.problems должен быть списком строк")

    verdict = report.get("verdict")
    if verdict == "green":
        if problems:
            fail("green previous_gate_report не должен содержать problems")
        if traces < TEST_MIN_TRACES:
            fail(
                f"green previous_gate_report содержит меньше {TEST_MIN_TRACES} трейсов"
            )
        return "advance_after_green", traces

    low_volume_problem = (
        f"ветка monitoring: трейсов {traces} меньше порога {TEST_MIN_TRACES}"
    )
    if (
        verdict == "red"
        and traces < TEST_MIN_TRACES
        and problems == [low_volume_problem]
    ):
        return "extend_after_low_volume", traces
    if verdict not in {"green", "red"}:
        fail("previous_gate_report.verdict должен быть green или red")
    fail(
        "предыдущий Gate red не только из-за недостатка трейсов; "
        "автоматический переход запрещён: " + " | ".join(problems)
    )


def main(
    train_selection=None,
    previous_test_selection=None,
    previous_gate_report=None,
    as_of_date: str = "",
):
    """Собрать следующее закрытое test-окно относительно ``as_of_date``."""
    train = validate_selection(train_selection, "train_selection")
    as_of = parse_date(as_of_date, "as_of_date")
    train_end = parse_date(train["date_to"], "train_selection.date_to")

    has_previous = _is_connected(previous_test_selection)
    has_report = _is_connected(previous_gate_report)
    if has_previous != has_report:
        fail(
            "previous_test_selection и previous_gate_report должны быть "
            "подключены вместе"
        )

    previous_id = ""
    previous_traces = None
    if not has_previous:
        transition = "initial"
        test_from = train_end + timedelta(days=1)
        test_to = test_from
    else:
        previous = validate_selection(
            previous_test_selection, "previous_test_selection"
        )
        if not same_identity(train, previous):
            fail(
                "previous_test_selection относится к другой "
                "паре source/agent/distributive/tz"
            )
        previous_from = parse_date(
            previous["date_from"], "previous_test_selection.date_from"
        )
        previous_to = parse_date(previous["date_to"], "previous_test_selection.date_to")
        if previous_from <= train_end:
            fail("previous_test_selection пересекается с train-периодом")

        transition, previous_traces = _checked_gate_report(
            previous_gate_report, previous
        )
        previous_id = previous["selection_id"]
        if transition == "advance_after_green":
            test_from = previous_to + timedelta(days=1)
            test_to = test_from
        else:
            test_from = previous_from
            test_to = previous_to + timedelta(days=1)

    if test_to >= as_of:
        fail(
            f"test-окно {test_from}..{test_to} ещё не закрыто относительно "
            f"as_of_date={as_of}; допустимы даты не позже {as_of - timedelta(days=1)}"
        )

    result = build_selection(
        agent_id=train["agent_ci"],
        distributive=train["distributive"],
        date_from=test_from,
        date_to=test_to,
        tz=train["tz"],
        profile_role="rolling_test",
        expected_min_traces=TEST_MIN_TRACES,
    )
    result["report_meta"].update(
        {
            "as_of_date": as_of.isoformat(),
            "transition": transition,
            "train_selection_id": train["selection_id"],
            "previous_test_selection_id": previous_id,
            "previous_test_traces": previous_traces,
        }
    )
    selection = result["selection"]
    print(
        "Rolling test profile | "
        f"transition={transition} "
        f"selection={selection['selection_id'][:12]} "
        f"period={selection['date_from']}..{selection['date_to']} "
        f"as_of={as_of}"
    )
    return result
