"""Image acquisition service with waterfall fallback (Pexels → Unsplash → DALL-E)."""

import requests
from typing import Optional
from loguru import logger
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from src.models.blog_post import BlogTopic, ImageMetadata
from src.models.config import get_settings


class ImageHandler:
    """Handles image acquisition with waterfall fallback system."""

    def __init__(self):
        """Initialize API clients."""
        self.settings = get_settings()
        self.openai_client = OpenAI(api_key=self.settings.openai_api_key)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def get_image_for_topic(self, topic: BlogTopic, alt_text: str) -> Optional[ImageMetadata]:
        """
        Get image using waterfall approach: Pexels → Unsplash → DALL-E.

        Args:
            topic: Blog topic
            alt_text: Pre-generated alt text for the image

        Returns:
            ImageMetadata if successful, None otherwise
        """
        logger.info(f"Searching for image: {topic.topic}")

        # Try Pexels first
        image = self._try_pexels(topic.topic)
        if image:
            image.alt_text = alt_text
            return image

        # Fallback to Unsplash
        image = self._try_unsplash(topic.topic)
        if image:
            image.alt_text = alt_text
            return image

        # Final fallback to DALL-E
        logger.warning("Stock photos failed, generating with DALL-E")
        image = self._generate_dalle(topic, alt_text)
        return image

    def _try_pexels(self, query: str) -> Optional[ImageMetadata]:
        """Try to get image from Pexels API."""
        try:
            headers = {"Authorization": self.settings.pexels_api_key}
            params = {
                "query": query,
                "per_page": 1,
                "orientation": "landscape"
            }

            response = requests.get(
                "https://api.pexels.com/v1/search",
                headers=headers,
                params=params,
                timeout=10
            )
            response.raise_for_status()

            data = response.json()
            if data.get("photos") and len(data["photos"]) > 0:
                photo = data["photos"][0]
                logger.info(f"Found Pexels image: {photo['url']}")

                return ImageMetadata(
                    url=photo["src"]["large"],
                    source="pexels",
                    alt_text="",  # Will be set by caller
                    photographer=photo.get("photographer"),
                    photographer_url=photo.get("photographer_url")
                )

        except Exception as e:
            logger.warning(f"Pexels API failed: {e}")

        return None

    def _try_unsplash(self, query: str) -> Optional[ImageMetadata]:
        """Try to get image from Unsplash API."""
        try:
            headers = {"Authorization": f"Client-ID {self.settings.unsplash_access_key}"}
            params = {
                "query": query,
                "per_page": 1,
                "orientation": "landscape"
            }

            response = requests.get(
                "https://api.unsplash.com/search/photos",
                headers=headers,
                params=params,
                timeout=10
            )
            response.raise_for_status()

            data = response.json()
            if data.get("results") and len(data["results"]) > 0:
                photo = data["results"][0]
                logger.info(f"Found Unsplash image: {photo['urls']['regular']}")

                return ImageMetadata(
                    url=photo["urls"]["regular"],
                    source="unsplash",
                    alt_text="",  # Will be set by caller
                    photographer=photo["user"].get("name"),
                    photographer_url=photo["user"].get("links", {}).get("html")
                )

        except Exception as e:
            logger.warning(f"Unsplash API failed: {e}")

        return None

    def _generate_dalle(self, topic: BlogTopic, alt_text: str) -> Optional[ImageMetadata]:
        """Generate image using DALL-E 3."""
        try:
            # Create descriptive prompt for DALL-E
            prompt = f"""Professional, high-quality photograph for a blog about {topic.topic} for a {topic.business_type} in {topic.location}.

Style: Clean, modern, professional photography
Mood: Trustworthy and welcoming
Lighting: Natural, well-lit
Composition: Landscape orientation, suitable for blog featured image

{alt_text}

No text, no people's faces, no logos."""

            logger.info("Generating DALL-E 3 image...")

            response = self.openai_client.images.generate(
                model="dall-e-3",
                prompt=prompt[:1000],  # DALL-E 3 prompt limit
                size="1792x1024",  # Landscape format
                quality="standard",  # Use "hd" for higher quality but more cost
                n=1,
            )

            image_url = response.data[0].url
            logger.info(f"Generated DALL-E image: {image_url}")

            return ImageMetadata(
                url=image_url,
                source="dalle",
                alt_text=alt_text,
                photographer="AI Generated",
                photographer_url=None
            )

        except Exception as e:
            logger.error(f"DALL-E generation failed: {e}")
            return None

    def download_and_prepare(self, image: ImageMetadata) -> Optional[bytes]:
        """
        Download image and prepare for WordPress upload.

        Args:
            image: Image metadata with URL

        Returns:
            Image bytes if successful, None otherwise
        """
        try:
            response = requests.get(image.url, timeout=30)
            response.raise_for_status()

            logger.info(f"Downloaded image: {len(response.content)} bytes")
            return response.content

        except Exception as e:
            logger.error(f"Failed to download image: {e}")
            return None
