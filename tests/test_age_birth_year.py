"""Unit tests for analyzer.age_from_birth_year — birth year → current age."""
import pytest

from analyzer import age_from_birth_year


def test_typical_birth_year():
    assert age_from_birth_year(2014, today_year=2026) == 12

def test_uses_current_year_by_default():
    # Just assert it returns a plausible int, not the exact value (clock-dependent).
    out = age_from_birth_year(2010)
    assert isinstance(out, int) and 5 <= out <= 30

def test_none_returns_none():
    assert age_from_birth_year(None, today_year=2026) is None

def test_blank_string_returns_none():
    assert age_from_birth_year("", today_year=2026) is None

def test_numeric_string_ok():
    assert age_from_birth_year("2015", today_year=2026) == 11

def test_junk_returns_none():
    assert age_from_birth_year("banana", today_year=2026) is None

def test_implausible_year_returns_none():
    # A 4-digit year that yields an absurd age is rejected (typo guard).
    assert age_from_birth_year(1500, today_year=2026) is None
    assert age_from_birth_year(2030, today_year=2026) is None  # future
