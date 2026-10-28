"""Amounts are integers in micro-units on the wire: 1 XE = 1,000,000 µXE (same for XUSD)."""

from __future__ import annotations

from decimal import Decimal, ROUND_DOWN

MICRO = 1_000_000


def to_micro(amount: str | int | float | Decimal) -> int:
    d = Decimal(str(amount))
    return int((d * MICRO).to_integral_value(rounding=ROUND_DOWN))


def from_micro(micro: int) -> str:
    d = Decimal(int(micro)) / MICRO
    s = f"{d:.6f}".rstrip("0").rstrip(".")
    return s if s else "0"
