"""prune_stale_files bounds local disk growth: it deletes old upload videos and
generated analysis artifacts, but only files older than the cutoff (so an
in-flight analysis is safe) and only artifacts by known suffix (so committed
files like mlb_match_stats.json are never touched)."""
import os
import time

from cleanup_utils import prune_stale_files


def _age(path, hours):
    t = time.time() - hours * 3600
    os.utime(path, (t, t))


def test_prunes_old_uploads_keeps_recent(tmp_path):
    up = tmp_path / "uploads"; up.mkdir()
    root = tmp_path / "root"; root.mkdir()
    old = up / "old.mp4"; old.write_bytes(b"x"); _age(old, 5)
    new = up / "new.mp4"; new.write_bytes(b"x")

    prune_stale_files(up, root, max_age_hours=2.0)

    assert not old.exists()
    assert new.exists()


def test_prunes_old_artifacts_by_suffix_only(tmp_path):
    up = tmp_path / "uploads"; up.mkdir()
    root = tmp_path / "root"; root.mkdir()
    old_fp = root / "abc_fingerprint.json"; old_fp.write_text("{}"); _age(old_fp, 5)
    old_keep = root / "mlb_match_stats.json"; old_keep.write_text("{}"); _age(old_keep, 5)
    new_fp = root / "def_fingerprint.json"; new_fp.write_text("{}")

    prune_stale_files(up, root, max_age_hours=2.0)

    assert not old_fp.exists()      # old generated artifact removed
    assert old_keep.exists()        # committed non-artifact kept even though old
    assert new_fp.exists()          # recent artifact kept


def test_missing_dirs_do_not_raise(tmp_path):
    prune_stale_files(tmp_path / "nope", tmp_path / "nope2")
