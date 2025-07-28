import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    logger = logging.getLogger("drift")

    # Only add handler if none exist (avoid duplicates)
    if not logger.handlers:
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.setLevel(level)
    # Keep propagate=True so pytest can capture logs
