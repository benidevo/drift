import argparse
import json
import logging
import sys

from drift.app import DriftApplication
from drift.exceptions import ConfigurationError, DriftException, SecurityError
from drift.security import SecurityValidator


def setup_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)

    if log_format == "json":
        logging.basicConfig(
            level=level,
            format=(
                '{"time": "%(asctime)s", "level": "%(levelname)s", '
                '"message": "%(message)s"}'
            ),
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    else:
        logging.basicConfig(
            level=level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Drift - Git Provider Code Review Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--config",
        "-c",
        type=str,
        help="Path to configuration file",
    )

    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level",
    )

    parser.add_argument(
        "--log-format",
        type=str,
        default="json",
        choices=["json", "text"],
        help="Logging format",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    analyze_parser = subparsers.add_parser("analyze", help="Analyze a pull request")
    analyze_parser.add_argument(
        "pr_id",
        type=SecurityValidator.validate_pr_id,
        help="Pull request ID (positive integer)",
    )
    analyze_parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Output file path (default: stdout)",
    )

    comment_parser = subparsers.add_parser("comment", help="Post a comment on a PR")
    comment_parser.add_argument(
        "pr_id",
        type=SecurityValidator.validate_pr_id,
        help="Pull request ID (positive integer)",
    )
    comment_parser.add_argument("comment", help="Comment text")

    update_parser = subparsers.add_parser("update", help="Update an existing comment")
    update_parser.add_argument(
        "pr_id",
        type=SecurityValidator.validate_pr_id,
        help="Pull request ID (positive integer)",
    )
    update_parser.add_argument(
        "comment_id",
        type=SecurityValidator.validate_comment_id,
        help="Comment ID to update",
    )
    update_parser.add_argument("comment", help="New comment text")

    subparsers.add_parser("test", help="Test configuration")

    args = parser.parse_args()

    setup_logging(args.log_level, args.log_format)
    logger = logging.getLogger(__name__)

    try:
        if args.config:
            config_path = SecurityValidator.validate_config_path(args.config)
            logger.info(f"Loading configuration from file: {config_path.name}")
            app = DriftApplication.from_file(str(config_path))
        else:
            logger.info("Loading configuration from environment variables")
            app = DriftApplication.from_env()

        if args.command == "analyze":
            logger.info(f"Analyzing PR: {args.pr_id}")
            result = app.analyze_pr(args.pr_id)

            output = json.dumps(result, indent=2, default=str)

            if args.output:
                output_path = SecurityValidator.validate_output_path(args.output)
                output_path.write_text(output)
                output_path.chmod(0o644)
                logger.info(f"Analysis saved to: {output_path.name}")
            else:
                print(output)

        elif args.command == "comment":
            logger.info(f"Posting comment to PR: {args.pr_id}")
            app.post_review(args.pr_id, args.comment)
            logger.info("Comment posted successfully")

        elif args.command == "update":
            logger.info(f"Updating comment {args.comment_id} on PR: {args.pr_id}")
            app.update_review(args.pr_id, args.comment_id, args.comment)
            logger.info("Comment updated successfully")

        elif args.command == "test":
            logger.info("Testing configuration...")
            logger.info(f"Provider: {app.config.provider}")
            logger.info(f"Repository: {app.config.repo}")
            logger.info(f"Base URL: {app.config.base_url or 'default'}")

            client = app.client
            logger.info(f"Client created successfully: {client.__class__.__name__}")
            print("Configuration is valid!")

        else:
            parser.print_help()
            sys.exit(1)

    except ConfigurationError as e:
        sanitized_error = SecurityValidator.sanitize_error_message(e)
        logger.error(f"Configuration error: {sanitized_error}")
        sys.exit(1)
    except SecurityError as e:
        logger.error(f"Security error: {e}")
        sys.exit(1)
    except DriftException as e:
        sanitized_error = SecurityValidator.sanitize_error_message(e)
        logger.error(f"Application error: {sanitized_error}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(130)
    except Exception as e:
        sanitized_error = SecurityValidator.sanitize_error_message(e)
        logger.error(f"Unexpected error: {sanitized_error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
