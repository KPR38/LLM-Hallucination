"""
Clean scraped NHS Inform data.

Steps:
- Read the existing scraped.json (raw output from the scraper).
- Remove entries with empty / very short text.
- Trim whitespace and normalise newlines.
- Drop obvious navigation/footer sections such as "How can we improve this page?".
- Deduplicate by URL.
- Write a cleaned JSON file and optionally replace scraped.json.
"""

import json
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent
RAW_PATH = PROJECT_ROOT / "scraped.json"
BACKUP_PATH = PROJECT_ROOT / "scraped_raw.json"
CLEAN_PATH = PROJECT_ROOT / "scraped_clean.json"


def clean_text(text: str) -> str:
    """Normalise whitespace and remove obvious footer / feedback sections."""
    if not text:
        return ""

    # Normalise spaces/newlines and remove non‑breaking spaces
    t = text.replace("\u00a0", " ")
    t = t.replace("\r\n", "\n").replace("\r", "\n")

    # Cut off common footer / feedback sections that are not medical content
    cut_markers = [
        "How can we improve this page?",
        "Help us improve NHS inform",
        "Your feedback has been received",
        "Don’t include personal information",
        "Don't include personal information",
        "Email Address",
        "Send feedback",
        "Last updated:",
        "Source:",
    ]
    lower_t = t
    cut_pos = len(t)
    for marker in cut_markers:
        idx = lower_t.find(marker)
        if idx != -1 and idx < cut_pos:
            cut_pos = idx
    if cut_pos != len(t):
        t = t[:cut_pos]

    # Collapse 3+ newlines to 2 and multiple spaces/tabs to a single space
    t = re.sub(r"\n{3,}", "\n\n", t)
    t = re.sub(r"[ \t]{2,}", " ", t)

    return t.strip()


def main() -> None:
    """Build a cleaned combined JSON from all per-page files under scraped/."""
    scraped_dir = PROJECT_ROOT / "scraped"
    if not scraped_dir.exists():
        raise FileNotFoundError(f"{scraped_dir} not found – run the scraper first.")

    per_page_files = sorted(scraped_dir.glob("*.json"))
    if not per_page_files:
        raise FileNotFoundError(f"No JSON files found in {scraped_dir} – run the scraper first.")

    cleaned = []
    seen_urls: set[str] = set()

    for path in per_page_files:
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue

        url = (item.get("url") or "").strip()
        title = (item.get("title") or "").strip()
        text = item.get("text") or ""

        # Skip if no URL at all
        if not url:
            continue

        # Clean text and skip if still empty / extremely short (likely navigation)
        text = clean_text(text)
        if not text or len(text) < 200:
            continue

        if url in seen_urls:
            continue
        seen_urls.add(url)

        cleaned.append(
            {
                "url": url,
                "title": title,
                "text": text,
                "content_length": len(text),
            }
        )

    print(f"Per-page files read: {len(per_page_files)}")
    print(f"Cleaned records kept: {len(cleaned)}")

    CLEAN_PATH.write_text(
        json.dumps(cleaned, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Saved cleaned data to {CLEAN_PATH}")

    # Backup the existing scraped.json (if any) and replace it with the cleaned version
    if RAW_PATH.exists() and not BACKUP_PATH.exists():
        RAW_PATH.rename(BACKUP_PATH)
        print(f"Backed up existing scraped.json to {BACKUP_PATH}")

    RAW_PATH.write_text(
        json.dumps(cleaned, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Overwrote {RAW_PATH} with cleaned data.")


if __name__ == "__main__":
    main()

