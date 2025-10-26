"""WordPress REST API client for publishing posts."""

import base64
from typing import Optional, List, Dict
import requests
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from src.models.blog_post import BlogPost, ImageMetadata
from src.models.config import WordPressSite


class WordPressClient:
    """WordPress REST API client for post management."""

    def __init__(self, site: WordPressSite):
        """
        Initialize WordPress client for a specific site.

        Args:
            site: WordPress site configuration
        """
        self.site = site
        self.base_url = site.url.rstrip('/') + '/wp-json/wp/v2'

        # Create basic auth header
        credentials = f"{site.username}:{site.app_password}"
        token = base64.b64encode(credentials.encode()).decode()
        self.headers = {
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json"
        }

    def test_connection(self) -> bool:
        """
        Test WordPress connection and authentication.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            response = requests.get(
                f"{self.base_url}/users/me",
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()

            user_data = response.json()
            logger.info(f"Connected to {self.site.name} as {user_data.get('name')}")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"WordPress connection failed for {self.site.name}: {e}")
            return False

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def upload_featured_image(
        self,
        image_data: bytes,
        image_metadata: ImageMetadata
    ) -> Optional[int]:
        """
        Upload featured image to WordPress media library.

        Args:
            image_data: Image file bytes
            image_metadata: Image metadata including alt text

        Returns:
            Media ID if successful, None otherwise
        """
        try:
            # Determine file extension from source or URL
            ext = "jpg"
            if "png" in image_metadata.url.lower():
                ext = "png"

            filename = f"featured-image-{hash(image_metadata.url)}.{ext}"

            # Prepare headers for media upload
            upload_headers = {
                "Authorization": self.headers["Authorization"],
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Type": f"image/{ext}"
            }

            # Upload image
            response = requests.post(
                f"{self.base_url}/media",
                headers=upload_headers,
                data=image_data,
                timeout=30
            )
            response.raise_for_status()

            media_data = response.json()
            media_id = media_data.get("id")

            # Update alt text
            if media_id:
                alt_text_payload = {"alt_text": image_metadata.alt_text}
                requests.post(
                    f"{self.base_url}/media/{media_id}",
                    headers=self.headers,
                    json=alt_text_payload,
                    timeout=10
                )

            logger.info(f"Uploaded image: media ID {media_id}")
            return media_id

        except Exception as e:
            logger.error(f"Failed to upload image: {e}")
            return None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def create_post(self, blog_post: BlogPost, image_data: Optional[bytes] = None) -> Optional[dict]:
        """
        Create WordPress post with content and featured image.

        Args:
            blog_post: Complete blog post data
            image_data: Featured image bytes (optional)

        Returns:
            WordPress post data if successful, None otherwise
        """
        try:
            # Upload featured image first
            featured_media_id = None
            if image_data and blog_post.image:
                featured_media_id = self.upload_featured_image(
                    image_data,
                    blog_post.image
                )

            # Prepare post payload
            payload = {
                "title": blog_post.seo.title,
                "content": blog_post.content.html_content,
                "status": blog_post.status,
                "slug": blog_post.seo.slug,
                "excerpt": blog_post.seo.meta_description,
            }

            # Add featured image if uploaded
            if featured_media_id:
                payload["featured_media"] = featured_media_id

            # Add categories (create if they don't exist)
            if blog_post.categories:
                category_ids = self._get_or_create_categories(blog_post.categories)
                payload["categories"] = category_ids

            # Add tags (create if they don't exist)
            if blog_post.tags:
                tag_ids = self._get_or_create_tags(blog_post.tags)
                payload["tags"] = tag_ids

            # Add Yoast SEO meta if available
            payload["meta"] = {
                "description": blog_post.seo.meta_description,
            }

            # Try to add Yoast-specific fields (will be ignored if Yoast not installed)
            try:
                payload["yoast_meta"] = {
                    "yoast_wpseo_title": blog_post.seo.meta_title,
                    "yoast_wpseo_metadesc": blog_post.seo.meta_description,
                }
            except:
                pass

            # Create post
            response = requests.post(
                f"{self.base_url}/posts",
                headers=self.headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()

            post_data = response.json()
            logger.info(
                f"Created post: {post_data.get('title', {}).get('rendered')} "
                f"(ID: {post_data.get('id')})"
            )

            return post_data

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to create WordPress post: {e}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response: {e.response.text}")
            return None

    def _get_or_create_categories(self, category_names: List[str]) -> List[int]:
        """Get or create categories and return their IDs."""
        category_ids = []

        for name in category_names:
            try:
                # Search for existing category
                response = requests.get(
                    f"{self.base_url}/categories",
                    headers=self.headers,
                    params={"search": name},
                    timeout=10
                )

                categories = response.json()

                if categories:
                    category_ids.append(categories[0]["id"])
                else:
                    # Create new category
                    create_response = requests.post(
                        f"{self.base_url}/categories",
                        headers=self.headers,
                        json={"name": name},
                        timeout=10
                    )
                    category_data = create_response.json()
                    category_ids.append(category_data["id"])
                    logger.info(f"Created category: {name}")

            except Exception as e:
                logger.warning(f"Failed to process category {name}: {e}")
                continue

        return category_ids

    def _get_or_create_tags(self, tag_names: List[str]) -> List[int]:
        """Get or create tags and return their IDs."""
        tag_ids = []

        for name in tag_names:
            try:
                # Search for existing tag
                response = requests.get(
                    f"{self.base_url}/tags",
                    headers=self.headers,
                    params={"search": name},
                    timeout=10
                )

                tags = response.json()

                if tags:
                    tag_ids.append(tags[0]["id"])
                else:
                    # Create new tag
                    create_response = requests.post(
                        f"{self.base_url}/tags",
                        headers=self.headers,
                        json={"name": name},
                        timeout=10
                    )
                    tag_data = create_response.json()
                    tag_ids.append(tag_data["id"])
                    logger.info(f"Created tag: {name}")

            except Exception as e:
                logger.warning(f"Failed to process tag {name}: {e}")
                continue

        return tag_ids

    def get_recent_posts(self, limit: int = 10) -> List[Dict]:
        """
        Get recent posts for internal linking analysis.

        Args:
            limit: Number of recent posts to retrieve

        Returns:
            List of post data dictionaries
        """
        try:
            response = requests.get(
                f"{self.base_url}/posts",
                headers=self.headers,
                params={"per_page": limit, "orderby": "date", "order": "desc"},
                timeout=15
            )
            response.raise_for_status()

            posts = response.json()
            logger.debug(f"Retrieved {len(posts)} recent posts")

            return posts

        except Exception as e:
            logger.error(f"Failed to get recent posts: {e}")
            return []
