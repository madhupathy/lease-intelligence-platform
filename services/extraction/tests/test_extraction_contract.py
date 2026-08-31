"""Tests for extraction contract: schema, field matrix, and prompt templates."""

from __future__ import annotations

from datetime import date

import pytest
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.agent.matrix import FieldMatrix, load_field_matrix
from app.agent.prompts import PROMPTS_DIR, validate_injection_notice
from app.agent.schema import LeaseExtraction

PROMPT_TEMPLATES_V1 = [
    "parties_premises_v1.0.md.j2",
    "term_v1.0.md.j2",
    "financial_v1.0.md.j2",
    "options_obligations_v1.0.md.j2",
    "opex_v1.0.md.j2",
]

SAMPLE_EXTRACTION_JSON = {
    "parties_premises": {
        "landlord": {
            "value": "ACME Properties LLC",
            "confidence": 0.95,
            "page": 1,
            "snippet": "Landlord: ACME Properties LLC",
        },
        "tenant": {
            "value": "Beta Corp",
            "confidence": 0.93,
            "page": 1,
            "snippet": "Tenant: Beta Corp",
        },
        "premises_address": {
            "value": "100 Main St, Chicago, IL",
            "confidence": 0.91,
            "page": 2,
            "snippet": "Premises: 100 Main St, Chicago, IL",
        },
        "rentable_sqft": {
            "value": 12500,
            "confidence": 0.88,
            "page": 2,
            "snippet": "12,500 rentable square feet",
        },
    },
    "term": {
        "commencement_date": {
            "value": "2024-01-01",
            "confidence": 0.94,
            "page": 3,
            "snippet": "Commencement Date: January 1, 2024",
        },
        "expiration_date": {
            "value": "2029-12-31",
            "confidence": 0.94,
            "page": 3,
            "snippet": "Expiration Date: December 31, 2029",
        },
        "initial_term_months": {
            "value": 72,
            "confidence": 0.9,
            "page": 3,
            "snippet": "Initial term of seventy-two (72) months",
        },
    },
    "financial": {
        "base_rent_schedule": [
            {
                "period_start": {
                    "value": "2024-01-01",
                    "confidence": 0.92,
                    "page": 5,
                    "snippet": "Year 1: January 1, 2024",
                },
                "period_end": {
                    "value": "2024-12-31",
                    "confidence": 0.92,
                    "page": 5,
                    "snippet": "through December 31, 2024",
                },
                "annual_rent": {
                    "value": 600000.0,
                    "confidence": 0.93,
                    "page": 5,
                    "snippet": "Annual Base Rent: $600,000",
                },
                "monthly_rent": {
                    "value": 50000.0,
                    "confidence": 0.93,
                    "page": 5,
                    "snippet": "Monthly Base Rent: $50,000",
                },
            },
            {
                "period_start": {
                    "value": "2025-01-01",
                    "confidence": 0.9,
                    "page": 5,
                    "snippet": "Year 2: January 1, 2025",
                },
                "period_end": {
                    "value": "2025-12-31",
                    "confidence": 0.9,
                    "page": 5,
                    "snippet": "through December 31, 2025",
                },
                "annual_rent": {
                    "value": 630000.0,
                    "confidence": 0.9,
                    "page": 5,
                    "snippet": "Annual Base Rent: $630,000",
                },
                "monthly_rent": {
                    "value": 52500.0,
                    "confidence": 0.9,
                    "page": 5,
                    "snippet": "Monthly Base Rent: $52,500",
                },
            },
        ],
        "escalation_type": {
            "value": "fixed_pct",
            "confidence": 0.85,
            "page": 6,
            "snippet": "five percent (5%) annual increase",
        },
        "escalation_value": {
            "value": 5.0,
            "confidence": 0.85,
            "page": 6,
            "snippet": "five percent (5%)",
        },
        "security_deposit": {
            "value": 100000.0,
            "confidence": 0.91,
            "page": 7,
            "snippet": "Security Deposit: $100,000",
        },
    },
    "options_obligations": {
        "renewal_options": [
            {
                "term_months": {
                    "value": 60,
                    "confidence": 0.87,
                    "page": 10,
                    "snippet": "one additional period of five (5) years",
                },
                "notice_min_days": {
                    "value": 180,
                    "confidence": 0.86,
                    "page": 10,
                    "snippet": "not less than one hundred eighty (180) days",
                },
                "notice_max_days": {
                    "value": 365,
                    "confidence": 0.84,
                    "page": 10,
                    "snippet": "not more than three hundred sixty-five (365) days",
                },
                "rent_basis": {
                    "value": "fair market rent",
                    "confidence": 0.82,
                    "page": 10,
                    "snippet": "fair market rent for comparable space",
                },
            }
        ],
        "termination_option": {
            "date": {
                "value": "2027-06-30",
                "confidence": 0.8,
                "page": 12,
                "snippet": "Termination Date: June 30, 2027",
            },
            "notice_days": {
                "value": 90,
                "confidence": 0.79,
                "page": 12,
                "snippet": "ninety (90) days prior written notice",
            },
            "fee": {
                "value": 250000.0,
                "confidence": 0.78,
                "page": 12,
                "snippet": "termination fee of $250,000",
            },
        },
        "holdover_rate_pct": {
            "value": 150.0,
            "confidence": 0.83,
            "page": 13,
            "snippet": "one hundred fifty percent (150%) of Base Rent",
        },
    },
    "opex": {
        "cam_structure": {
            "value": "net",
            "confidence": 0.9,
            "page": 8,
            "snippet": "Tenant shall pay all Operating Expenses",
        },
        "base_year": {
            "value": 2024,
            "confidence": 0.88,
            "page": 8,
            "snippet": "Base Year: calendar year 2024",
        },
        "cam_cap_pct": {
            "value": 5.0,
            "confidence": 0.75,
            "page": 9,
            "snippet": "five percent (5%) cumulative cap",
        },
        "cam_cap_type": {
            "value": "cumulative",
            "confidence": 0.74,
            "page": 9,
            "snippet": "cumulative cap on Controllable Expenses",
        },
    },
}


class TestExtractionSchema:
    def test_lease_extraction_round_trip_from_json(self) -> None:
        model = LeaseExtraction.model_validate(SAMPLE_EXTRACTION_JSON)
        assert model.parties_premises.landlord.value == "ACME Properties LLC"
        assert len(model.financial.base_rent_schedule) == 2
        assert model.financial.base_rent_schedule[0].annual_rent.value == 600000.0
        assert model.financial.base_rent_schedule[1].monthly_rent.value == 52500.0

        dumped = model.model_dump(mode="json")
        round_trip = LeaseExtraction.model_validate(dumped)
        assert round_trip == model

    def test_extra_fields_forbidden(self) -> None:
        payload = dict(SAMPLE_EXTRACTION_JSON)
        payload["unexpected"] = "nope"
        with pytest.raises(Exception):
            LeaseExtraction.model_validate(payload)

    def test_termination_option_partial_date_without_fee(self) -> None:
        payload = dict(SAMPLE_EXTRACTION_JSON)
        payload["options_obligations"]["termination_option"] = {
            "date": {
                "value": "2027-06-30",
                "confidence": 0.85,
                "page": 12,
                "snippet": "Termination Date: June 30, 2027",
            },
            "notice_days": {"value": 90, "confidence": 0.8, "page": 12, "snippet": "ninety days notice"},
            "fee": {"value": None, "confidence": 0.0, "page": None, "snippet": None},
        }
        model = LeaseExtraction.model_validate(payload)
        assert model.options_obligations.termination_option is not None
        assert model.options_obligations.termination_option.date.value == date(2027, 6, 30)
        assert model.options_obligations.termination_option.fee.value is None

        round_trip = LeaseExtraction.model_validate(model.model_dump(mode="json"))
        assert round_trip.options_obligations.termination_option is not None
        assert round_trip.options_obligations.termination_option.fee.value is None


class TestFieldMatrix:
    def test_loads_and_validates_yaml(self) -> None:
        matrix = load_field_matrix()
        assert isinstance(matrix, FieldMatrix)
        assert set(matrix.groups) == {
            "parties_premises",
            "term",
            "financial",
            "options_obligations",
            "opex",
        }

        financial = matrix.groups["financial"]
        assert "base rent" in financial.keywords
        assert financial.priority == 30
        assert any("base rent" in pattern for pattern in financial.heading_signals)

        opex = matrix.groups["opex"]
        assert "operating expenses" in opex.keywords
        assert any("cam" in pattern.lower() for pattern in opex.heading_signals)

        options = matrix.groups["options_obligations"]
        assert "option to renew" in options.keywords


class TestPromptTemplates:
    @pytest.fixture
    def jinja_env(self) -> Environment:
        return Environment(
            loader=FileSystemLoader(PROMPTS_DIR),
            autoescape=select_autoescape(enabled_extensions=()),
        )

    def test_every_v1_template_renders_with_dummy_context(self, jinja_env: Environment) -> None:
        dummy_context = "Page 1: Sample lease clause for template rendering test."
        for template_name in PROMPT_TEMPLATES_V1:
            rendered = jinja_env.get_template(template_name).render(context=dummy_context)
            assert dummy_context in rendered
            assert "<document>" in rendered

    def test_all_templates_include_injection_notice(self) -> None:
        for template_name in PROMPT_TEMPLATES_V1:
            content = (PROMPTS_DIR / template_name).read_text(encoding="utf-8")
            validate_injection_notice(content)

    def test_injection_notice_scan_rejects_missing_line(self) -> None:
        with pytest.raises(ValueError, match="missing injection notice"):
            validate_injection_notice("## Role\nNo safety notice here.")

    def test_scan_all_versioned_templates_on_disk(self) -> None:
        """Every *_v*.md.j2 file must contain the injection notice."""
        template_paths = sorted(PROMPTS_DIR.glob("*_v*.md.j2"))
        assert len(template_paths) == len(PROMPT_TEMPLATES_V1)
        for path in template_paths:
            validate_injection_notice(path.read_text(encoding="utf-8"))
