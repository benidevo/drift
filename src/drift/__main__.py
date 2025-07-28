import logging
import sys

from drift.logger import setup_logging


def main() -> int:
    setup_logging()
    logger = logging.getLogger("drift")

    logger.info("Drift AI-powered architectural code review")
    logger.info("Starting analysis...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
