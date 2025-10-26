"""Google Sheets integration for reading topics and logging results."""

from typing import List, Optional
import gspread
from google.oauth2.service_account import Credentials
from loguru import logger

from src.models.blog_post import BlogTopic, PostLog
from src.models.config import get_settings


class SheetsClient:
    """Google Sheets client for data management."""

    # Google Sheets API scopes
    SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]

    def __init__(self):
        """Initialize Google Sheets client."""
        self.settings = get_settings()
        self.client = self._authenticate()
        self.sheet = self.client.open_by_key(self.settings.google_sheet_id)

    def _authenticate(self) -> gspread.Client:
        """Authenticate with Google Sheets API."""
        try:
            credentials = Credentials.from_service_account_file(
                self.settings.google_sheets_credentials_file,
                scopes=self.SCOPES
            )
            return gspread.authorize(credentials)
        except Exception as e:
            logger.error(f"Failed to authenticate with Google Sheets: {e}")
            raise

    def get_pending_topics(self, limit: Optional[int] = None) -> List[BlogTopic]:
        """
        Get pending blog topics from the input worksheet.

        Expected columns: Topic, Business Type, Location, Internal Link URLs, Site Domain, Status

        Args:
            limit: Maximum number of topics to retrieve

        Returns:
            List of BlogTopic objects where Status is empty or 'Pending'
        """
        try:
            worksheet = self.sheet.worksheet("Topics")  # Input sheet name
            all_records = worksheet.get_all_records()

            topics = []
            for idx, row in enumerate(all_records, start=2):  # Start at 2 (row 1 is headers)
                # Skip if already processed
                status = row.get("Status", "").strip().lower()
                if status in ["completed", "processing", "failed"]:
                    continue

                try:
                    topic = BlogTopic.from_sheet_row(row, row_number=idx)
                    topics.append(topic)

                    if limit and len(topics) >= limit:
                        break

                except Exception as e:
                    logger.warning(f"Skipping invalid row {idx}: {e}")
                    continue

            logger.info(f"Found {len(topics)} pending topics")
            return topics

        except gspread.exceptions.WorksheetNotFound:
            logger.error("Worksheet 'Topics' not found. Please create it with required columns.")
            return []
        except Exception as e:
            logger.error(f"Failed to read topics from sheet: {e}")
            return []

    def mark_topic_status(self, row_number: int, status: str, post_url: Optional[str] = None):
        """
        Update topic status in the sheet.

        Args:
            row_number: Row number to update
            status: New status (Processing/Completed/Failed)
            post_url: Published post URL (optional)
        """
        try:
            worksheet = self.sheet.worksheet("Topics")

            # Find Status column (usually column F)
            headers = worksheet.row_values(1)
            try:
                status_col = headers.index("Status") + 1
            except ValueError:
                logger.warning("Status column not found, adding it")
                status_col = len(headers) + 1
                worksheet.update_cell(1, status_col, "Status")

            # Update status
            worksheet.update_cell(row_number, status_col, status)

            # If post URL provided, add it to Post URL column
            if post_url:
                try:
                    url_col = headers.index("Post URL") + 1
                except ValueError:
                    url_col = len(headers) + 2
                    worksheet.update_cell(1, url_col, "Post URL")

                worksheet.update_cell(row_number, url_col, post_url)

            logger.info(f"Updated row {row_number}: {status}")

        except Exception as e:
            logger.error(f"Failed to update topic status: {e}")

    def log_post_result(self, post_log: PostLog):
        """
        Log post result to the Logs worksheet.

        Args:
            post_log: PostLog object with result data
        """
        if not self.settings.log_to_sheet:
            return

        try:
            # Get or create Logs worksheet
            try:
                log_worksheet = self.sheet.worksheet("Logs")
            except gspread.exceptions.WorksheetNotFound:
                logger.info("Creating Logs worksheet")
                log_worksheet = self.sheet.add_worksheet("Logs", rows=1000, cols=10)

                # Add headers
                headers = [
                    "Date", "Site", "Topic", "Post Title",
                    "Post URL", "Word Count", "Status", "Error"
                ]
                log_worksheet.update('A1:H1', [headers])

            # Append log row
            log_worksheet.append_row(post_log.to_sheet_row())
            logger.debug(f"Logged result for: {post_log.post_title}")

        except Exception as e:
            logger.error(f"Failed to log to sheet: {e}")

    def create_template_sheet(self):
        """Create template worksheets with proper headers."""
        try:
            # Create Topics worksheet
            try:
                topics_ws = self.sheet.worksheet("Topics")
            except gspread.exceptions.WorksheetNotFound:
                topics_ws = self.sheet.add_worksheet("Topics", rows=100, cols=7)

            topics_headers = [
                "Topic",
                "Business Type",
                "Location",
                "Internal Link URLs",
                "Site Domain",
                "Status",
                "Post URL"
            ]
            topics_ws.update('A1:G1', [topics_headers])

            # Create Logs worksheet
            try:
                logs_ws = self.sheet.worksheet("Logs")
            except gspread.exceptions.WorksheetNotFound:
                logs_ws = self.sheet.add_worksheet("Logs", rows=1000, cols=8)

            logs_headers = [
                "Date", "Site", "Topic", "Post Title",
                "Post URL", "Word Count", "Status", "Error"
            ]
            logs_ws.update('A1:H1', [logs_headers])

            logger.info("Template sheets created successfully")

        except Exception as e:
            logger.error(f"Failed to create template sheets: {e}")
            raise
