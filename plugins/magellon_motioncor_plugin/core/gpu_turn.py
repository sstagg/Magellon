"""One MotionCor run per GPU at a time, single-file tests first.

A plugin container drives one GPU. Import tasks (the main queue) and the
single-file tests from the Run Processing Jobs page (the test queue) are
consumed on separate threads, but a MotionCor run takes most of the GPU's
memory, so they must not overlap. ``gpu_turn`` serializes them and lets a
waiting test go before the next import task: a test waits at most for the
run already on the GPU.
"""
from __future__ import annotations

import threading
from contextlib import contextmanager

_cond = threading.Condition()
_busy = False
_tests_waiting = 0


@contextmanager
def gpu_turn(*, test: bool = False):
    global _busy, _tests_waiting
    with _cond:
        if test:
            _tests_waiting += 1
        try:
            while _busy or (not test and _tests_waiting):
                _cond.wait()
        finally:
            if test:
                _tests_waiting -= 1
        _busy = True
    try:
        yield
    finally:
        with _cond:
            _busy = False
            _cond.notify_all()
