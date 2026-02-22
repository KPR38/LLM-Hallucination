# Manual guide: Getting A–Z data from NHS Inform using web scraping

This guide walks you through getting the illnesses-and-conditions A–Z data from the NHS Inform link **by doing it yourself** with Python, `requests`, and Beautiful Soup.

---

## 1. What you need

- **Python** (3.7+)
- **Libraries**: `requests` (to fetch web pages), `beautifulsoup4` (to parse HTML), `lxml` (parser for Beautiful Soup)
- **The NHS Inform A–Z page**:  
  `https://www.nhsinform.scot/illnesses-and-conditions/a-to-z`

**Install the libraries (one-time):**
```bash
pip install requests beautifulsoup4 lxml
```

---

## 2. Big picture: what “web scraping” does here

1. **Fetch** the A–Z index page (one URL) and get its HTML.
2. **Parse** the HTML and **find all links** that point to individual condition pages (e.g. “abdominal aortic aneurysm”, “achilles tendinopathy”).
3. **Visit each of those links** one by one (with a small delay to be polite).
4. On each condition page, **find the main text** (the article body) and **save** it (e.g. title + text to a file or a list).

So: one index page → many links → many pages → extract and save content from each.

---

## 3. Step 1: Fetch one page and see the HTML

**Goal:** Get the HTML of the A–Z page and understand its structure.

- Use `requests.get(url)` with a **User-Agent** header (some sites expect a browser-like client).
- Get the response text: `response.text`.

**Try this in Python (or a small script):**
```python
import requests

url = "https://www.nhsinform.scot/illnesses-and-conditions/a-to-z"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}
response = requests.get(url, headers=headers, timeout=30)
print(response.status_code)  # should be 200
html = response.text
# Optional: save to a file to inspect in a browser or text editor
# with open("az_page.html", "w", encoding="utf-8") as f:
#     f.write(html)
```

**What to do:** Open the saved HTML (or print a small part of it) and look for:
- Where the **links** to conditions are (e.g. inside `<a href="...">`).
- What pattern the URLs follow (e.g. they all contain `/illnesses-and-conditions/`).

---

## 4. Step 2: Parse HTML with Beautiful Soup and find links

**Goal:** From the A–Z page HTML, get a list of all URLs that are condition pages.

- Parse the HTML: `BeautifulSoup(html, "lxml")`.
- Find all `<a>` tags: `soup.find_all("a", href=True)`.
- For each `<a>`:
  - Read `href` (may be relative, e.g. `/illnesses-and-conditions/a-to-z/abdominal-aortic-aneurysm/`).
  - Turn it into a **full URL**: base is `https://www.nhsinform.scot`, so full URL = base + href.
  - **Filter**: keep only links that look like condition pages (e.g. contain `illnesses-and-conditions` and are not just the A–Z index itself).
- Put all such full URLs in a list (and remove duplicates if needed).

**Hint:** `urllib.parse.urljoin(base_url, href)` turns a base URL and a relative path into a full URL.

**You do:** Write a loop over `soup.find_all("a", href=True)`, build the full URL, and append to a list if it matches your condition pattern. Print the list length and a few URLs to check.

---

## 5. Step 3: Visit one condition page and find the main content

**Goal:** For **one** condition URL, fetch the page and extract the main article text (not menus, footers, etc.).

- Fetch that URL the same way as Step 1 (requests + User-Agent).
- Parse with Beautiful Soup.
- On NHS Inform, the main content is usually inside a specific `<div>` (e.g. with a class like `panel-content` or `plethoraplugins-tabs--content`). You need to **inspect** the HTML of one condition page to see which tag wraps the article body.
- Use `soup.find("div", class_="...")` or `soup.find_all("div", class_=...)` and pick the one that contains the long text.
- Get the text: `element.get_text(separator="\n", strip=True)`.

**You do:** Pick one condition URL from your list. Fetch it, parse it, find the div that has the condition text, and print that text (or its length) to confirm you got the right part.

---

## 6. Step 4: Loop over all links and save data

**Goal:** Do Step 3 for every URL in your list; save title + text (e.g. to JSON or CSV).

- For each URL in your list:
  - Fetch the page.
  - Parse with Beautiful Soup.
  - Find the **title** (e.g. `<title>` tag) and the **main content** div you found in Step 3.
  - Store in a list of dicts, e.g. `{"url": url, "title": title, "text": text}`.
  - **Be polite:** `time.sleep(1)` (or similar) between requests so you don’t hit the server too hard.
- At the end, save the list (e.g. `json.dumps(list_of_dicts, indent=2)` to a file, or write to CSV).

**You do:** Write the loop, add the delay, and save the result to something like `scraped.json`. Start with a **small** list (e.g. first 5 URLs) to test before running on all links.

---

## 7. Quick reference: useful Beautiful Soup and requests bits

| Task | Example |
|------|--------|
| Fetch a page | `requests.get(url, headers=..., timeout=30)` |
| Get HTML | `response.text` |
| Parse HTML | `BeautifulSoup(html, "lxml")` |
| Find all links | `soup.find_all("a", href=True)` |
| Get link URL | `tag["href"]` |
| Find div by class | `soup.find("div", class_="panel-content")` or use a regex if class has multiple parts |
| Get text from element | `element.get_text(separator="\n", strip=True)` |
| Build full URL | `from urllib.parse import urljoin` then `urljoin("https://www.nhsinform.scot", href)` |

---

## 8. Suggested order of work

1. Fetch the A–Z page and save a copy of the HTML; open it and see where the condition links are.
2. Write code to parse that page and collect all condition URLs; print the count and a few URLs.
3. Pick one condition URL; write code to fetch it and extract the main content div; print the text length.
4. Write a loop over the first 5 URLs, extract title + text, and save to a list.
5. Save that list to `scraped.json` (or CSV).
6. Remove the “first 5” limit and run on the full list (with a delay between requests).

---

## 9. If something goes wrong

- **Timeout:** Increase `timeout=30` or add retries.
- **Wrong content:** Re-inspect the condition page HTML; the class name might be different (e.g. `plethoraplugins-tabs--content`).
- **Too many links:** Filter by `"/illnesses-and-conditions/"` in the URL so you don’t scrape unrelated pages.
- **Encoding:** Use `response.text` (requests decodes for you) and when writing files use `encoding="utf-8"`.

You already have a working scraper in this repo (`scraper.py` / `nhs_scraper.py`) for reference; this guide is so you can **recreate the logic yourself** step by step and understand each part.
