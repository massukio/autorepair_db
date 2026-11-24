"""An exception inside a Qt slot would make PyQt5 abort the whole run.
Record it instead and fail the test that caused it."""
import sys

import pytest

_errors = []


def _hook(exc_type, exc, tb):
    _errors.append(exc)


@pytest.fixture(autouse=True)
def _qt_exceptions_fail_the_test():
    old = sys.excepthook
    sys.excepthook = _hook
    _errors.clear()
    yield
    sys.excepthook = old
    if _errors:
        raise _errors[0]
