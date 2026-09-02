"""Profile ноды пользовательского test-окна."""

from __future__ import annotations

from .profile_contract import build_query_selection, parse_calendar_date


def main(
    agent_id: str = "",
    distributive: str = "",
    test_date_from: str = "",
    test_date_to: str = "",
    tz: str = "Europe/Moscow",
) -> dict:
    """Собрать заданные пользователем границы test для Query."""
    test_start_date = parse_calendar_date(test_date_from, "test_date_from")
    test_end_date = parse_calendar_date(test_date_to, "test_date_to")
    profile_output = build_query_selection(
        agent_id=agent_id,
        distributive=distributive,
        period_start_date=test_start_date,
        period_end_date=test_end_date,
        timezone_name=tz,
    )
    query_selection = profile_output["selection"]
    print(
        "Test window profile | "
        f"selection={query_selection['selection_id'][:12]} "
        f"agent={query_selection['agent_ci']} "
        f"distributive={query_selection['distributive']} "
        f"period={query_selection['date_from']}..{query_selection['date_to']} "
        f"tz={query_selection['tz']}"
    )
    return profile_output
