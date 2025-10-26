"""Blog post data models."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, HttpUrl


class BlogTopic(BaseModel):
    """Input topic from Google Sheets."""

    topic: str = Field(..., description="Blog post topic/keyword")
    business_type: str = Field(..., description="Type of business")
    location: str = Field(..., description="Business location")
    internal_links: List[str] = Field(
        default_factory=list,
        description="Comma-separated internal link URLs"
    )
    site_domain: str = Field(..., description="Target WordPress site domain")
    row_number: int = Field(..., description="Row number in Google Sheets")

    @classmethod
    def from_sheet_row(cls, row: dict, row_number: int) -> "BlogTopic":
        """Create BlogTopic from Google Sheets row."""
        internal_links_str = row.get("Internal Link URLs", "")
        internal_links = [
            link.strip()
            for link in internal_links_str.split(",")
            if link.strip()
        ]

        return cls(
            topic=row.get("Topic", ""),
            business_type=row.get("Business Type", ""),
            location=row.get("Location", ""),
            internal_links=internal_links,
            site_domain=row.get("Site Domain", ""),
            row_number=row_number
        )


class SEOMetadata(BaseModel):
    """SEO metadata for blog post."""

    title: str = Field(..., max_length=60, description="SEO title (H1)")
    meta_title: str = Field(..., max_length=60, description="Meta title tag")
    meta_description: str = Field(..., max_length=155, description="Meta description")
    slug: str = Field(..., description="URL slug")
    keywords: List[str] = Field(default_factory=list, description="Focus keywords")


class GeneratedContent(BaseModel):
    """AI-generated blog content."""

    html_content: str = Field(..., description="HTML formatted blog post")
    word_count: int = Field(..., description="Total word count")
    headings: List[str] = Field(default_factory=list, description="H2/H3 headings used")
    internal_links_used: List[str] = Field(
        default_factory=list,
        description="Internal links inserted"
    )
    outbound_link: Optional[str] = Field(None, description="Authority outbound link")


class ImageMetadata(BaseModel):
    """Featured image metadata."""

    url: str = Field(..., description="Image URL")
    source: str = Field(..., description="Image source (pexels/unsplash/dalle)")
    alt_text: str = Field(..., description="Alt text for accessibility")
    photographer: Optional[str] = Field(None, description="Photographer name")
    photographer_url: Optional[str] = Field(None, description="Photographer profile URL")


class BlogPost(BaseModel):
    """Complete blog post ready for WordPress."""

    # Source information
    topic: BlogTopic = Field(..., description="Original topic data")

    # Generated content
    seo: SEOMetadata = Field(..., description="SEO metadata")
    content: GeneratedContent = Field(..., description="Blog content")
    image: Optional[ImageMetadata] = Field(None, description="Featured image")

    # WordPress metadata
    categories: List[str] = Field(default_factory=list, description="Post categories")
    tags: List[str] = Field(default_factory=list, description="Post tags")
    status: str = Field(default="draft", description="Post status (draft/publish)")

    # Tracking
    created_at: datetime = Field(default_factory=datetime.utcnow)
    wordpress_post_id: Optional[int] = Field(None, description="WordPress post ID")
    wordpress_url: Optional[str] = Field(None, description="Published post URL")

    def to_wordpress_payload(self) -> dict:
        """Convert to WordPress REST API payload."""
        payload = {
            "title": self.seo.title,
            "content": self.content.html_content,
            "status": self.status,
            "slug": self.seo.slug,
            "excerpt": self.seo.meta_description,
            "meta": {
                "description": self.seo.meta_description,
            },
            "categories": self.categories,
            "tags": self.tags,
        }

        # Add featured image if available
        if self.image and hasattr(self, 'featured_media_id'):
            payload["featured_media"] = self.featured_media_id

        return payload


class PostLog(BaseModel):
    """Logging entry for Google Sheets."""

    site: str = Field(..., description="Site name")
    post_title: str = Field(..., description="Post title")
    post_url: Optional[str] = Field(None, description="Published URL")
    status: str = Field(..., description="Success/Failed/Pending")
    date: datetime = Field(default_factory=datetime.utcnow)
    error_message: Optional[str] = Field(None, description="Error details if failed")
    word_count: int = Field(..., description="Word count")
    topic: str = Field(..., description="Original topic")

    def to_sheet_row(self) -> List[str]:
        """Convert to Google Sheets row format."""
        return [
            self.date.strftime("%Y-%m-%d %H:%M:%S"),
            self.site,
            self.topic,
            self.post_title,
            self.post_url or "N/A",
            str(self.word_count),
            self.status,
            self.error_message or ""
        ]
