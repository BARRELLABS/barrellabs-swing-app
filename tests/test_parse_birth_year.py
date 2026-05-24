"""parse_birth_year: shared, generous birth-year validation used at signup,
add-player, and settings so a plausible year is stored and typos are dropped.
age_from_birth_year handles bracket fallback for ages outside the scored band."""
import datetime

from analyzer import parse_birth_year


def test_valid_year_int():
    assert parse_birth_year(2014) == 2014


def test_valid_year_string_with_whitespace():
    assert parse_birth_year("  2010 ") == 2010


def test_blank_and_none_are_none():
    assert parse_birth_year("") is None
    assert parse_birth_year(None) is None


def test_nonnumeric_is_none():
    assert parse_birth_year("abc") is None


def test_future_year_is_none():
    nxt = datetime.date.today().year + 1
    assert parse_birth_year(nxt) is None


def test_absurd_past_year_is_none():
    assert parse_birth_year(1500) is None


def test_current_year_ok():
    cur = datetime.date.today().year
    assert parse_birth_year(cur) == cur


def test_adult_birth_year_still_valid():
    # Coaches/adults exist; storage should accept the year even though
    # age_from_birth_year will fall back to the default bracket for them.
    assert parse_birth_year(1980) == 1980
