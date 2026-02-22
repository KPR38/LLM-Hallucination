"""
NHS Inform (nhsinform.scot) scraper.
Collects URLs from the sitemap or the illnesses-and-conditions A-Z page,
then visits each URL and scrapes the main content.
"""

import time
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.nhsinform.scot"
A_Z_URL = "https://www.nhsinform.scot/illnesses-and-conditions/a-to-z"
SITEMAP_URL = "https://www.nhsinform.scot/sitemap.xml"


# Only scrape pages under these paths (optional filter)
SCOPES = (
    "/illnesses-and-conditions/",
    "/symptoms-and-self-help/",
    "/tests-and-treatments/",
)

# Index/landing pages that have no main content block; skip to avoid empty text
INDEX_PATHS_TO_SKIP = (
    "/illnesses-and-conditions",
    "/symptoms-and-self-help",
    "/tests-and-treatments",
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}
REQUEST_DELAY = 1.0  # seconds between requests


def get_soup(url: str, session: requests.Session, *, parse_xml: bool = False) -> BeautifulSoup | None:
    """Fetch URL and return BeautifulSoup or None on failure. Use parse_xml=True for sitemap XML."""
    try:
        r = session.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        parser = "xml" if parse_xml else "lxml"
        return BeautifulSoup(r.text, parser)
    except Exception as e:
        print(f"  Error fetching {url}: {e}")
        return None


def urls_from_az_page(session: requests.Session, page_url: str | None = None) -> list[str]:
    """Extract condition page URLs from the A-Z page (or any index page you drop)."""
    url = page_url or A_Z_URL
    urls = []
    soup = get_soup(url, session)
    if not soup:
        return urls

    base_domain = urlparse(url).netloc or "www.nhsinform.scot"
    scheme = urlparse(url).scheme or "https"

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("#"):
            continue
        full = urljoin(url, href)
        parsed = urlparse(full)
        if parsed.netloc and parsed.netloc != base_domain:
            continue
        if not full.startswith("http"):
            full = f"{scheme}://{base_domain}{parsed.path or '/'}"
        # Collect illness/condition (and related) pages
        if "/illnesses-and-conditions/" in full or "/symptoms-and-self-help/" in full or "/tests-and-treatments/" in full:
            path = urlparse(full).path.rstrip("/")
            if path != "/illnesses-and-conditions/a-to-z":
                urls.append(full)

    return list(dict.fromkeys(urls))


def urls_from_sitemap_url(session: requests.Session, sitemap_url: str) -> list[str]:
    """Extract page URLs from a sitemap XML (e.g. when you drop a sitemap link)."""
    urls = []
    soup = get_soup(sitemap_url, session, parse_xml=True)
    if not soup:
        return urls

    for loc in soup.find_all("loc"):
        loc_url = loc.get_text(strip=True)
        if loc_url.endswith(".xml"):
            time.sleep(REQUEST_DELAY)
            sub = get_soup(loc_url, session, parse_xml=True)
            if sub:
                for sub_loc in sub.find_all("loc"):
                    u = sub_loc.get_text(strip=True)
                    if u.startswith("https://") and "nhsinform.scot" in u and not u.endswith(".xml"):
                        urls.append(u)
        else:
            if (loc_url.startswith("https://") and "nhsinform.scot" in loc_url
                    and not urlparse(loc_url).path.rstrip("/").endswith(".xml")):
                urls.append(loc_url)

    return list(dict.fromkeys(urls))


def scrape_page_content(session: requests.Session, url: str) -> dict | None:
    """Visit a page and return title + main content text (and optional HTML)."""
    soup = get_soup(url, session)
    if not soup:
        return None

    title = ""
    t = soup.find("title")
    if t:
        title = t.get_text(strip=True)

    # NHS Inform uses .panel-content.guidetabs or .plethoraplugins-tabs--content
    target = (
        soup.find("div", class_=re.compile(r"plethoraplugins-tabs--content", re.I))
        or soup.find("div", class_=re.compile(r"panel-content|guidetabs", re.I))
        or soup.find("main")
        or soup.find("article")
        or soup.find("div", class_=re.compile(r"content|article|main|body|prose|page", re.I))
        or soup.find("body")
    )
    text = target.get_text(separator="\n", strip=True) if target else ""
    # Collapse multiple newlines
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    return {
        "url": url,
        "title": title,
        "text": text,
        "content_length": len(text),
    }


def filter_urls(urls: list[str], use_scope_filter: bool) -> list[str]:
    """Optionally restrict to SCOPES paths."""
    if not use_scope_filter:
        return urls
    return [u for u in urls if any(u.startswith(BASE_URL + s) for s in SCOPES)]


def skip_index_pages(urls: list[str]) -> list[str]:
    """Drop index/landing URLs that yield no main content (empty text)."""
    return [u for u in urls if urlparse(u).path.rstrip("/") not in INDEX_PATHS_TO_SKIP]


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Scrape NHS Inform illness/condition pages.")
    parser.add_argument("--link", type=str, metavar="URL", help="Drop an NHS Inform link (A-Z page or sitemap) to discover and scrape all diseases/content from it")
    parser.add_argument("--sitemap", action="store_true", help="Use sitemap.xml only (default: try sitemap then A-Z)")
    parser.add_argument("--az-only", action="store_true", help="Use A-Z page only (no sitemap)")
    parser.add_argument("--no-scope-filter", action="store_true", help="Scrape all URLs from sitemap (not just illnesses/symptoms/treatments)")
    parser.add_argument("--limit", type=int, default=0, help="Max number of pages to scrape (0 = no limit)")
    parser.add_argument("--out", default="scraped", help="Output directory (default: scraped)")
    parser.add_argument("--json", default="scraped.json", help="Output JSON file (default: scraped.json)")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()

    # Collect URLs
    urls = []
    if args.link:
        link = args.link.strip()
        print(f"Using your link: {link}")
        if link.lower().endswith(".xml") or "sitemap" in link.lower():
            urls = urls_from_sitemap_url(session, link)
            print("Discovered URLs from sitemap.")
        else:
            urls = urls_from_az_page(session, page_url=link)
            print("Discovered URLs from index page (diseases/conditions, symptoms, tests & treatments).")
    elif args.az_only:
        print("Collecting URLs from A-Z page...")
        urls = urls_from_az_page(session)
    elif args.sitemap:
        print("Collecting URLs from sitemap only...")
        urls = urls_from_sitemap_url(session, SITEMAP_URL)
    else:
        print("Trying sitemap...")
        urls = urls_from_sitemap_url(session, SITEMAP_URL)
        if not urls:
            print("Sitemap failed or empty, using A-Z page...")
            urls = urls_from_az_page(session)

    # When you drop a link, we scrape everything found on that page; otherwise apply optional filter
    use_filter = not args.no_scope_filter and not args.link
    urls = filter_urls(urls, use_scope_filter=use_filter)
    urls = skip_index_pages(urls)
    print(f"Found {len(urls)} URLs.")

    if args.limit:
        urls = urls[: args.limit]
        print(f"Limited to first {args.limit} URLs.")

    # Scrape each URL
    results = []
    for i, url in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}] {url}")
        time.sleep(REQUEST_DELAY)
        data = scrape_page_content(session, url)
        
        if data:
            results.append(data)
            # Optional: save per-page JSON
            safe = re.sub(r"[^\w\-]", "_", urlparse(url).path.strip("/")) or "page"
            (out_dir / f"{safe[:80]}.json").write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
            )

    # Save combined JSON
    out_json = Path(args.json)
    out_json.write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Done. Saved {len(results)} pages to {out_json} and to {out_dir}/")


if __name__ == "__main__":
    main()
