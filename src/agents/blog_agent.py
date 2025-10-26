"""Main Blog Agent orchestrating the entire content generation and publishing workflow."""

from typing import Optional
from loguru import logger

from src.models.blog_post import BlogTopic, BlogPost, PostLog, ImageMetadata
from src.models.config import get_settings, WordPressSite
from src.services.content_generator import ContentGenerator
from src.services.image_handler import ImageHandler
from src.services.wordpress_client import WordPressClient
from src.services.sheets_client import SheetsClient


class BlogAgent:
    """
    Main orchestration agent for automated blog posting.

    This agent coordinates:
    1. Content generation (OpenAI)
    2. Image acquisition (Pexels → Unsplash → DALL-E)
    3. WordPress publishing
    4. Logging and tracking
    """

    def __init__(self):
        """Initialize the blog agent with all required services."""
        self.settings = get_settings()
        self.content_generator = ContentGenerator()
        self.image_handler = ImageHandler()
        self.sheets_client = SheetsClient()

        logger.info("Blog Agent initialized")

    def process_topic(
        self,
        topic: BlogTopic,
        site: WordPressSite,
        status: str = "publish"
    ) -> bool:
        """
        Process a single topic: generate content, get image, publish to WordPress.

        Args:
            topic: Blog topic to process
            site: Target WordPress site
            status: Post status (draft/publish)

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Processing topic: {topic.topic} for {site.name}")

        try:
            # Mark as processing
            self.sheets_client.mark_topic_status(topic.row_number, "Processing")

            # Step 1: Generate SEO metadata
            logger.info("Generating SEO metadata...")
            seo_metadata = self.content_generator.generate_seo_metadata(topic)

            # Step 2: Generate blog content
            logger.info("Generating blog content...")
            content = self.content_generator.generate_blog_content(topic, seo_metadata)

            # Step 3: Generate categories and tags
            logger.info("Generating categories and tags...")
            categories, tags = self.content_generator.generate_categories_and_tags(topic, content)

            # Step 4: Get featured image
            logger.info("Acquiring featured image...")
            alt_text = self.content_generator.generate_alt_text(topic)
            image_metadata = self.image_handler.get_image_for_topic(topic, alt_text)

            image_data = None
            if image_metadata:
                image_data = self.image_handler.download_and_prepare(image_metadata)

            # Step 5: Create BlogPost object
            blog_post = BlogPost(
                topic=topic,
                seo=seo_metadata,
                content=content,
                image=image_metadata,
                categories=categories,
                tags=tags,
                status=status
            )

            # Step 6: Publish to WordPress
            logger.info(f"Publishing to WordPress: {site.name}")
            wp_client = WordPressClient(site)

            if not wp_client.test_connection():
                raise Exception("WordPress connection failed")

            post_result = wp_client.create_post(blog_post, image_data)

            if not post_result:
                raise Exception("WordPress post creation failed")

            # Extract post URL
            post_url = post_result.get("link")
            post_id = post_result.get("id")

            logger.info(f"Successfully published: {post_url}")

            # Step 7: Update blog post with WordPress data
            blog_post.wordpress_post_id = post_id
            blog_post.wordpress_url = post_url

            # Step 8: Log success
            self.sheets_client.mark_topic_status(
                topic.row_number,
                "Completed",
                post_url
            )

            post_log = PostLog(
                site=site.name,
                post_title=seo_metadata.title,
                post_url=post_url,
                status="Success",
                word_count=content.word_count,
                topic=topic.topic
            )
            self.sheets_client.log_post_result(post_log)

            logger.success(f"✅ Post published successfully: {post_url}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to process topic: {e}")

            # Log failure
            self.sheets_client.mark_topic_status(topic.row_number, "Failed")

            post_log = PostLog(
                site=site.name,
                post_title=topic.topic,
                post_url=None,
                status="Failed",
                word_count=0,
                topic=topic.topic,
                error_message=str(e)
            )
            self.sheets_client.log_post_result(post_log)

            return False

    def process_batch(self, limit: Optional[int] = None) -> dict:
        """
        Process batch of pending topics from Google Sheets.

        Args:
            limit: Maximum number of topics to process

        Returns:
            Statistics dict with success/failure counts
        """
        logger.info("Starting batch processing...")

        # Get pending topics
        topics = self.sheets_client.get_pending_topics(limit=limit)

        if not topics:
            logger.info("No pending topics found")
            return {"success": 0, "failed": 0, "total": 0}

        # Process each topic
        stats = {"success": 0, "failed": 0, "total": len(topics)}

        for topic in topics:
            # Find matching WordPress site
            site = self._find_site_for_domain(topic.site_domain)

            if not site:
                logger.error(f"No WordPress site configured for domain: {topic.site_domain}")
                stats["failed"] += 1
                continue

            # Process topic
            success = self.process_topic(topic, site, status="publish")

            if success:
                stats["success"] += 1
            else:
                stats["failed"] += 1

        logger.info(
            f"Batch processing complete: {stats['success']} success, "
            f"{stats['failed']} failed, {stats['total']} total"
        )

        return stats

    def _find_site_for_domain(self, domain: str) -> Optional[WordPressSite]:
        """Find WordPress site configuration matching domain."""
        for site in self.settings.wordpress_sites:
            if domain.lower() in site.url.lower():
                return site
        return None

    def generate_demo_post(self, demo_topic: Optional[dict] = None) -> bool:
        """
        Generate a demo post for testing (doesn't publish to WordPress).

        Args:
            demo_topic: Custom topic dict or None for default demo

        Returns:
            True if generation successful
        """
        if demo_topic is None:
            demo_topic = {
                "Topic": "Best Coffee Shops",
                "Business Type": "Coffee Shop",
                "Location": "San Francisco",
                "Internal Link URLs": "https://example.com/about,https://example.com/contact",
                "Site Domain": "example.com"
            }

        topic = BlogTopic.from_sheet_row(demo_topic, row_number=0)

        logger.info("Generating demo content (not publishing)...")

        try:
            # Generate all content
            seo = self.content_generator.generate_seo_metadata(topic)
            content = self.content_generator.generate_blog_content(topic, seo)
            categories, tags = self.content_generator.generate_categories_and_tags(topic, content)
            alt_text = self.content_generator.generate_alt_text(topic)

            # Display results
            logger.info("\n" + "="*60)
            logger.info("DEMO POST GENERATED")
            logger.info("="*60)
            logger.info(f"\nSEO Title: {seo.title}")
            logger.info(f"Meta Description: {seo.meta_description}")
            logger.info(f"Slug: {seo.slug}")
            logger.info(f"Word Count: {content.word_count}")
            logger.info(f"Headings: {', '.join(content.headings[:3])}")
            logger.info(f"Internal Links: {len(content.internal_links_used)}")
            logger.info(f"Categories: {', '.join(categories)}")
            logger.info(f"Tags: {', '.join(tags)}")
            logger.info(f"Alt Text: {alt_text}")
            logger.info("\nContent Preview (first 500 chars):")
            logger.info(content.html_content[:500] + "...")
            logger.info("="*60 + "\n")

            return True

        except Exception as e:
            logger.error(f"Demo generation failed: {e}")
            return False
