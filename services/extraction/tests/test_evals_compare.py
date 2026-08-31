"""Unit tests for Level 1 value comparison (no DB)."""

from evals.compare import lists_match, values_match


def test_dates_exact():
    assert values_match("commencement_date", "2020-01-01", "2020-01-01")
    assert not values_match("commencement_date", "2020-01-01", "2020-01-02")


def test_money_within_one_percent():
    assert values_match("security_deposit", 10000, 10050)
    assert not values_match("security_deposit", 10000, 10200)


def test_ints_exact():
    assert values_match("initial_term_months", 60, 60)
    assert not values_match("initial_term_months", 60, 61)


def test_strings_fuzzy():
    assert values_match("landlord", "Acme Realty LLC", "Acme Realty L.L.C.")
    assert not values_match("landlord", "Acme Realty", "Beta Holdings")


def test_lists_order_insensitive():
    gold = [
        {"period_start": "2020-01-01", "annual_rent": 100000},
        {"period_start": "2021-01-01", "annual_rent": 103000},
    ]
    extracted = list(reversed(gold))
    assert lists_match("base_rent_schedule", gold, extracted)


def test_normalize_prefixed_keys_in_gold_io():
    from evals.gold_io import normalize_field_key

    assert normalize_field_key("financial.security_deposit") == "security_deposit"
    assert normalize_field_key("landlord") == "landlord"
