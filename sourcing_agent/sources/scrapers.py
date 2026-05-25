"""
Direct HTML and sitemap scrapers for companies without RSS feeds:
- Anthropic (news + research pages)
- Google DeepMind (blog sitemap + publications sitemap)
- Mistral AI (news page)
- Runway ML (news page)
- Cursor (blog sitemap)
- Stability AI (news-updates page)
- Perplexity (discover/tech + research pages)
"""

import httpx
import re
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}


def _get(client: httpx.Client, url: str) -> str | None:
    try:
        resp = client.get(url, follow_redirects=True)
        resp.raise_for_status()
        return resp.text
    except Exception:
        return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cutoff_date(days: int = 7) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


# ── Anthropic ─────────────────────────────────────────────────────────────────

def _scrape_anthropic(client: httpx.Client) -> List[Dict[str, Any]]:
    """Scrape anthropic.com/news and anthropic.com/research."""
    results = []

    for page_url, bias in [
        ("https://www.anthropic.com/news", "reactive"),
        ("https://www.anthropic.com/research", "educational"),
    ]:
        html = _get(client, page_url)
        if not html:
            continue

        soup = BeautifulSoup(html, "lxml")

        # Anthropic uses Next.js — article links are typically <a> tags with /news/ or /research/ paths
        seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not (href.startswith("/news/") or href.startswith("/research/")):
            continue
        # Skip index pages and overly short slugs
        if href in seen or href in ("/news", "/research") or href.count("/") < 2:
            continue
        seen.add(href)

        full_url = "https://www.anthropic.com" + href
        # Title: try nearest heading or link text
        heading = a.find(["h2", "h3", "h4"])
        title = (heading.get_text(strip=True) if heading else a.get_text(strip=True))
        # Strip date prefixes like "Apr 30, 2026ScienceEvaluating..."
        title = re.sub(r"^[A-Z][a-z]{2}\s+\d{1,2},?\s+\d{4}\S*", "", title).strip()
        if not title or len(title) < 10:
            continue

            results.append({
                "title": title,
                "url": full_url,
                "source_name": "Anthropic (official)",
                "source_weight": 1.0,
                "official": True,
                "published_at": _now_iso(),
                "virality_signal": 0,
                "content_bias": bias,
                "raw_text": "",
            })

    return results


# ── Google DeepMind ───────────────────────────────────────────────────────────

def _scrape_deepmind(client: httpx.Client, max_days: int = 14) -> List[Dict[str, Any]]:
    """Parse DeepMind sitemap for recent blog and publication URLs."""
    cutoff = _cutoff_date(max_days)
    results = []

    sitemap_xml = _get(client, "https://deepmind.google/sitemap.xml")
    if not sitemap_xml:
        return results

    try:
        root = ET.fromstring(sitemap_xml)
    except ET.ParseError:
        return results

    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

    for url_el in root.findall("sm:url", ns):
        loc = url_el.findtext("sm:loc", namespaces=ns) or ""
        lastmod = url_el.findtext("sm:lastmod", namespaces=ns) or ""

        is_blog = "/blog/" in loc and loc.count("/") > 4
        is_pub = "/research/publications/" in loc and loc.rstrip("/").split("/")[-1].isdigit()

        if not (is_blog or is_pub):
            continue

        # Filter by lastmod date
        if lastmod:
            try:
                mod_date = datetime.fromisoformat(lastmod).replace(tzinfo=timezone.utc)
                if mod_date < cutoff:
                    continue
            except ValueError:
                pass

        # Build a readable title from the URL slug
        slug = loc.rstrip("/").split("/")[-1]
        title_from_slug = slug.replace("-", " ").title()
        title = f"[DeepMind] {title_from_slug}" if is_blog else f"[DeepMind Research] Publication {slug}"

        results.append({
            "title": title,
            "url": loc,
            "source_name": "Google DeepMind (official)",
            "source_weight": 1.0,
            "official": True,
            "published_at": (datetime.fromisoformat(lastmod).replace(tzinfo=timezone.utc).isoformat()
                             if lastmod else _now_iso()),
            "virality_signal": 0,
            "content_bias": "educational" if is_pub else "both",
            "raw_text": "",
        })

    return results


# ── Cursor ────────────────────────────────────────────────────────────────────

def _scrape_cursor(client: httpx.Client) -> List[Dict[str, Any]]:
    """Parse cursor.com sitemap for blog post URLs."""
    results = []

    sitemap_xml = _get(client, "https://cursor.com/sitemap.xml")
    if not sitemap_xml:
        return results

    try:
        root = ET.fromstring(sitemap_xml)
    except ET.ParseError:
        return results

    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    skip_suffixes = {"/blog", "/blog/topic/product", "/blog/topic/research",
                     "/blog/topic/company", "/blog/topic/customers", "/blog/topic/news",
                     "/blog/topic/ideas"}

    for url_el in root.findall("sm:url", ns):
        loc = url_el.findtext("sm:loc", namespaces=ns) or ""
        if not loc.startswith("https://cursor.com/blog/"):
            continue
        # Skip very short slugs (index/tag pages like /blog/news)
        slug_part = loc.rstrip("/").removeprefix("https://cursor.com/blog/")
        if len(slug_part) < 5 or "/" in slug_part:
            continue
        if loc.rstrip("/") in skip_suffixes:
            continue

        slug = loc.rstrip("/").split("/")[-1]
        title = f"[Cursor] {slug.replace('-', ' ').title()}"

        results.append({
            "title": title,
            "url": loc,
            "source_name": "Cursor (official)",
            "source_weight": 0.9,
            "official": True,
            "published_at": _now_iso(),
            "virality_signal": 0,
            "content_bias": "both",
            "raw_text": "",
        })

    return results[:20]  # cap to latest 20


# ── Mistral AI ────────────────────────────────────────────────────────────────

def _scrape_mistral(client: httpx.Client) -> List[Dict[str, Any]]:
    """Scrape mistral.ai/news page."""
    html = _get(client, "https://mistral.ai/news")
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    results = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.startswith("/news/") or href == "/news/" or href in seen:
            continue
        seen.add(href)

        full_url = "https://mistral.ai" + href
        heading = a.find(["h2", "h3", "h4", "p"])
        title = heading.get_text(strip=True) if heading else a.get_text(strip=True)
        if not title or len(title) < 10:
            title = href.split("/")[-1].replace("-", " ").title()

        results.append({
            "title": f"[Mistral] {title}",
            "url": full_url,
            "source_name": "Mistral AI (official)",
            "source_weight": 1.0,
            "official": True,
            "published_at": _now_iso(),
            "virality_signal": 0,
            "content_bias": "reactive",
            "raw_text": "",
        })

    return results[:15]


# ── Runway ML ─────────────────────────────────────────────────────────────────

def _scrape_runway(client: httpx.Client) -> List[Dict[str, Any]]:
    """Scrape runwayml.com/news page."""
    html = _get(client, "https://runwayml.com/news")
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    results = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/news/" not in href or href in seen:
            continue
        seen.add(href)

        full_url = href if href.startswith("http") else "https://runwayml.com" + href
        heading = a.find(["h2", "h3", "h4"])
        title = heading.get_text(strip=True) if heading else a.get_text(strip=True)
        if not title or len(title) < 10:
            continue

        results.append({
            "title": f"[Runway] {title}",
            "url": full_url,
            "source_name": "Runway ML (official)",
            "source_weight": 0.95,
            "official": True,
            "published_at": _now_iso(),
            "virality_signal": 0,
            "content_bias": "both",
            "raw_text": "",
        })

    return results[:15]


# ── Stability AI ──────────────────────────────────────────────────────────────

def _scrape_stability(client: httpx.Client) -> List[Dict[str, Any]]:
    """Scrape stability.ai/news-updates page."""
    html = _get(client, "https://stability.ai/news-updates")
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    results = []

    # Stability uses Squarespace — articles are in <article> or .blog-item elements
    articles = soup.find_all(["article", "div"], class_=lambda c: c and "blog" in c.lower()) or []
    if not articles:
        # Fallback: look for headings with links
        articles = soup.find_all(["h1", "h2", "h3"])

    seen = set()
    for el in articles[:20]:
        a = el.find("a", href=True) if el.name not in ("h1", "h2", "h3") else el.find_parent("a")
        if not a:
            a = el if el.name == "a" else None
        if not a:
            continue

        href = a.get("href", "")
        if not href or href in seen:
            continue
        seen.add(href)

        full_url = href if href.startswith("http") else "https://stability.ai" + href
        heading = el.find(["h2", "h3", "h4"]) or el
        title = heading.get_text(strip=True) if hasattr(heading, "get_text") else str(heading)
        if not title or len(title) < 10:
            continue

        results.append({
            "title": f"[Stability AI] {title}",
            "url": full_url,
            "source_name": "Stability AI (official)",
            "source_weight": 0.9,
            "official": True,
            "published_at": _now_iso(),
            "virality_signal": 0,
            "content_bias": "both",
            "raw_text": "",
        })

    return results[:15]


# ── Perplexity ────────────────────────────────────────────────────────────────

def _scrape_perplexity(client: httpx.Client) -> List[Dict[str, Any]]:
    """Scrape research.perplexity.ai for research posts."""
    results = []

    for page_url, bias in [
        ("https://research.perplexity.ai/", "educational"),
        ("https://www.perplexity.ai/discover/tech", "reactive"),
    ]:
        html = _get(client, page_url)
        if not html:
            continue

        soup = BeautifulSoup(html, "lxml")
        seen = set()

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if not href or href in seen or href in ("/", "#"):
                continue
            if len(href) < 5:
                continue
            seen.add(href)

            full_url = href if href.startswith("http") else "https://www.perplexity.ai" + href
            heading = a.find(["h2", "h3", "h4"])
            title = heading.get_text(strip=True) if heading else a.get_text(strip=True)
            if not title or len(title) < 15:
                continue

            results.append({
                "title": f"[Perplexity] {title}",
                "url": full_url,
                "source_name": "Perplexity (official)",
                "source_weight": 0.9,
                "official": True,
                "published_at": _now_iso(),
                "virality_signal": 0,
                "content_bias": bias,
                "raw_text": "",
            })

    return results[:20]


# ── Main entry point ──────────────────────────────────────────────────────────

def fetch_scrapers() -> List[Dict[str, Any]]:
    """Run all scrapers and return combined candidates."""
    with httpx.Client(timeout=15, headers=HEADERS, follow_redirects=True) as client:
        results = []
        results.extend(_scrape_anthropic(client))
        results.extend(_scrape_deepmind(client))
        results.extend(_scrape_cursor(client))
        results.extend(_scrape_mistral(client))
        results.extend(_scrape_runway(client))
        results.extend(_scrape_stability(client))
        results.extend(_scrape_perplexity(client))
    return results
