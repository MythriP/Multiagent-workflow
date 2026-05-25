"""
enrich.py — Fetches full article text and collects all useful media (images,
videos, documents) for a clustered story.

Behaviour at a glance:

  1. For each candidate URL in the cluster (sorted by source weight):

     a. If the URL points to a research paper (arXiv, ACL, OpenReview, ar5iv),
        download the PDF, lift figures from it, record the PDF as a document,
        and DO NOT follow outbound links from the paper page (the body is
        mostly references / nav / metadata noise).

     b. Otherwise, fetch the HTML, scrape its primary text + media, then
        scan the article body's `<a>` tags. Any link that scores ≥ threshold
        on the relevance scorer (different domain + good URL/anchor signals)
        is fetched as a SECONDARY full source — same shape, same fields —
        contributing to text, images, and videos.

  2. Images are validated by ACTUAL decoded dimensions, not by HTML width
     attributes. Logos, badges, avatars, and analytics pixels are dropped.

  3. Videos are probed for duration:
     - ≤ 10 min → recorded as a "short" clip the script agent can use whole
     - 10–30 min → recorded with 1–3 highlight windows (start/end/label)
       chosen from the video's chapter list (or evenly-spaced fallbacks)
     - direct .mp4/.webm without metadata are kept (they're usually short
       blog-embedded GIFs/loops)

  4. `key_facts` is rebuilt over a wider, navigation-stripped text window so
     reactive articles (which often have all the facts at the bottom of the
     body) actually populate.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

import httpx
import yaml
from bs4 import BeautifulSoup

from . import pdf_utils
from .enrich_helpers import (
    ImageInfo,
    VideoInfo,
    is_noise_domain,
    pick_video_windows,
    probe_video,
    score_outbound_link,
    validate_image,
)

log = logging.getLogger(__name__)


CONFIG_PATH = Path(__file__).parent.parent / "config" / "settings.yaml"
PDF_CACHE_DIR = Path(__file__).parent.parent / ".pdf_cache"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

YOUTUBE_PATTERN = re.compile(
    r"(https?://(?:www\.)?(?:youtube\.com/(?:embed/|watch\?v=)|youtu\.be/)[\w\-]{11})"
)
VIDEO_EXT_PATTERN = re.compile(
    r"https?://[^\s\"'<>]+\.(?:mp4|webm|mov|m3u8)", re.IGNORECASE
)


def _load_config() -> Dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


# ── HTML helpers ─────────────────────────────────────────────────────────────


def _article_root(soup: BeautifulSoup):
    """Find the most-content-bearing root inside the page (article/main/body)."""
    return (
        soup.find("article")
        or soup.find(attrs={"role": "main"})
        or soup.find("main")
        or soup.body
    )


def _strip_chrome(soup: BeautifulSoup) -> None:
    """Drop nav/sidebar/footer/script noise IN PLACE before any extraction."""
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    for selector in [
        "nav", "footer", "header", "aside",
        "[role='navigation']", "[role='complementary']", "[role='banner']",
        ".sidebar", ".sidebar-wrap", ".side-nav",
        ".comments", ".comment-list", ".related-posts",
        ".newsletter", ".subscribe", ".share", ".social",
    ]:
        for el in soup.select(selector):
            el.decompose()


def _absolutise(url: str, page_url: str) -> str:
    if not url:
        return ""
    if url.startswith(("http://", "https://", "data:")):
        return url
    if url.startswith("//"):
        return "https:" + url
    from urllib.parse import urljoin
    return urljoin(page_url, url)


def _extract_text(soup: BeautifulSoup, max_chars: int = 10_000) -> str:
    """Pull the article body text after stripping chrome.

    The cap is deliberately bigger than the previous 8K limit so that
    longer articles (Verge / TechCrunch with sidebars) still expose actual
    factual sentences after our noise-stripping pass.
    """
    root = _article_root(soup)
    if not root:
        return ""
    text = root.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def _extract_raw_media(
    soup: BeautifulSoup, page_url: str
) -> Tuple[List[str], List[str]]:
    """Collect *candidate* image and video URLs from a page (no validation yet)."""
    images: List[str] = []
    videos: List[str] = []

    for prop in ("og:image", "og:image:secure_url", "twitter:image"):
        meta = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
        if meta and meta.get("content"):
            images.append(_absolutise(meta["content"], page_url))

    og_video = soup.find("meta", property="og:video") or soup.find(
        "meta", attrs={"name": "og:video"}
    )
    if og_video and og_video.get("content"):
        videos.append(_absolutise(og_video["content"], page_url))

    for img in soup.find_all("img"):
        src = (
            img.get("src")
            or img.get("data-src")
            or img.get("data-lazy-src")
            or img.get("data-original")
            or ""
        )
        if not src:
            srcset = img.get("srcset") or ""
            if srcset:
                # Take the largest entry from srcset
                parts = [p.strip().split(" ")[0] for p in srcset.split(",") if p.strip()]
                if parts:
                    src = parts[-1]
        if not src or src.startswith("data:"):
            continue
        full = _absolutise(src, page_url)
        if full not in images:
            images.append(full)

    for iframe in soup.find_all("iframe", src=True):
        s = _absolutise(iframe["src"], page_url)
        if "youtube.com/embed/" in s or "youtu.be/" in s or "vimeo.com/" in s:
            if s not in videos:
                videos.append(s)

    for video in soup.find_all("video"):
        s = video.get("src") or ""
        if s:
            full = _absolutise(s, page_url)
            if full not in videos:
                videos.append(full)
        for source in video.find_all("source", src=True):
            full = _absolutise(source["src"], page_url)
            if full not in videos:
                videos.append(full)

    raw = str(soup)
    for m in YOUTUBE_PATTERN.findall(raw):
        if m not in videos:
            videos.append(m)
    for m in VIDEO_EXT_PATTERN.findall(raw):
        if m not in videos:
            videos.append(m)

    # Deduplicate while preserving order
    images = list(dict.fromkeys(images))
    videos = list(dict.fromkeys(videos))
    return images, videos


# ── Outbound link harvesting ─────────────────────────────────────────────────


def _harvest_outbound_links(
    soup: BeautifulSoup,
    page_url: str,
    min_score: int,
    max_links: int,
) -> List[Tuple[int, str, str]]:
    """Return the top-scoring outbound links inside the article body.

    Returns a list of `(score, url, anchor_text)` tuples, descending by score.
    `_strip_chrome` should have been called already so we're only scanning
    real article content.
    """
    root = _article_root(soup)
    if not root:
        return []

    seen_urls: set[str] = set()
    candidates: List[Tuple[int, str, str]] = []

    for a in root.find_all("a", href=True):
        raw_href = a["href"]
        href = _absolutise(raw_href, page_url)
        if href in seen_urls:
            continue
        anchor_text = a.get_text(" ", strip=True) or ""
        score = score_outbound_link(href, anchor_text, page_url)
        if score < min_score:
            continue
        seen_urls.add(href)
        candidates.append((score, href, anchor_text[:200]))

    candidates.sort(key=lambda c: -c[0])
    return candidates[:max_links]


# ── Key-facts extraction (smarter) ───────────────────────────────────────────

# Phrases that indicate "this sentence is actually a useful fact".
_FACT_SIGNAL = re.compile(
    # Concrete numbers with units
    r"\d+(?:[.,]\d+)?\s*(%|x|×|billion|million|thousand|ms|tokens?|"
    r"parameters?|hours?|days?|weeks?|months?|years?|MB|GB|TB|FLOPS?)|"
    # Result / claim verbs
    r"\b(state[- ]of[- ]the[- ]art|SOTA|outperform(?:s|ed)?|"
    r"benchmark(?:s|ed)?|achieved|achieves|reported|reduced|improved|"
    r"introduce(?:s|d)?|propose(?:s|d)?|released|trained on|fine-tuned|"
    r"compared (?:to|with))\b|"
    # Structural-claim phrases (many ML papers describe contributions this way)
    r"\b(?:three|four|five|six|seven|eight|two|key|core|main)\s+"
    r"(?:innovations?|contributions?|components?|failure[- ]modes?|"
    r"pillars?|layers?|stages?|principles?|building\s+blocks?)\b|"
    # Failure-mode lists / definition headers (e.g. "the four failure modes are…")
    r"\b(?:failure[- ]modes?|core failures?)\s+(?:are|of|include)\b",
    re.IGNORECASE,
)

# Phrases that mark website chrome / nav widgets that look "factual" but aren't.
_NOISE_FACT = re.compile(
    r"\b(idea for a project|add value for arXiv|subscribe|sign up|"
    r"newsletter|cookie|privacy policy|terms of service|share this|"
    r"follow follow|contact us|all rights reserved|copyright|"
    r"posts from this (?:topic|author)|figure \d+:|table \d+:|"
    r"see all|view (?:all|more)|read more|click here|email digest|"
    r"home(?:page)? feed|leave a comment|posted by|stay tuned)\b",
    re.IGNORECASE,
)

# Sentences starting with these patterns are usually nav, section intros,
# or fragmentary list items — not standalone facts.
_NOISE_PREFIX = re.compile(
    r"^\s*("
    r"figure\s+\d|table\s+\d|"
    r"\d+\.\s+[A-Z]|"     # "1. Transformer-Based LLMs" — section heading
    r"that also fall into|"  # mid-paragraph fragments lifted out
    r"posts? from this|by [A-Z][a-z]+\s+[A-Z][a-z]+|"
    r"close\s+[A-Z]"
    r")",
    re.IGNORECASE,
)


def _split_sentences(text: str) -> List[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def _extract_key_facts(texts: List[str], max_facts: int = 8) -> List[str]:
    """Pull the most fact-bearing sentences across all source texts.

    Each candidate sentence is scored by `_FACT_SIGNAL` matches, then ranked
    and deduplicated. Sentences that match `_NOISE_FACT` are dropped outright.
    """
    scored: List[Tuple[int, str]] = []
    seen: set[str] = set()

    for text in texts:
        for sentence in _split_sentences(text):
            if len(sentence) < 40 or len(sentence) > 320:
                continue
            if _NOISE_FACT.search(sentence) or _NOISE_PREFIX.search(sentence):
                continue
            matches = _FACT_SIGNAL.findall(sentence)
            score = len(matches)
            if score == 0:
                continue
            normal = re.sub(r"\W+", " ", sentence.lower()).strip()
            if normal in seen:
                continue
            seen.add(normal)
            scored.append((score, sentence))

    scored.sort(key=lambda s: -s[0])
    return [s for _, s in scored[:max_facts]]


# ── Single-page fetch ────────────────────────────────────────────────────────


def _fetch_article(
    client: httpx.Client, url: str, timeout: int
) -> Tuple[str, List[str], List[str], BeautifulSoup | None]:
    """Fetch one URL → (text, raw_image_urls, raw_video_urls, soup)."""
    try:
        resp = client.get(url, timeout=timeout, follow_redirects=True)
        resp.raise_for_status()
    except Exception as exc:
        log.debug("Article fetch failed for %s: %s", url, exc)
        return "", [], [], None

    soup = BeautifulSoup(resp.text, "lxml")
    _strip_chrome(soup)
    text = _extract_text(soup)
    images, videos = _extract_raw_media(soup, url)
    return text, images, videos, soup


# ── Image / video pipelines ──────────────────────────────────────────────────


def _validate_images(
    client: httpx.Client,
    candidates: List[str],
    cfg: Dict,
    max_images: int,
) -> List[str]:
    """Run each candidate image URL through the dimensional gate."""
    min_w = int(cfg.get("image_min_width", 200))
    min_h = int(cfg.get("image_min_height", 200))
    max_aspect = float(cfg.get("image_max_aspect_ratio", 6.0))

    keepers: List[str] = []
    for url in candidates:
        if len(keepers) >= max_images:
            break
        info: ImageInfo | None = validate_image(
            client, url, min_w=min_w, min_h=min_h, max_aspect=max_aspect,
        )
        if info is None:
            continue
        keepers.append(info.url)
    return keepers


def _classify_videos(
    candidates: List[str],
    topic: str,
    cfg: Dict,
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Split candidate videos into (short_clip_urls, windowed_long_videos).

    Short videos are returned as plain strings (back-compat with the rest of
    the pipeline). Long videos get a structured entry with start/end windows.
    """
    short_max = int(cfg.get("short_max_sec", 600))
    long_max = int(cfg.get("long_max_sec", 1800))
    max_windows = int(cfg.get("max_windows_per_long", 3))
    default_window = int(cfg.get("window_default_sec", 30))

    keywords = [w for w in re.split(r"\W+", topic.lower()) if len(w) >= 4]

    shorts: List[str] = []
    longs: List[Dict[str, Any]] = []

    for url in candidates:
        if is_noise_domain(url):
            continue
        # Direct-mp4 / webm files: yt-dlp typically can't probe them. Treat
        # them as short clips (blog GIFs / demo loops are nearly always < 60s).
        lower = url.split("?")[0].lower()
        is_direct = any(lower.endswith(ext) for ext in (".mp4", ".webm", ".mov", ".m4v"))

        if is_direct:
            shorts.append(url)
            continue

        info: VideoInfo = probe_video(url)
        if info.duration_sec is None:
            # Don't drop — let the script-agent stage probe it later.
            shorts.append(url)
            continue
        if info.duration_sec <= short_max:
            shorts.append(url)
            continue
        if info.duration_sec <= long_max:
            windows = pick_video_windows(
                info,
                topic_keywords=keywords,
                max_windows=max_windows,
                default_window_sec=default_window,
            )
            longs.append({
                "url": url,
                "duration_sec": round(info.duration_sec, 1),
                "title": info.title,
                "windows": windows,
            })
        # Anything beyond `long_max` is dropped — too heavy to be worth windowing.

    return shorts, longs


# ── Paper handling (arXiv et al.) ────────────────────────────────────────────


def _enrich_paper_source(
    candidate: Dict[str, Any],
    paper_kind: str,
    paper_id: str,
    pdf_cap: int,
) -> Tuple[Dict[str, Any], List[str], List[str], List[str]]:
    """Specialised path for research-paper URLs.

    We DO NOT follow outbound links on a paper page. We DO download the PDF
    (if available), extract figures, and record the PDF URL as a document.
    Returns (source_entry, image_urls, video_urls, document_urls).
    """
    pdf_url = pdf_utils.paper_pdf_url(paper_kind, paper_id)
    figure_urls: List[str] = []
    docs: List[str] = []

    if pdf_url:
        docs.append(pdf_url)
        # Cache PDF + lifted figures in `.pdf_cache/<paper_id>/`. The figures
        # are recorded via a custom `pdf://<id>/<filename>` scheme that the
        # script agent recognises and resolves locally.
        cache_root = PDF_CACHE_DIR / paper_id
        pdf_path = cache_root / "paper.pdf"
        if not pdf_path.exists():
            cache_root.mkdir(parents=True, exist_ok=True)
            ok = pdf_utils.download_pdf(pdf_url, pdf_path)
            if not ok:
                log.info("⚠️  PDF download failed for %s", pdf_url)
                pdf_path = None  # type: ignore
        if pdf_path and pdf_path.exists():
            figs = pdf_utils.extract_pdf_figures(
                pdf_path, cache_root, max_figures=pdf_cap,
            )
            for f in figs:
                figure_urls.append(f"pdf://{paper_id}/{f.name}")
            log.info(
                "📄 Paper %s: extracted %d figure(s) from PDF",
                paper_id, len(figs),
            )

    # We still want the paper page's abstract text — it's the cleanest summary.
    source_entry: Dict[str, Any] = {
        "url": candidate.get("url", ""),
        "name": candidate.get("source_name", ""),
        "weight": candidate.get("source_weight", 0.95),
        "official": True,
        "text": candidate.get("raw_text", "")[:3000],
        "is_paper": True,
        "paper_kind": paper_kind,
        "paper_id": paper_id,
    }
    if candidate.get("hn_score") is not None:
        source_entry["hn_score"] = candidate["hn_score"]
        source_entry["hn_comments"] = candidate.get("hn_comments", 0)
    return source_entry, figure_urls, [], docs


# ── Main entry ───────────────────────────────────────────────────────────────


def enrich_cluster(scored_story: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch, validate, and merge every useful asset for a clustered story.

    The output dict is the schema saved as topic.json. Compared to the older
    enrichment, we now produce:
      • media.images          — only validated, content-sized images
      • media.videos          — short clips + structured long-video entries
      • media.long_videos     — extracted long-video metadata + windows
      • media.documents       — PDF URLs (with figures already cached)
      • sources               — original cluster + relevant followed links
      • key_facts             — fact-scored, noise-filtered sentences
    """
    cfg = _load_config().get("enrichment", {})
    max_images = int(cfg.get("max_images", 12))
    max_videos = int(cfg.get("max_videos", 4))
    max_documents = int(cfg.get("max_documents", 3))
    timeout = int(cfg.get("request_timeout", 10))
    pdf_cap = int(cfg.get("pdf_max_figures", 5))
    follow_cfg = cfg.get("follow_links", {}) or {}
    follow_enabled = bool(follow_cfg.get("enabled", True))
    follow_max = int(follow_cfg.get("max_per_source", 3))
    follow_min_score = int(follow_cfg.get("relevance_min_score", 2))
    video_cfg = cfg.get("video", {}) or {}

    cluster = scored_story.get("_cluster", [])
    dedupe_slug = scored_story.get("_slug", "")
    topic_title = scored_story.get("title", "")

    raw_images: List[str] = []  # candidates pre-validation
    raw_videos: List[str] = []
    documents: List[str] = []
    enriched_sources: List[Dict[str, Any]] = []
    all_texts: List[str] = []
    fetched_urls: set[str] = set()

    sorted_cluster = sorted(
        cluster, key=lambda c: c.get("source_weight", 0), reverse=True
    )

    with httpx.Client(timeout=timeout, headers=HEADERS, follow_redirects=True) as client:
        for candidate in sorted_cluster:
            url = candidate.get("url", "")
            if not url or url in fetched_urls:
                continue
            fetched_urls.add(url)

            paper = pdf_utils.detect_paper(url)
            if paper:
                kind, paper_id = paper
                source_entry, paper_imgs, paper_vids, paper_docs = (
                    _enrich_paper_source(candidate, kind, paper_id, pdf_cap)
                )
                for u in paper_imgs:
                    if u not in raw_images:
                        raw_images.append(u)
                for u in paper_vids:
                    if u not in raw_videos:
                        raw_videos.append(u)
                for u in paper_docs:
                    if u not in documents:
                        documents.append(u)
                if source_entry.get("text"):
                    all_texts.append(source_entry["text"])
                enriched_sources.append(source_entry)
                # IMPORTANT: do not follow outbound links on paper pages
                continue

            # ── Regular article path ────────────────────────────────────────
            text, imgs, vids, soup = _fetch_article(client, url, timeout)
            for u in imgs:
                if u not in raw_images:
                    raw_images.append(u)
            for u in vids:
                if u not in raw_videos:
                    raw_videos.append(u)
            if text or candidate.get("raw_text"):
                all_texts.append(text or candidate.get("raw_text", ""))

            source_entry = {
                "url": url,
                "name": candidate.get("source_name", ""),
                "weight": candidate.get("source_weight", 0.5),
                "official": candidate.get("official", False),
                "text": (text or candidate.get("raw_text", ""))[:3000],
                "is_paper": False,
            }
            if candidate.get("hn_score") is not None:
                source_entry["hn_score"] = candidate["hn_score"]
                source_entry["hn_comments"] = candidate.get("hn_comments", 0)
            if candidate.get("reddit_score") is not None:
                source_entry["reddit_score"] = candidate["reddit_score"]
                source_entry["reddit_comments"] = candidate.get("reddit_comments", 0)
            if candidate.get("github_stars_today") is not None:
                source_entry["github_stars_today"] = candidate["github_stars_today"]
            enriched_sources.append(source_entry)

            # ── Outbound link follow-up ─────────────────────────────────────
            if not (follow_enabled and soup is not None):
                continue
            outbound = _harvest_outbound_links(
                soup, url, min_score=follow_min_score, max_links=follow_max,
            )
            for score, link_url, anchor in outbound:
                if link_url in fetched_urls:
                    continue
                fetched_urls.add(link_url)

                # Followed paper? Run the paper path.
                paper2 = pdf_utils.detect_paper(link_url)
                if paper2:
                    kind, paper_id = paper2
                    pseudo_candidate = {
                        "url": link_url,
                        "source_name": f"{candidate.get('source_name', '')} → {anchor[:80]}",
                        "source_weight": 0.85,
                        "official": True,
                        "raw_text": "",
                    }
                    src, p_imgs, p_vids, p_docs = _enrich_paper_source(
                        pseudo_candidate, kind, paper_id, pdf_cap,
                    )
                    for u in p_imgs:
                        if u not in raw_images:
                            raw_images.append(u)
                    for u in p_docs:
                        if u not in documents:
                            documents.append(u)
                    enriched_sources.append(src)
                    log.info(
                        "  ↳ followed link (paper): %s [score=%d]", link_url, score
                    )
                    continue

                # Regular followed article
                t2, i2, v2, _soup2 = _fetch_article(client, link_url, timeout)
                if not t2 and not i2 and not v2:
                    continue
                for u in i2:
                    if u not in raw_images:
                        raw_images.append(u)
                for u in v2:
                    if u not in raw_videos:
                        raw_videos.append(u)
                if t2:
                    all_texts.append(t2)
                followed_entry = {
                    "url": link_url,
                    "name": f"{candidate.get('source_name', '')} → {anchor[:80]}".strip(" →"),
                    "weight": 0.6,  # followed links: trustworthy but not equal to origin
                    "official": False,
                    "text": t2[:3000],
                    "is_paper": False,
                    "followed_from": url,
                    "follow_score": score,
                    "anchor_text": anchor[:200],
                }
                enriched_sources.append(followed_entry)
                log.info(
                    "  ↳ followed link (article): %s [score=%d]", link_url, score
                )

        # ── Validate images by actual decoded dimensions ─────────────────────
        validated_images = _validate_images(client, raw_images, cfg, max_images)

    # ── Classify videos by duration ──────────────────────────────────────────
    short_videos, long_videos = _classify_videos(raw_videos, topic_title, video_cfg)
    short_videos = short_videos[:max_videos]
    documents = documents[:max_documents]

    key_facts = _extract_key_facts(all_texts)

    log.info(
        "📦 Enriched %s: %d sources (%d followed) · %d images (%d candidates) · "
        "%d short videos · %d long videos · %d documents · %d key facts",
        dedupe_slug,
        len(enriched_sources),
        sum(1 for s in enriched_sources if s.get("followed_from")),
        len(validated_images), len(raw_images),
        len(short_videos), len(long_videos),
        len(documents), len(key_facts),
    )

    return {
        "slug": dedupe_slug,
        "topic": topic_title,
        "score": scored_story.get("score", 0),
        "content_type": scored_story.get("content_type", "reactive"),
        "published_at": scored_story.get("published_at"),
        "sources": enriched_sources,
        "media": {
            "images": validated_images,
            "videos": short_videos,
            "long_videos": long_videos,
            "documents": documents,
        },
        "key_facts": key_facts,
        "already_posted": False,
        "approved": None,
        "_scoring_detail": {
            "recency": scored_story.get("recency_score"),
            "virality": scored_story.get("virality_score"),
            "source_weight": scored_story.get("source_weight_score"),
            "amplification": scored_story.get("amplification_score"),
            "distinct_sources": scored_story.get("distinct_sources"),
        },
    }
