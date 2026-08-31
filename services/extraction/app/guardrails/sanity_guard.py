"""Output guard: date and rent sanity checks (AGENTS.md §8)."""

from __future__ import annotations

from datetime import date

from app.agent.schema import ExtractedValue, Financial, Term
from app.guardrails import Result, Verdict
from app.guardrails.context import GuardContext

_MIN_DATE = date(1950, 1, 1)
_MAX_DATE = date(2100, 12, 31)


def _check_date(value: date | None, field_path: str, flags: list[str]) -> None:
    if value is None:
        return
    if value < _MIN_DATE or value > _MAX_DATE:
        flags.append(f"{field_path} date out of range: {value}")


def _check_positive_number(value: float | int | None, field_path: str, flags: list[str]) -> None:
    if value is None:
        return
    if value <= 0:
        flags.append(f"{field_path} must be > 0, got {value}")


class SanityGuard:
    def check(self, ctx: GuardContext) -> Result:
        flags: list[str] = []

        if isinstance(ctx.group_model, Term):
            term = ctx.group_model
            _check_date(term.commencement_date.value, "commencement_date", flags)
            _check_date(term.expiration_date.value, "expiration_date", flags)
            if (
                term.commencement_date.value is not None
                and term.expiration_date.value is not None
                and term.expiration_date.value <= term.commencement_date.value
            ):
                flags.append("expiration_date must be after commencement_date")

        if isinstance(ctx.group_model, Financial):
            financial = ctx.group_model
            for index, period in enumerate(financial.base_rent_schedule):
                prefix = f"base_rent_schedule[{index}]"
                _check_date(period.period_start.value, f"{prefix}.period_start", flags)
                _check_date(period.period_end.value, f"{prefix}.period_end", flags)
                _check_positive_number(period.annual_rent.value, f"{prefix}.annual_rent", flags)
                _check_positive_number(period.monthly_rent.value, f"{prefix}.monthly_rent", flags)
            _check_positive_number(financial.escalation_value.value, "escalation_value", flags)
            _check_positive_number(financial.security_deposit.value, "security_deposit", flags)

        if flags:
            return Result(Verdict.FLAG, "; ".join(flags))

        return Result(Verdict.PASS)
