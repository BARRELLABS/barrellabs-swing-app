"""unique_upload_name: collision-resistant per-user upload filenames so
concurrent users sharing one upload dir can't overwrite each other's video
and fingerprint mid-analysis (the whole artifact chain keys off this stem)."""
from upload_paths import unique_upload_name


def test_same_filename_two_users_are_distinct():
    a = unique_upload_name("IMG_1234.mov", owner="ann")
    b = unique_upload_name("IMG_1234.mov", owner="ben")
    assert a != b


def test_same_filename_same_user_distinct_each_call():
    # iPhone exports collide constantly ("IMG_1234.mov", "swing.mp4").
    a = unique_upload_name("swing.mp4", owner="ann")
    b = unique_upload_name("swing.mp4", owner="ann")
    assert a != b


def test_preserves_extension_lowercased():
    assert unique_upload_name("Clip.MOV", owner="ann").endswith(".mov")


def test_keeps_owner_token_and_stem_hint():
    name = unique_upload_name("my swing.mp4", owner="ann", token="tok")
    assert name == "ann_tok_my-swing.mp4"


def test_sanitizes_path_traversal_in_name_and_owner():
    name = unique_upload_name("../../etc/passwd.mp4", owner="../x", token="tok")
    assert "/" not in name
    assert ".." not in name


def test_blank_name_falls_back_safely():
    assert unique_upload_name("", owner=None, token="tok") == "anon_tok_swing.mp4"
