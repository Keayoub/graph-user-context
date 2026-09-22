import os

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION_TESTS") != "1",
    reason="Set RUN_INTEGRATION_TESTS=1 and configure a test tenant to run integration tests",
)


def test_integration_tests_are_opt_in() -> None:
    assert os.getenv("RUN_INTEGRATION_TESTS") == "1"
