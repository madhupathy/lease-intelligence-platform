"""Field key → extraction group mapping (AGENTS.md §6)."""

from __future__ import annotations

FIELD_GROUPS: dict[str, list[str]] = {
    "parties_premises": ["landlord", "tenant", "premises_address", "rentable_sqft"],
    "term": ["commencement_date", "expiration_date", "initial_term_months"],
    "financial": [
        "base_rent_schedule",
        "escalation_type",
        "escalation_value",
        "security_deposit",
    ],
    "options_obligations": ["renewal_options", "termination_option", "holdover_rate_pct"],
    "opex": ["cam_structure", "base_year", "cam_cap_pct", "cam_cap_type"],
}

FIELD_TO_GROUP: dict[str, str] = {
    field_key: group for group, keys in FIELD_GROUPS.items() for field_key in keys
}
