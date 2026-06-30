"""Scrape Properstar Tunisia house listings.

properstar.com sits behind an Azure WAF JavaScript challenge: any plain HTTP
client (curl, requests, Scrapy's default downloader, and even Scrapy's
Playwright integration with its request-interception hooks) gets a 403
forever. A real, un-intercepted browser session is required to pass the
challenge once; after that the WAF cookie is reused for every paginated
request in the same browser context. This script drives that session
directly with Playwright (bypassing scrapy-playwright's downloader, whose
``page.route()`` interception breaks the challenge) and writes the parsed
listings straight to JSON.
"""

import argparse
import json
import re

from playwright.sync_api import sync_playwright

START_URL = "https://www.properstar.com/tunisia/buy/house"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

ROOMS_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*rooms?", re.IGNORECASE)
BEDROOMS_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*bed", re.IGNORECASE)
BATHROOMS_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*bath", re.IGNORECASE)
SIZE_RE = re.compile(r"([\d,.]+)\s*(?:sq\s?ft|sqm|m²|m2)", re.IGNORECASE)
TYPE_RE = re.compile(r"^[A-Za-z][A-Za-z\s]*")


def find_first(pattern, text):
    match = pattern.search(text or "")
    return match.group(0).strip() if match else None


def text_of(el):
    return (el.inner_text() or "").strip() if el else None


def extract_card(card, base_url):
    title_el = card.query_selector("a.listing-title")
    title = text_of(title_el)
    href = title_el.get_attribute("href") if title_el else None
    listing_url = base_url.split("/tunisia")[0] + href if href else base_url

    price = text_of(card.query_selector(".listing-price-main"))
    location = text_of(card.query_selector(".item-location"))
    highlights = text_of(card.query_selector(".item-highlights")) or ""
    contact = text_of(card.query_selector(".user-about"))

    type_match = TYPE_RE.match(highlights)
    property_type = type_match.group(0).strip() if type_match else None

    return {
        "url": listing_url,
        "title": title or property_type,
        "location": location,
        "price": price,
        "size": find_first(SIZE_RE, highlights),
        "rooms": find_first(ROOMS_RE, highlights),
        "bedrooms": find_first(BEDROOMS_RE, highlights),
        "bathrooms": find_first(BATHROOMS_RE, highlights),
        "house_maker_contact": contact,
    }


def scrape(max_pages, output_path, headless=True):
    records = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(user_agent=USER_AGENT, locale="en-US")
        page = context.new_page()

        seen_urls = set()
        for page_number in range(1, max_pages + 1):
            url = START_URL if page_number == 1 else f"{START_URL}?p={page_number}"
            response = page.goto(url, wait_until="networkidle", timeout=45000)
            page.wait_for_timeout(3000 if page_number == 1 else 1200)

            cards = page.query_selector_all("article.item-adaptive")
            new_count = 0
            for card in cards:
                record = extract_card(card, url)
                if record["url"] in seen_urls:
                    continue
                if record.get("price") or record.get("title"):
                    seen_urls.add(record["url"])
                    records.append(record)
                    new_count += 1

            print(
                f"page {page_number}: status={response.status if response else None} "
                f"cards={len(cards)} new={new_count}"
            )
            if not cards or new_count == 0:
                break

        browser.close()

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(records)} listings to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-pages", type=int, default=30)
    parser.add_argument("--output", default="houses.json")
    parser.add_argument(
        "--headed", action="store_true", help="Run with a visible browser window"
    )
    args = parser.parse_args()

    scrape(args.max_pages, args.output, headless=not args.headed)
