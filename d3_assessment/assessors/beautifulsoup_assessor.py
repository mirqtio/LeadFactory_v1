"""
BeautifulSoup assessor for HTML content extraction
PRD v1.2 - Extract page structure as JSON

Timeout: 5s
Cost: Free (no external API)
Output: bsoup_json column
"""
import asyncio
import aiohttp
from typing import Dict, Any, Optional, List
from bs4 import BeautifulSoup
import json
from urllib.parse import urlparse

from d3_assessment.assessors.base import BaseAssessor, AssessmentResult
from d3_assessment.models import AssessmentType
from d3_assessment.exceptions import AssessmentError, AssessmentTimeoutError
from core.logging import get_logger

logger = get_logger(__name__, domain="d3")


class BeautifulSoupAssessor(BaseAssessor):
    """Extract page content and structure using BeautifulSoup"""

    def __init__(self):
        super().__init__()
        self.timeout = 5  # 5 second timeout as per PRD

    @property
    def assessment_type(self) -> AssessmentType:
        return AssessmentType.CONTENT_ANALYSIS

    async def assess(self, url: str, business_data: Dict[str, Any]) -> AssessmentResult:
        """
        Extract page content and structure

        Args:
            url: Website URL to analyze
            business_data: Business information

        Returns:
            AssessmentResult with bsoup_json data
        """
        try:
            # Fetch page content
            content = await self._fetch_page(url)

            if not content:
                return AssessmentResult(
                    assessment_type=self.assessment_type,
                    status="failed",
                    error_message="Failed to fetch page content",
                )

            # Parse with BeautifulSoup
            soup = BeautifulSoup(content, "html.parser")

            # Extract structured data
            extracted_data = {
                "title": self._extract_title(soup),
                "meta_description": self._extract_meta_description(soup),
                "headings": self._extract_headings(soup),
                "images": self._extract_images(soup, url),
                "links": self._extract_links(soup, url),
                "structured_data": self._extract_structured_data(soup),
                "contact_info": self._extract_contact_info(soup),
                "social_links": self._extract_social_links(soup),
                "text_stats": self._calculate_text_stats(soup),
                "forms": self._extract_forms(soup),
                "page_structure": self._analyze_page_structure(soup),
            }

            return AssessmentResult(
                assessment_type=self.assessment_type,
                status="completed",
                data={
                    "bsoup_json": extracted_data,
                    "url_analyzed": url,
                    "extraction_timestamp": asyncio.get_event_loop().time(),
                },
                metrics={
                    "page_size_bytes": len(content),
                    "extraction_time_ms": 0,  # Will be set by coordinator
                },
            )

        except asyncio.TimeoutError:
            raise AssessmentTimeoutError(
                f"BeautifulSoup extraction timed out after {self.timeout}s"
            )
        except Exception as e:
            logger.error(f"BeautifulSoup assessment failed for {url}: {e}")
            raise AssessmentError(f"BeautifulSoup extraction failed: {str(e)}")

    async def _fetch_page(self, url: str) -> Optional[str]:
        """Fetch page content with timeout"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                    headers={"User-Agent": "Mozilla/5.0 (compatible; LeadFactory/1.0)"},
                ) as response:
                    if response.status == 200:
                        return await response.text()
                    return None
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract page title"""
        title_tag = soup.find("title")
        return title_tag.text.strip() if title_tag else ""

    def _extract_meta_description(self, soup: BeautifulSoup) -> str:
        """Extract meta description"""
        meta = soup.find("meta", attrs={"name": "description"})
        if meta and meta.get("content"):
            return meta["content"].strip()
        return ""

    def _extract_headings(self, soup: BeautifulSoup) -> Dict[str, List[str]]:
        """Extract all headings by level"""
        headings = {}
        for i in range(1, 7):
            h_tags = soup.find_all(f"h{i}")
            if h_tags:
                headings[f"h{i}"] = [
                    tag.text.strip() for tag in h_tags if tag.text.strip()
                ]
        return headings

    def _extract_images(
        self, soup: BeautifulSoup, base_url: str
    ) -> List[Dict[str, str]]:
        """Extract image information"""
        images = []
        for img in soup.find_all("img")[:20]:  # Limit to 20 images
            img_data = {
                "src": self._make_absolute_url(img.get("src", ""), base_url),
                "alt": img.get("alt", ""),
                "title": img.get("title", ""),
            }
            if img_data["src"]:
                images.append(img_data)
        return images

    def _extract_links(
        self, soup: BeautifulSoup, base_url: str
    ) -> Dict[str, List[str]]:
        """Extract and categorize links"""
        internal_links = []
        external_links = []
        domain = urlparse(base_url).netloc

        for link in soup.find_all("a", href=True)[:50]:  # Limit to 50 links
            href = self._make_absolute_url(link["href"], base_url)
            if href:
                if domain in href:
                    internal_links.append(href)
                else:
                    external_links.append(href)

        return {
            "internal": list(set(internal_links))[:20],
            "external": list(set(external_links))[:10],
        }

    def _extract_structured_data(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract JSON-LD structured data"""
        structured_data = []
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                structured_data.append(data)
            except:
                pass
        return structured_data[:5]  # Limit to 5 items

    def _extract_contact_info(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract contact information from page"""
        contact = {}

        # Look for phone numbers
        phone_patterns = ["tel:", "phone", "call"]
        for pattern in phone_patterns:
            phone_elem = soup.find(attrs={"href": lambda x: x and pattern in x})
            if phone_elem:
                contact["phone"] = phone_elem.get("href", "").replace("tel:", "")
                break

        # Look for email
        email_elem = soup.find(attrs={"href": lambda x: x and "mailto:" in x})
        if email_elem:
            contact["email"] = email_elem.get("href", "").replace("mailto:", "")

        # Look for address
        address_elem = soup.find(attrs={"itemtype": "http://schema.org/PostalAddress"})
        if address_elem:
            contact["address"] = address_elem.text.strip()

        return contact

    def _extract_social_links(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract social media links"""
        social_patterns = {
            "facebook": "facebook.com",
            "twitter": "twitter.com",
            "instagram": "instagram.com",
            "linkedin": "linkedin.com",
            "youtube": "youtube.com",
        }

        social_links = {}
        for name, pattern in social_patterns.items():
            link = soup.find("a", href=lambda x: x and pattern in x)
            if link:
                social_links[name] = link.get("href", "")

        return social_links

    def _calculate_text_stats(self, soup: BeautifulSoup) -> Dict[str, int]:
        """Calculate text statistics"""
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()

        text = soup.get_text()
        words = text.split()

        return {
            "total_words": len(words),
            "unique_words": len(set(words)),
            "paragraphs": len(soup.find_all("p")),
            "lists": len(soup.find_all(["ul", "ol"])),
        }

    def _extract_forms(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract form information"""
        forms = []
        for form in soup.find_all("form")[:5]:  # Limit to 5 forms
            form_data = {
                "action": form.get("action", ""),
                "method": form.get("method", "get").upper(),
                "fields": [],
            }

            # Extract input fields
            for input_elem in form.find_all(["input", "textarea", "select"]):
                field = {
                    "type": input_elem.get("type", "text"),
                    "name": input_elem.get("name", ""),
                    "required": input_elem.has_attr("required"),
                }
                if field["name"]:
                    form_data["fields"].append(field)

            if form_data["fields"]:
                forms.append(form_data)

        return forms

    def _analyze_page_structure(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Analyze overall page structure"""
        return {
            "has_header": bool(soup.find(["header", "nav"])),
            "has_footer": bool(soup.find("footer")),
            "has_sidebar": bool(soup.find(["aside", ".sidebar", "#sidebar"])),
            "has_hero": bool(soup.find([".hero", "#hero", "section.hero"])),
            "has_cta": bool(
                soup.find_all(
                    text=lambda t: t and "call" in t.lower() and "action" in t.lower()
                )
            ),
            "uses_bootstrap": bool(
                soup.find(attrs={"class": lambda x: x and "container" in x})
            ),
            "uses_wordpress": bool(
                soup.find(attrs={"class": lambda x: x and "wp-" in x})
            ),
        }

    def _make_absolute_url(self, url: str, base_url: str) -> str:
        """Convert relative URLs to absolute"""
        if not url:
            return ""
        if url.startswith(("http://", "https://", "//")):
            return url
        if url.startswith("/"):
            parsed_base = urlparse(base_url)
            return f"{parsed_base.scheme}://{parsed_base.netloc}{url}"
        return ""

    def calculate_cost(self) -> float:
        """BeautifulSoup extraction is free"""
        return 0.0
