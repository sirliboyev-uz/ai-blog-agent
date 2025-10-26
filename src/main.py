"""Main entry point for AI Blog Agent with scheduling support."""

import sys
import argparse
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from src.models.config import get_settings
from src.agents.blog_agent import BlogAgent
from src.utils.logger import setup_logger
from src.utils.notifications import NotificationService


def run_batch_job(limit: int = None):
    """
    Run batch processing job.

    Args:
        limit: Maximum number of topics to process
    """
    logger.info("="*60)
    logger.info(f"Starting batch job at {datetime.now()}")
    logger.info("="*60)

    try:
        agent = BlogAgent()
        stats = agent.process_batch(limit=limit)

        # Send notification
        notifier = NotificationService()
        notifier.send_batch_summary(stats)

        logger.info(f"Batch job completed: {stats}")

    except Exception as e:
        logger.error(f"Batch job failed: {e}")
        raise


def run_demo():
    """Run demo mode to generate test content."""
    logger.info("Running in DEMO mode (no WordPress publishing)")

    try:
        agent = BlogAgent()
        success = agent.generate_demo_post()

        if success:
            logger.success("Demo completed successfully!")
        else:
            logger.error("Demo failed")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Demo failed: {e}")
        sys.exit(1)


def setup_scheduler():
    """Setup automated scheduler based on configuration."""
    settings = get_settings()

    scheduler = BlockingScheduler()

    # Calculate how many times per week to post
    posts_per_week = settings.posts_per_week_per_site
    posting_hours = settings.posting_hours_list

    # For 3 posts per week, schedule for Mon, Wed, Fri
    # For 2 posts per week, schedule for Tue, Thu
    if posts_per_week == 3:
        days = "mon,wed,fri"
    elif posts_per_week == 2:
        days = "tue,thu"
    elif posts_per_week == 1:
        days = "mon"
    else:
        # Daily or custom
        days = "*"

    # Schedule for each posting hour
    for hour in posting_hours:
        cron_trigger = CronTrigger(
            day_of_week=days,
            hour=hour,
            minute=0
        )

        scheduler.add_job(
            run_batch_job,
            trigger=cron_trigger,
            args=[1],  # Process 1 topic per scheduled run
            id=f"batch_job_{hour}",
            name=f"Batch Processing at {hour}:00"
        )

        logger.info(f"Scheduled: {days} at {hour}:00")

    logger.info("Scheduler configured. Starting...")
    logger.info("Press Ctrl+C to stop")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped")


def create_template_sheet():
    """Create template Google Sheets structure."""
    logger.info("Creating template sheets...")

    try:
        from src.services.sheets_client import SheetsClient

        sheets_client = SheetsClient()
        sheets_client.create_template_sheet()

        logger.success("Template sheets created successfully!")

    except Exception as e:
        logger.error(f"Failed to create template sheets: {e}")
        sys.exit(1)


def test_connections():
    """Test all API connections."""
    logger.info("Testing connections...")

    settings = get_settings()
    all_ok = True

    # Test OpenAI
    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key)
        client.models.list()
        logger.success("✅ OpenAI connection OK")
    except Exception as e:
        logger.error(f"❌ OpenAI connection failed: {e}")
        all_ok = False

    # Test WordPress sites
    from src.services.wordpress_client import WordPressClient

    for site in settings.wordpress_sites:
        try:
            wp_client = WordPressClient(site)
            if wp_client.test_connection():
                logger.success(f"✅ WordPress connection OK: {site.name}")
            else:
                logger.error(f"❌ WordPress connection failed: {site.name}")
                all_ok = False
        except Exception as e:
            logger.error(f"❌ WordPress connection failed ({site.name}): {e}")
            all_ok = False

    # Test Google Sheets
    try:
        from src.services.sheets_client import SheetsClient
        sheets_client = SheetsClient()
        logger.success("✅ Google Sheets connection OK")
    except Exception as e:
        logger.error(f"❌ Google Sheets connection failed: {e}")
        all_ok = False

    if all_ok:
        logger.success("\n🎉 All connections successful!")
    else:
        logger.error("\n❌ Some connections failed. Check configuration.")
        sys.exit(1)


def main():
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="AI Blog Agent - Automated WordPress content generation and publishing"
    )

    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run in demo mode (generate content without publishing)"
    )

    parser.add_argument(
        "--batch",
        type=int,
        metavar="N",
        help="Process N topics from Google Sheets and publish"
    )

    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Run automated scheduler based on config"
    )

    parser.add_argument(
        "--test-connections",
        action="store_true",
        help="Test all API connections (OpenAI, WordPress, Google Sheets)"
    )

    parser.add_argument(
        "--create-template",
        action="store_true",
        help="Create template Google Sheets structure"
    )

    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Set logging level"
    )

    args = parser.parse_args()

    # Setup logging
    setup_logger(log_level=args.log_level)

    logger.info("AI Blog Agent starting...")

    # Execute based on mode
    if args.demo:
        run_demo()

    elif args.batch is not None:
        run_batch_job(limit=args.batch)

    elif args.schedule:
        setup_scheduler()

    elif args.test_connections:
        test_connections()

    elif args.create_template:
        create_template_sheet()

    else:
        parser.print_help()
        logger.info("\nNo mode specified. Use --demo, --batch, --schedule, or --test-connections")


if __name__ == "__main__":
    main()
