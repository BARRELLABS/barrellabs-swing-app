"""Locks the facility-logo XSS guard: only a small real PNG data-URI is a valid
logo (it renders into sponsored kids' reports, so a crafted logo_url must be
rejected on write)."""
import base64, io
import facility_storage as fs


def _png_uri(size=(8, 8)):
    from PIL import Image
    buf = io.BytesIO(); Image.new("RGBA", size).save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def test_valid_png_accepted():
    assert fs._is_valid_png_data_uri(_png_uri()) is True


def test_attribute_breakout_rejected():
    assert fs._is_valid_png_data_uri('x" onerror="alert(1)') is False


def test_non_png_data_uri_rejected():
    payload = base64.b64encode(b"<script>alert(1)</script>").decode()
    assert fs._is_valid_png_data_uri("data:text/html;base64," + payload) is False


def test_javascript_scheme_rejected():
    assert fs._is_valid_png_data_uri("javascript:alert(1)") is False


def test_oversized_png_rejected():
    import os
    from PIL import Image
    n = 400  # a noise PNG this size is ~640KB, over the 400KB cap
    img = Image.frombytes("RGBA", (n, n), os.urandom(n * n * 4))
    buf = io.BytesIO(); img.save(buf, format="PNG")
    uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    assert len(buf.getvalue()) > 400_000   # sanity: it really is oversized
    assert fs._is_valid_png_data_uri(uri) is False


def test_set_facility_logo_rejects_junk_without_backend():
    # backend not configured in tests -> still must reject junk before any write
    assert fs.set_facility_logo("fid", "javascript:alert(1)")["ok"] is False
