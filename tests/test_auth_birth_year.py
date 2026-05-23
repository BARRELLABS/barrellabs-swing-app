"""birth_year round-trips through the profile mapping + is update-whitelisted."""
import auth


def test_profile_from_row_includes_birth_year():
    row = {"id": "p1", "user_id": "u1", "name": "Test", "handedness": "RIGHT",
           "birth_year": 2014}
    prof = auth._profile_from_row(row)
    assert prof["birth_year"] == 2014

def test_profile_from_row_birth_year_absent_is_none():
    prof = auth._profile_from_row({"id": "p1", "name": "Test"})
    assert prof.get("birth_year") is None

def test_birth_year_is_update_whitelisted():
    assert "birth_year" in auth.ALLOWED_PROFILE_UPDATES
