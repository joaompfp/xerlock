"""Format detection and dispatch (backend/schedule.py): the content decides the reader."""

import sys

import pytest

from backend.schedule import MPP_NEEDS_XML, detect_format, parse_schedule


def test_formats_are_detected_from_content():
    assert detect_format(b"ERMHDR\t15.2\t2026-03-02") == "xer"
    assert detect_format(b"\xef\xbb\xbf<?xml version='1.0'?><Project>") == "mspdi"
    assert detect_format(b"  \r\n<Project xmlns='x'>") == "mspdi"
    assert detect_format(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\0" * 100) == "mpp"
    # Anything else is handed to the .xer reader, as every upload was before.
    assert detect_format(b"PK\x03\x04") == "xer"
    assert detect_format(b"") == "xer"


def test_unknown_content_fails_in_the_xer_reader(tmp_path):
    p = tmp_path / "x.xer"
    p.write_bytes(b"not a schedule")
    with pytest.raises(ValueError, match="No projects"):
        parse_schedule(str(p))


def test_mpp_without_java_says_save_as_xml(tmp_path, monkeypatch):
    """The standalone build (and a server without a JRE) cannot import backend.mpp; the
    user is told to save the file from Project as XML instead."""
    p = tmp_path / "x.mpp"
    p.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\0" * 600)
    import backend
    monkeypatch.setitem(sys.modules, "backend.mpp", None)  # makes the import raise ImportError
    monkeypatch.delattr(backend, "mpp", raising=False)     # even when another test imported it
    with pytest.raises(ValueError) as e:
        parse_schedule(str(p))
    assert str(e.value) == MPP_NEEDS_XML and "Save As > XML" in MPP_NEEDS_XML
