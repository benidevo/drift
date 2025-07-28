import logging

import pytest


@pytest.fixture(autouse=True)
def reset_logging():
    """Reset logging configuration before each test."""
    # Get the drift logger
    logger = logging.getLogger("drift")

    # Store original state
    original_handlers = logger.handlers[:]
    original_propagate = logger.propagate

    # Clear handlers and ensure propagation for tests
    logger.handlers.clear()
    logger.propagate = True

    yield

    # Restore original state
    logger.handlers = original_handlers
    logger.propagate = original_propagate
