"""Configuration models and settings management."""

from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import json


class WordPressSite(BaseSettings):
    """WordPress site configuration."""

    name: str = Field(..., description="Site display name")
    url: str = Field(..., description="WordPress site URL")
    username: str = Field(..., description="WordPress username")
    app_password: str = Field(..., description="WordPress application password")

    model_config = SettingsConfigDict(extra='ignore')


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # OpenAI Configuration
    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o", alias="OPENAI_MODEL")

    # Image API Keys
    pexels_api_key: str = Field(..., alias="PEXELS_API_KEY")
    unsplash_access_key: str = Field(..., alias="UNSPLASH_ACCESS_KEY")

    # Google Sheets Configuration
    google_sheets_credentials_file: str = Field(
        ..., alias="GOOGLE_SHEETS_CREDENTIALS_FILE"
    )
    google_sheet_id: str = Field(..., alias="GOOGLE_SHEET_ID")

    # WordPress Sites
    wordpress_sites_json: str = Field(..., alias="WORDPRESS_SITES")

    # Notifications (Optional)
    telegram_bot_token: Optional[str] = Field(default=None, alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: Optional[str] = Field(default=None, alias="TELEGRAM_CHAT_ID")
    slack_webhook_url: Optional[str] = Field(default=None, alias="SLACK_WEBHOOK_URL")

    # Scheduling Configuration
    posts_per_week_per_site: int = Field(default=3, alias="POSTS_PER_WEEK_PER_SITE")
    posting_hours: str = Field(default="9,12,15", alias="POSTING_HOURS")

    # Content Configuration
    min_word_count: int = Field(default=800, alias="MIN_WORD_COUNT")
    max_word_count: int = Field(default=1000, alias="MAX_WORD_COUNT")
    enable_internal_linking: bool = Field(default=True, alias="ENABLE_INTERNAL_LINKING")
    min_internal_links: int = Field(default=1, alias="MIN_INTERNAL_LINKS")
    max_internal_links: int = Field(default=5, alias="MAX_INTERNAL_LINKS")

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_to_sheet: bool = Field(default=True, alias="LOG_TO_SHEET")

    model_config = SettingsConfigDict(
        env_file="config/.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra='ignore'
    )

    @field_validator('wordpress_sites_json')
    @classmethod
    def validate_wordpress_sites(cls, v: str) -> str:
        """Validate WordPress sites JSON format."""
        try:
            sites = json.loads(v)
            if not isinstance(sites, list):
                raise ValueError("WORDPRESS_SITES must be a JSON array")
            for site in sites:
                if not all(k in site for k in ['name', 'url', 'username', 'app_password']):
                    raise ValueError("Each site must have: name, url, username, app_password")
            return v
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in WORDPRESS_SITES: {e}")

    @property
    def wordpress_sites(self) -> List[WordPressSite]:
        """Parse WordPress sites from JSON string."""
        sites_data = json.loads(self.wordpress_sites_json)
        return [WordPressSite(**site) for site in sites_data]

    @property
    def posting_hours_list(self) -> List[int]:
        """Parse posting hours into list of integers."""
        return [int(h.strip()) for h in self.posting_hours.split(',')]


# Global settings instance
settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create settings singleton."""
    global settings
    if settings is None:
        settings = Settings()
    return settings
