import re

import scrapy

from properstar.items import ProperstarItem


class ProperstarHousesSpider(scrapy.Spider):
    """Scrapes Tunisia house listings from properstar.com.

    properstar.com sits behind an Azure WAF JS challenge that rejects plain
    HTTP requests (and even scrapy-playwright's intercepted requests) with a
    403. This spider only succeeds if requests are routed through an
    unblocker proxy that solves the challenge for you, e.g. Zyte API
    (set ZYTE_API_KEY, see settings.py). For a working scrape without a paid
    API key, use scrape_properstar.py at the project root instead, which
    drives a real, un-intercepted Playwright browser session.
    """

    name = "properstar_houses"
    allowed_domains = ["properstar.com"]

    start_url = "https://www.properstar.com/tunisia/buy/house"
    max_pages = 30

    rooms_pattern = re.compile(r"(\d+(?:[.,]\d+)?)\s*rooms?", re.IGNORECASE)
    bedrooms_pattern = re.compile(r"(\d+(?:[.,]\d+)?)\s*bed", re.IGNORECASE)
    bathrooms_pattern = re.compile(r"(\d+(?:[.,]\d+)?)\s*bath", re.IGNORECASE)
    size_pattern = re.compile(r"([\d,.]+)\s*(?:sq\s?ft|sqm|m²|m2)", re.IGNORECASE)
    type_pattern = re.compile(r"^[A-Za-z][A-Za-z\s]*")

    async def start(self):
        yield self._page_request(self.start_url, page_number=1)

    def _page_request(self, url, page_number):
        return scrapy.Request(
            url,
            callback=self.parse,
            cb_kwargs={"page_number": page_number},
            dont_filter=True,
        )

    def parse(self, response, page_number):
        cards = response.css("article.item-adaptive")
        if not cards:
            self.logger.warning(
                "No listing cards found on page %s (%s)", page_number, response.url
            )
            return

        for card in cards:
            item = self._extract_card(card, response)
            if item.get("price") or item.get("title"):
                yield item

        if page_number < self.max_pages:
            next_url = f"{self.start_url}?p={page_number + 1}"
            yield self._page_request(next_url, page_number=page_number + 1)

    def _extract_card(self, card, response):
        title_el = card.css("a.listing-title")
        title = (title_el.css("::text").get() or "").strip() or None
        listing_href = title_el.attrib.get("href")
        listing_url = response.urljoin(listing_href) if listing_href else response.url

        price = (card.css(".listing-price-main ::text").get() or "").strip() or None
        location = (card.css(".item-location::text").get() or "").strip() or None

        highlights = " ".join(
            t.strip() for t in card.css(".item-highlights ::text").getall() if t.strip()
        )

        property_type = None
        type_match = self.type_pattern.match(highlights)
        if type_match:
            property_type = type_match.group(0).strip() or None

        contact = (card.css(".user-about::text").get() or "").strip() or None

        return ProperstarItem(
            url=listing_url,
            title=title or property_type,
            location=location,
            price=price,
            size=self._find_first(highlights, self.size_pattern),
            rooms=self._find_first(highlights, self.rooms_pattern),
            bedrooms=self._find_first(highlights, self.bedrooms_pattern),
            bathrooms=self._find_first(highlights, self.bathrooms_pattern),
            house_maker_contact=contact,
        )

    @staticmethod
    def _find_first(text, pattern):
        match = pattern.search(text or "")
        return match.group(0).strip() if match else None
