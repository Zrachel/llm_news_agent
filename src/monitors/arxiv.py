"""LLM News Agent - arXiv monitor."""

import asyncio
import io
import re
from datetime import datetime
from typing import Any

import arxiv
import httpx

from src.monitors.base import BaseMonitor, NewsItem
from src.utils.logging import get_logger

logger = get_logger("monitors.arxiv")

# Try to import PyMuPDF for PDF parsing
try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False
    logger.warning("PyMuPDF not installed, PDF affiliation extraction disabled")


class ArxivMonitor(BaseMonitor):
    """Monitor for arXiv papers."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__("arXiv")
        config = config or {}

        self.max_results = config.get("max_results", 50)
        self.categories = config.get("categories", ["cs.CL", "cs.LG"])
        self.keywords = config.get(
            "keywords",
            ["LLM", "language model", "transformer", "GPT", "reasoning"],
        )

    def _build_query(self) -> str:
        """Build arXiv search query."""
        # Category filter
        cat_query = " OR ".join(f"cat:{cat}" for cat in self.categories)

        # Keyword filter
        kw_query = " OR ".join(self.keywords)

        return f"({cat_query}) AND ({kw_query})"

    async def fetch_new_items(self) -> list[NewsItem]:
        """Fetch new papers from arXiv."""

        query = self._build_query()
        logger.debug(f"arXiv query: {query}")

        # Run blocking arxiv call in thread pool
        loop = asyncio.get_event_loop()
        papers = await loop.run_in_executor(None, self._search_papers, query)

        new_items: list[NewsItem] = []

        for paper in papers:
            paper_id = paper.entry_id

            if self.is_seen(paper_id):
                continue

            self.mark_seen(paper_id)

            # Parse authors
            authors = [a.name for a in paper.authors[:5]]
            author_str = ", ".join(authors)
            if len(paper.authors) > 5:
                author_str += f" et al. (+{len(paper.authors) - 5})"

            item = NewsItem(
                id=paper_id,
                title=paper.title.replace("\n", " ").strip(),
                source="arXiv",
                url=paper.pdf_url or paper.entry_id,
                published=paper.published,
                abstract=paper.summary.replace("\n", " ").strip(),  # Keep full abstract
                author=author_str,
                extra={
                    "categories": paper.categories,
                    "primary_category": paper.primary_category,
                    "affiliations": [],  # Will be filled later
                },
            )
            new_items.append(item)

        logger.info(f"arXiv: Found {len(new_items)} new papers")

        # Fetch affiliations for new items (limit to first 10 to avoid rate limiting)
        if new_items:
            logger.info(f"arXiv: Fetching affiliations...")
            for item in new_items[:10]:
                affiliations = await self._fetch_affiliations(item.id)
                item.extra["affiliations"] = affiliations
                await asyncio.sleep(0.5)  # Rate limit

        return new_items

    def _search_papers(self, query: str) -> list[arxiv.Result]:
        """Blocking search for papers."""
        search = arxiv.Search(
            query=query,
            max_results=self.max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
        )
        return list(search.results())

    async def _fetch_affiliations(self, arxiv_id: str) -> list[str]:
        """Fetch author affiliations from arXiv HTML page or PDF."""
        # Extract paper ID (e.g., "2602.23349" from full URL)
        match = re.search(r"(\d+\.\d+)", arxiv_id)
        if not match:
            return []

        paper_id = match.group(1)

        # Try HTML first (faster)
        affiliations = await self._fetch_affiliations_from_html(paper_id)

        # If HTML failed, try PDF
        if not affiliations and HAS_PYMUPDF:
            affiliations = await self._fetch_affiliations_from_pdf(paper_id)

        return affiliations

    async def _fetch_affiliations_from_html(self, paper_id: str) -> list[str]:
        """Fetch affiliations from arXiv HTML page."""
        html_url = f"https://arxiv.org/html/{paper_id}"

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(html_url)
                if resp.status_code != 200:
                    return []

                html = resp.text
                affiliations = []

                # Pattern 1: ltx_role_affiliation class (most common)
                aff_matches = re.findall(
                    r'class="ltx_contact ltx_role_affiliation"[^>]*>([^<]+)',
                    html
                )
                for aff in aff_matches:
                    aff = aff.strip()
                    if aff and len(aff) > 5:
                        if aff not in affiliations:
                            affiliations.append(aff)

                # Pattern 2: Name<br>Affiliation format (e.g., Databricks papers)
                if not affiliations:
                    author_matches = re.findall(
                        r'<span class="ltx_personname">[^<]+<br class="ltx_break"\s*/?>([^<]+)',
                        html
                    )
                    for aff in author_matches:
                        aff = aff.strip()
                        if aff and "@" not in aff and len(aff) > 3:
                            if aff not in affiliations:
                                affiliations.append(aff)

                return affiliations[:5]

        except Exception as e:
            logger.debug(f"Failed to fetch HTML affiliations for {paper_id}: {e}")
            return []

    async def _fetch_affiliations_from_pdf(self, paper_id: str) -> list[str]:
        """Fetch affiliations from arXiv PDF (first page only)."""
        pdf_url = f"https://arxiv.org/pdf/{paper_id}.pdf"

        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(pdf_url)
                if resp.status_code != 200:
                    return []

                # Parse PDF first page
                pdf_bytes = resp.content
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")

                if len(doc) == 0:
                    return []

                # Extract text from first page only (where affiliations typically are)
                first_page = doc[0]
                text = first_page.get_text()
                doc.close()

                # Extract affiliations from text
                affiliations = self._extract_affiliations_from_text(text)
                return affiliations[:5]

        except Exception as e:
            logger.debug(f"Failed to fetch PDF affiliations for {paper_id}: {e}")
            return []

    def _extract_affiliations_from_text(self, text: str) -> list[str]:
        """Extract affiliations from PDF text."""
        affiliations = []

        # Common institution keywords (must be in the affiliation)
        inst_keywords = [
            # Academic
            'university', 'institute', 'college', 'school of',
            'laboratory', 'lab ', 'center', 'centre',
            'department of', 'dept', 'faculty',
            'mit', 'stanford', 'berkeley', 'cmu', 'caltech',
            'oxford', 'cambridge', 'eth zurich', 'epfl', 'tsinghua', 'peking',
            # Tech companies
            'google', 'meta ai', 'meta ', 'microsoft', 'openai', 'anthropic',
            'deepmind', 'nvidia', 'amazon', 'apple', 'ibm', 'intel',
            'databricks', 'hugging face', 'cohere', 'ai2', 'allen institute',
            'scale ai', 'stability ai', 'mistral ai', 'together ai',
            'baidu', 'alibaba', 'tencent', 'bytedance', 'zhipu',
            # Research orgs
            'securebio', 'fair ', 'brain ',
        ]

        # Split text into lines and look for affiliations
        lines = text.split('\n')

        # Look in first 50 lines (typically header area)
        for line in lines[:50]:
            line = line.strip()
            if not line or len(line) < 5 or len(line) > 100:
                continue

            # Check if line contains institution keywords
            line_lower = line.lower()

            # Must contain at least one institution keyword
            if not any(kw in line_lower for kw in inst_keywords):
                continue

            # Clean up the line
            # Remove common prefixes like numbers, bullets, superscripts
            cleaned = re.sub(r'^[\d\.\)\]\*†‡§¶]+\s*', '', line)
            # Remove superscript markers at end
            cleaned = re.sub(r'[\*†‡§¶]+$', '', cleaned)
            # Remove inline superscript numbers (like "1University")
            cleaned = re.sub(r'(\d)([A-Z])', r'\2', cleaned)
            # Remove email addresses
            cleaned = re.sub(r'\S+@\S+\.\S+', '', cleaned).strip()
            # Remove trailing punctuation and partial text indicators
            cleaned = re.sub(r'[\.\,\-]+$', '', cleaned).strip()

            if not cleaned or len(cleaned) < 5:
                continue

            # Skip lines that end with hyphen or look incomplete
            if cleaned.endswith('-') or cleaned.endswith(' In') or cleaned.endswith(' of'):
                continue

            # Skip if it looks like abstract/content text
            skip_patterns = [
                'abstract', 'introduction', 'related work', 'method',
                'conclusion', 'reference', 'arxiv:', 'we propose',
                'this paper', 'in this', 'our approach', 'we present',
                'the model', 'training', 'dataset', 'results',
                'experiments', 'performance', 'baseline', 'sota',
                'only the', 'retain only', 'labels for', 'labels of',
                'we posit', 'we show', 'we find', 'we demonstrate',
                'the forefront', 'discourse', 'recent', 'advances',
                'novel', 'propose', 'existing', 'previous', 'prior',
                'however', 'therefore', 'moreover', 'furthermore',
                'specifically', 'particularly', 'significantly',
                'approach', 'framework', 'system', 'benchmark',
                'evaluation', 'analysis', 'study', 'survey',
                'now at', 'work conducted', 'together with',
                'techniques', 'gradients', 'reduce', 'memory',
            ]
            if any(sp in cleaned.lower() for sp in skip_patterns):
                continue

            # Skip lines that look like sentences (have too many words)
            word_count = len(cleaned.split())
            if word_count > 12:
                continue

            # Skip lines that start with common sentence starters
            sentence_starters = [
                r'^(the|a|an|this|that|these|those|we|our|in|on|for|to|with|by|as|is|are|was|were|has|have|had)\s',
            ]
            if any(re.match(pat, cleaned, re.IGNORECASE) for pat in sentence_starters):
                continue

            # Must look like an affiliation (contains location or org pattern)
            affiliation_patterns = [
                # Academic
                r'university', r'institute', r'school of', r'department',
                r'lab\b', r'center', r'centre', r'faculty',
                r'\bmit\b', r'\bstanford\b', r'\bberkeley\b', r'\bcmu\b', r'\bcaltech\b',
                r'\boxford\b', r'\bcambridge\b', r'eth zurich', r'\bepfl\b',
                # Companies
                r'\bgoogle\b', r'\bmeta\b', r'\bmicrosoft\b', r'\bopenai\b', r'\banthropic\b',
                r'\bdeepmind\b', r'\bnvidia\b', r'\bdatabricks\b', r'allen institute',
                r'scale ai', r'stability ai', r'mistral ai', r'together ai',
                r'\bbaidu\b', r'\balibaba\b', r'\btencent\b', r'\bbytedance\b',
                # Research
                r'\bfair\b', r'\bbrain\b',
                r', [A-Z][a-z]+$',  # Ends with location like ", California"
            ]
            if any(re.search(pat, cleaned, re.IGNORECASE) for pat in affiliation_patterns):
                # Normalize: remove duplicate affiliations that are substrings
                is_duplicate = False
                for existing in affiliations:
                    if cleaned in existing or existing in cleaned:
                        is_duplicate = True
                        break
                if not is_duplicate:
                    affiliations.append(cleaned)

        return affiliations
