"""Progress-reporter contract tests.

``ProgressReporter`` is a Protocol; plugins depend on the shape, not a
concrete class. ``NullReporter`` is the host's no-op default when a
plugin runs outside a job context — it must swallow calls silently.
"""
from __future__ import annotations

from magellon_sdk.progress import JobCancelledError, NullReporter, ProgressReporter


def test_null_reporter_report_no_args():
    NullReporter().report(0)


def test_null_reporter_report_with_message():
    NullReporter().report(50, "halfway")


def test_null_reporter_log():
    NullReporter().log("info", "hi")


def test_null_reporter_satisfies_protocol_structurally():
    reporter: ProgressReporter = NullReporter()
    reporter.report(10, "ok")
    reporter.log("warning", "meh")


def test_duck_typed_reporter_satisfies_protocol():
    """Any object with the right method shapes is a ProgressReporter."""
    captured: list = []

    class Duck:
        def report(self, percent, message=None):
            captured.append(("report", percent, message))

        def log(self, level, message):
            captured.append(("log", level, message))

    reporter: ProgressReporter = Duck()
    reporter.report(75, "almost")
    reporter.log("error", "boom")
    assert captured == [("report", 75, "almost"), ("log", "error", "boom")]


def test_job_cancelled_error_is_exception():
    assert issubclass(JobCancelledError, Exception)
    try:
        raise JobCancelledError("user cancelled")
    except JobCancelledError as e:
        assert "cancelled" in str(e)
