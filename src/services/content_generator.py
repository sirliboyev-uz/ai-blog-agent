"""OpenAI-powered content generation service."""

import re
from typing import List, Optional
from openai import OpenAI
from loguru import logger

from src.models.blog_post import BlogTopic, SEOMetadata, GeneratedContent
from src.models.config import get_settings


class ContentGenerator:
    """AI content generator using OpenAI Agent SDK."""

    def __init__(self):
        """Initialize OpenAI client."""
        self.settings = get_settings()
        self.client = OpenAI(api_key=self.settings.openai_api_key)
        self.model = self.settings.openai_model

    def generate_seo_metadata(self, topic: BlogTopic) -> SEOMetadata:
        """Generate SEO-optimized metadata."""
        prompt = f"""Generate SEO metadata for a blog post about "{topic.topic}" for a {topic.business_type} in {topic.location}.

Return ONLY a JSON object with this exact structure (no markdown, no explanation):
{{
  "title": "compelling H1 title (max 60 chars)",
  "meta_title": "SEO meta title (max 60 chars)",
  "meta_description": "engaging meta description (max 155 chars)",
  "slug": "url-friendly-slug",
  "keywords": ["keyword1", "keyword2", "keyword3"]
}}

Requirements:
- Title must include the main topic and location
- Meta description must be compelling and include a call-to-action
- Slug should be lowercase with hyphens
- Include 3-5 relevant keywords"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an SEO expert. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            response_format={"type": "json_object"}
        )

        metadata_json = response.choices[0].message.content
        logger.debug(f"Generated SEO metadata: {metadata_json}")

        import json
        metadata = json.loads(metadata_json)
        return SEOMetadata(**metadata)

    def generate_blog_content(
        self,
        topic: BlogTopic,
        seo: SEOMetadata,
        existing_posts_context: Optional[str] = None
    ) -> GeneratedContent:
        """Generate complete blog post content with intelligent linking."""

        # Prepare internal links context
        internal_links_context = ""
        if topic.internal_links and self.settings.enable_internal_linking:
            links_list = "\n".join([f"- {link}" for link in topic.internal_links])
            internal_links_context = f"""
Internal links to use ({self.settings.min_internal_links}-{self.settings.max_internal_links} links, naturally placed):
{links_list}

Place these links ONLY where contextually relevant. Use descriptive anchor text, not "click here".
"""

        # Build comprehensive prompt
        prompt = f"""Write a professional, SEO-optimized blog post for:

**Topic**: {topic.topic}
**Business**: {topic.business_type} in {topic.location}
**Target Length**: {self.settings.min_word_count}-{self.settings.max_word_count} words
**SEO Title**: {seo.title}

{internal_links_context}

**Requirements**:
1. Write {self.settings.min_word_count}-{self.settings.max_word_count} words of engaging, informative content
2. Use HTML formatting: <h2> for main sections, <h3> for subsections, <p> for paragraphs
3. Include 2-3 <h2> headings that break up the content logically
4. Add {self.settings.min_internal_links}-{self.settings.max_internal_links} internal links naturally in context (use provided URLs)
5. Include ONE outbound link to a reputable authority website (Wikipedia, .edu, industry leader)
6. Write in a professional, helpful tone
7. Focus on providing value to readers in {topic.location}
8. Include local context and specifics about {topic.location} where relevant
9. Use the main topic "{topic.topic}" naturally throughout (avoid keyword stuffing)
10. Format links as: <a href="URL">descriptive anchor text</a>

**Structure**:
- Opening paragraph: Hook the reader, establish context
- 2-3 main sections with <h2> headings
- Closing paragraph: Summary and call-to-action
- Natural internal linking throughout (NOT in a "Resources" section)

Return ONLY the HTML content (no title, no meta tags, just the article body).
"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert content writer specializing in SEO and local business marketing. Write engaging, informative blog posts that provide real value."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
        )

        html_content = response.choices[0].message.content.strip()

        # Extract metadata from content
        word_count = len(re.findall(r'\w+', re.sub(r'<[^>]+>', '', html_content)))
        headings = re.findall(r'<h[23]>(.*?)</h[23]>', html_content)

        # Extract links
        internal_links_used = []
        outbound_link = None

        for link in re.findall(r'<a\s+href=["\'](.*?)["\']', html_content):
            if any(internal in link for internal in topic.internal_links):
                internal_links_used.append(link)
            elif not any(domain in link for domain in [topic.site_domain]):
                outbound_link = link

        logger.info(
            f"Generated content: {word_count} words, "
            f"{len(headings)} headings, "
            f"{len(internal_links_used)} internal links"
        )

        return GeneratedContent(
            html_content=html_content,
            word_count=word_count,
            headings=headings,
            internal_links_used=internal_links_used,
            outbound_link=outbound_link
        )

    def generate_alt_text(self, topic: BlogTopic) -> str:
        """Generate descriptive alt text for images."""
        prompt = f"""Generate a concise, descriptive alt text (max 125 characters) for a featured image for a blog post about "{topic.topic}" for a {topic.business_type} in {topic.location}.

The alt text should be:
- Descriptive and specific
- Include relevant keywords naturally
- Be useful for visually impaired users
- Not start with "image of" or "picture of"

Return ONLY the alt text, nothing else."""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an accessibility expert."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=50
        )

        alt_text = response.choices[0].message.content.strip().strip('"\'')
        logger.debug(f"Generated alt text: {alt_text}")

        return alt_text[:125]  # Enforce max length

    def generate_categories_and_tags(self, topic: BlogTopic, content: GeneratedContent) -> tuple[List[str], List[str]]:
        """Generate relevant categories and tags for WordPress."""
        prompt = f"""Based on this blog post topic and content, suggest WordPress categories and tags.

Topic: {topic.topic}
Business: {topic.business_type}
Location: {topic.location}
Headings: {', '.join(content.headings[:3])}

Return ONLY a JSON object with this structure:
{{
  "categories": ["Category 1", "Category 2"],
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"]
}}

Requirements:
- 1-2 broad categories (e.g., "Local Business", "Services", industry name)
- 5-8 specific tags (keywords, topics, location-based)"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a WordPress taxonomy expert. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            response_format={"type": "json_object"}
        )

        import json
        taxonomy = json.loads(response.choices[0].message.content)

        return taxonomy.get("categories", []), taxonomy.get("tags", [])
