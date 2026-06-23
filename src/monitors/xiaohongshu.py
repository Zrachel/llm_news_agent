"""LLM News Agent - Xiaohongshu (Little Red Book) monitor.

Uses Playwright to scrape search results from the web UI since the
API endpoints (edith.xiaohongshu.com) are no longer available.
"""

import asyncio
import re
from datetime import datetime
from typing import Any
from urllib.parse import quote_plus

from playwright.sync_api import Browser, Page, sync_playwright

from src.monitors.base import BaseMonitor, NewsItem
from src.utils.logging import get_logger

logger = get_logger("monitors.xiaohongshu")

# Search base URL
SEARCH_URL = "https://www.xiaohongshu.com/search_result"

# CSS selectors for note cards (try multiple, page structure may change)
NOTE_CARD_SELECTORS = [
    "section.note-item",
    "div[class*='note-item']",
    "div[class*='search-result-card']",
    "a[href*='/explore/']",
]

# Selectors for extracting note data from a card element
TITLE_SELECTORS = [
    "span[class*='title']",
    "div[class*='title']",
    "span.note-text",
    "div[class*='desc']",
    "span[class*='content']",
]

USER_SELECTORS = [
    "span[class*='author']",
    "div[class*='author']",
    "span[class*='nickname']",
    "a[class*='author']",
    "div[class*='name']",
]

LIKE_SELECTORS = [
    "span[class*='like']",
    "div[class*='like']",
    "span[class*='count']",
    "span[class*='engage']",
]


def _parse_cookie(cookie: str | None) -> dict[str, str]:
    """Parse cookie string into dict. Supports both full cookie string and single value."""
    if not cookie:
        return {}
    cookie = cookie.strip()
    # If it looks like a full cookie string (contains = and ;)
    if ";" in cookie or "=" in cookie:
        result = {}
        for part in cookie.split(";"):
            part = part.strip()
            if "=" in part:
                k, v = part.split("=", 1)
                result[k.strip()] = v.strip()
        return result
    # Otherwise treat as web_session value
    return {"web_session": cookie}


def _extract_note_id(href: str) -> str | None:
    """Extract note ID from a URL like /explore/abc123xyz or full URL."""
    match = re.search(r"/explore/([a-zA-Z0-9]+)", href)
    if match:
        return match.group(1)
    # Try ID from data attributes
    match = re.search(r'data-note-id="([a-zA-Z0-9]+)"', href)
    if match:
        return match.group(1)
    return None


def _extract_text(el, selectors: list[str]) -> str:
    """Try multiple selectors to extract text from an element."""
    for sel in selectors:
        try:
            child = el.query_selector(sel)
            if child:
                text = child.inner_text().strip()
                if text:
                    return text
        except Exception:
            continue
    return ""


def _extract_notes_from_page(page: Page) -> list[dict[str, Any]]:
    """Parse note data from the search results page DOM."""
    notes = []
    seen_ids = set()

    # Strategy 1: Find all explore links, then find their parent cards
    explore_links = page.query_selector_all("a[href*='/explore/']")
    for link in explore_links:
        try:
            href = link.get_attribute("href") or ""
            note_id = _extract_note_id(href)
            if not note_id or note_id in seen_ids:
                continue
            seen_ids.add(note_id)

            # Find the card container (parent that holds all info)
            card = link
            for _ in range(6):  # Walk up to find card container
                card = card.evaluate_handle("el => el.parentElement")
                card_el = card.as_element()
                if card_el and (
                    card_el.get_attribute("class") and
                    "note" in card_el.get_attribute("class") or
                    card_el.get_attribute("class") and
                    "card" in card_el.get_attribute("class") or
                    card_el.get_attribute("class") and
                    "item" in card_el.get_attribute("class")
                ):
                    break

            # Extract title - try from card, fallback to link text
            title = ""
            if card_el:
                title = _extract_text(card_el, TITLE_SELECTORS)
            if not title:
                title = link.inner_text().strip()[:100]

            # Extract author
            author = ""
            if card_el:
                author = _extract_text(card_el, USER_SELECTORS)

            # Extract likes
            likes = 0
            if card_el:
                like_text = _extract_text(card_el, LIKE_SELECTORS)
                likes = _parse_count(like_text)

            # Extract description from meta tags or card
            desc = ""
            if card_el:
                desc_elem = card_el.query_selector(
                    "span[class*='desc'], div[class*='desc'], span[class*='summary']"
                )
                if desc_elem:
                    desc = desc_elem.inner_text().strip()

            notes.append({
                "id": note_id,
                "title": title,
                "desc": desc,
                "user": author,
                "likes": likes,
                "type": "",
            })
        except Exception:
            continue

    # Strategy 2: If no notes found via links, try section-based parsing
    if not notes:
        for selector in NOTE_CARD_SELECTORS:
            try:
                cards = page.query_selector_all(selector)
                if cards and len(cards) > 0:
                    for card in cards[:20]:  # Limit to 20
                        try:
                            link = card.query_selector("a[href*='/explore/']")
                            if not link:
                                continue
                            href = link.get_attribute("href") or ""
                            note_id = _extract_note_id(href)
                            if not note_id or note_id in seen_ids:
                                continue
                            seen_ids.add(note_id)

                            title = card.inner_text().strip()[:100]
                            # First line is usually title
                            first_line = title.split("\n")[0] if "\n" in title else title

                            notes.append({
                                "id": note_id,
                                "title": first_line,
                                "desc": title,
                                "user": "",
                                "likes": 0,
                                "type": "",
                            })
                        except Exception:
                            continue
                    if notes:
                        break
            except Exception:
                continue

    # Strategy 3: Try to extract from embedded JSON data in page
    if not notes:
        try:
            page_content = page.content()
            # Look for note data in script tags
            json_matches = re.findall(r'"noteId"\s*:\s*"([a-zA-Z0-9]+)"', page_content)
            title_matches = re.findall(r'"title"\s*:\s*"([^"]{5,100})"', page_content)
            user_matches = re.findall(r'"nickname"\s*:\s*"([^"]+)"', page_content)

            for i, nid in enumerate(json_matches[:10]):
                if nid in seen_ids:
                    continue
                seen_ids.add(nid)
                notes.append({
                    "id": nid,
                    "title": title_matches[i] if i < len(title_matches) else f"笔记 {nid}",
                    "desc": "",
                    "user": user_matches[i] if i < len(user_matches) else "",
                    "likes": 0,
                    "type": "",
                })
        except Exception:
            pass

    return notes


def _parse_count(text: str) -> int:
    """Parse a count string like '1.2万' or '3.5k' into integer."""
    if not text:
        return 0
    text = text.strip().replace(",", "")
    try:
        if "万" in text:
            num = float(re.search(r"[\d.]+", text).group())
            return int(num * 10000)
        if "k" in text.lower():
            num = float(re.search(r"[\d.]+", text).group())
            return int(num * 1000)
        if "w" in text.lower():
            num = float(re.search(r"[\d.]+", text).group())
            return int(num * 10000)
        return int(re.search(r"[\d]+", text).group())
    except (ValueError, AttributeError, IndexError):
        return 0


def _scrape_with_playwright(
    cookie_dict: dict[str, str],
    keywords: list[str],
    limit_per_keyword: int,
) -> list[dict[str, Any]]:
    """Run Playwright scraping synchronously. Called from thread pool."""
    notes = []
    browser: Browser | None = None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                    "Version/16.0 Safari/604.1"
                ),
                viewport={"width": 1280, "height": 800},
            )

            # Set cookies
            cookie_list = []
            for name, value in cookie_dict.items():
                cookie_list.append({
                    "name": name,
                    "value": value,
                    "domain": ".xiaohongshu.com",
                    "path": "/",
                })
            if cookie_list:
                context.add_cookies(cookie_list)

            page = context.new_page()

            for keyword in keywords:
                encoded_kw = quote_plus(keyword)
                url = f"{SEARCH_URL}?keyword={encoded_kw}"

                try:
                    page.goto(url, timeout=30000, wait_until="domcontentloaded")
                    # Wait for content to load
                    page.wait_for_timeout(3000)

                    # Check if redirected to login
                    current_url = page.url
                    if "login" in current_url.lower() or "passport" in current_url.lower():
                        msg = f"cookie may be expired for keyword '{keyword}'"
                        logger.warning(f"Xiaohongshu: Redirected to login - {msg}")
                        continue

                    # Wait for note cards to appear
                    try:
                        page.wait_for_selector("a[href*='/explore/']", timeout=10000)
                    except Exception:
                        logger.debug(f"Xiaohongshu: No explore links found for keyword '{keyword}'")
                        continue

                    # Additional wait for dynamic content
                    page.wait_for_timeout(2000)

                    found = _extract_notes_from_page(page)
                    notes.extend(found[:limit_per_keyword])

                    count = len(found[:limit_per_keyword])
                    logger.debug(f"Xiaohongshu: Found {count} notes for keyword '{keyword}'")

                except Exception as e:
                    logger.warning(f"Xiaohongshu: Scrape failed for keyword '{keyword}': {e}")
                    continue

                # Rate limiting between keywords
                page.wait_for_timeout(2000)

            page.close()
            context.close()

    except Exception as e:
        logger.error(f"Xiaohongshu: Playwright error: {e}")
    finally:
        if browser:
            try:
                browser.close()
            except Exception:
                pass

    return notes


class XiaohongshuMonitor(BaseMonitor):
    """Monitor for Xiaohongshu (Little Red Book) platform using Playwright web scraping."""

    def __init__(self, cookie: str | None = None, config: dict[str, Any] | None = None):
        super().__init__("小红书")
        config = config or {}

        self.cookie = cookie
        self.enabled = config.get("enabled", False) and bool(cookie)

        self.keywords = config.get(
            "keywords",
            ["LLM", "大模型", "GPT", "Claude", "ChatGPT", "AI模型"],
        )

        self.limit_per_keyword = config.get("limit_per_keyword", 5)

        # Parse cookie into dict
        self.cookie_dict = _parse_cookie(cookie)

        if not self.cookie_dict:
            logger.warning("Xiaohongshu: No valid cookie configured")

    def _search_notes_sync(self, keyword: str, limit: int = 5) -> list[dict[str, Any]]:
        """Synchronous search using Playwright. Called from thread pool."""
        return _scrape_with_playwright(self.cookie_dict, [keyword], limit)

    async def fetch_new_items(self) -> list[NewsItem]:
        """Fetch new notes from Xiaohongshu via web scraping."""

        if not self.enabled:
            logger.debug("Xiaohongshu: Disabled or no cookie configured")
            return []

        new_items: list[NewsItem] = []
        loop = asyncio.get_event_loop()

        for keyword in self.keywords:
            try:
                # Run Playwright (sync) in thread pool
                notes = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        self._search_notes_sync,
                        keyword,
                        self.limit_per_keyword,
                    ),
                    timeout=60,
                )
            except TimeoutError:
                logger.warning(f"Xiaohongshu: Timeout searching for '{keyword}'")
                continue
            except Exception as e:
                logger.warning(f"Xiaohongshu: Search failed for '{keyword}': {e}")
                continue

            for note in notes:
                note_id = note.get("id")
                if not note_id or self.is_seen(note_id):
                    continue

                self.mark_seen(note_id)

                title = note.get("title", "").strip()
                desc = note.get("desc", "").strip()

                item = NewsItem(
                    id=note_id,
                    title=title or desc[:100] or f"小红书笔记 {note_id}",
                    source="小红书",
                    url=f"https://www.xiaohongshu.com/explore/{note_id}",
                    text=desc[:500] or title[:500],
                    author=note.get("user", ""),
                    published=datetime.now(),
                    extra={
                        "likes": note.get("likes", 0),
                        "type": note.get("type", ""),
                    },
                )
                new_items.append(item)

            # Rate limiting between keywords
            await asyncio.sleep(2)

        logger.info(f"小红书: Found {len(new_items)} new notes")
        return new_items
