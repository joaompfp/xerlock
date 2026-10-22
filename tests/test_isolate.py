"""Parsing in a child process: results come back whole, refusals keep their message,
and a parse that hangs, crashes or dies ends as an error instead of taking the server."""

import os
import time

import pytest

from backend.isolate import ParseFailed, parse_isolated


def test_a_schedule_comes_back_whole(sample_path):
    data = parse_isolated(sample_path)
    assert len(data["activities"]) == 24


def test_a_refusal_keeps_its_message(tmp_path):
    f = tmp_path / "empty.xer"
    f.write_text("ERMHDR\t20.12\n%E\n")
    with pytest.raises(ValueError, match="No projects"):
        parse_isolated(str(f))


def test_a_parse_over_time_is_stopped():
    start = time.monotonic()
    with pytest.raises(ValueError, match="took more than"):
        parse_isolated(30, timeout=0.5, fn=time.sleep)
    assert time.monotonic() - start < 10


def test_a_crash_is_reported_without_raising_it():
    with pytest.raises(ParseFailed) as e:
        parse_isolated(5, fn=len)  # TypeError inside the child
    assert "Could not parse" in str(e.value)
    assert "TypeError" in e.value.detail


def test_a_child_that_dies_is_an_error():
    with pytest.raises(ParseFailed):
        parse_isolated(3, fn=os._exit)
