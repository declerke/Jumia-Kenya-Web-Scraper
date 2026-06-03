"""
Jumia Kenya product price scraper.

Scrapes 6 categories with pagination using requests + BeautifulSoup4.
Writes results to PostgreSQL raw.product_prices via UPSERT.
"""

import logging
import os
import random
import time
from typing import List, Dict, Any, Optional

import psycopg2
import requests
from bs4 import BeautifulSoup

from scraper.utils import parse_price, parse_discount, build_full_url

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Connection": "keep-alive",
}

CATEGORIES: Dict[str, str] = {
    "Smartphones": "https://www.jumia.co.ke/smartphones/",
    "Computing": "https://www.jumia.co.ke/computing/",
    "TVs & Audio": "https://www.jumia.co.ke/televisions/",
    "Home Appliances": "https://www.jumia.co.ke/home-appliances/",
    "Men's Fashion": "https://www.jumia.co.ke/men-clothing/",
    "Supermarket": "https://www.jumia.co.ke/supermarket/",
}

MIN_PAGES = 3
REQUEST_TIMEOUT = 30  # seconds


# ---------------------------------------------------------------------------
# Scraping helpers
# ---------------------------------------------------------------------------

def fetch_page(url: str, session: requests.Session) -> Optional[BeautifulSoup]:
    """Fetch a single page and return a BeautifulSoup object, or None on failure."""
    try:
        response = session.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")
    except requests.exceptions.HTTPError as exc:
        logger.warning("HTTP error fetching %s: %s", url, exc)
        return None
    except requests.exceptions.RequestException as exc:
        logger.warning("Request error fetching %s: %s", url, exc)
        return None


def parse_products(soup: BeautifulSoup, category: str, page_num: int) -> List[Dict[str, Any]]:
    """
    Extract product records from a parsed page.

    CSS selectors:
        article.prd       — product card
        h3.name           — product name
        div.prc           — current price
        div.old           — old price
        div.bdg._dsct     — discount badge
        a.core            — link to product page
    """
    products = []
    cards = soup.select("article.prd")

    if not cards:
        logger.info("No product cards found on page %d for category '%s'.", page_num, category)
        return products

    for card in cards:
        name_tag = card.select_one("h3.name")
        price_tag = card.select_one("div.prc")
        old_price_tag = card.select_one("div.old")
        discount_tag = card.select_one("div.bdg._dsct")
        link_tag = card.select_one("a.core")

        name = name_tag.get_text(strip=True) if name_tag else None
        current_price = parse_price(price_tag.get_text(strip=True) if price_tag else None)
        old_price = parse_price(old_price_tag.get_text(strip=True) if old_price_tag else None)
        discount = parse_discount(discount_tag.get_text(strip=True) if discount_tag else None)
        product_url = build_full_url(link_tag.get("href") if link_tag else None)

        # Skip rows with no price — unusable for analysis
        if current_price is None:
            continue

        products.append(
            {
                "product_name": name,
                "current_price_kes": current_price,
                "old_price_kes": old_price,
                "discount_pct": discount,
                "category": category,
                "product_url": product_url,
                "page_num": page_num,
            }
        )

    logger.info(
        "Category '%s' | page %d | %d products parsed.", category, page_num, len(products)
    )
    return products


def scrape_category(category: str, base_url: str, pages: int = MIN_PAGES) -> List[Dict[str, Any]]:
    """
    Scrape `pages` pages of a Jumia category.

    Rate limiting: random sleep of 2–4 seconds between page requests.
    """
    all_products: List[Dict[str, Any]] = []
    session = requests.Session()

    for page_num in range(1, pages + 1):
        if page_num == 1:
            url = base_url
        else:
            url = f"{base_url}?page={page_num}"

        logger.info("Fetching: %s", url)
        soup = fetch_page(url, session)

        if soup is None:
            logger.warning("Skipping page %d for '%s' — fetch failed.", page_num, category)
            continue

        products = parse_products(soup, category, page_num)
        all_products.extend(products)

        # Respectful rate limiting between pages
        if page_num < pages:
            delay = random.uniform(2, 4)
            logger.debug("Sleeping %.2fs before next page.", delay)
            time.sleep(delay)

    logger.info(
        "Category '%s' complete — %d total products scraped.", category, len(all_products)
    )
    return all_products


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db_connection() -> psycopg2.extensions.connection:
    """Return a psycopg2 connection using environment variables."""
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "postgres"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        dbname=os.environ.get("POSTGRES_DB", "jumia_db"),
        user=os.environ.get("POSTGRES_USER", "postgres"),
        password=os.environ.get("POSTGRES_PASSWORD", "postgres"),
    )


def ensure_schema(conn: psycopg2.extensions.connection) -> None:
    """Create raw schema and product_prices table if they do not exist."""
    with conn.cursor() as cur:
        cur.execute("CREATE SCHEMA IF NOT EXISTS raw;")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS raw.product_prices (
                product_id       SERIAL PRIMARY KEY,
                product_name     VARCHAR(500),
                current_price_kes NUMERIC(12,2),
                old_price_kes    NUMERIC(12,2),
                discount_pct     NUMERIC(5,2),
                category         VARCHAR(100),
                product_url      TEXT,
                scraped_at       TIMESTAMPTZ DEFAULT NOW(),
                page_num         INT,
                scrape_date      DATE DEFAULT CURRENT_DATE
            );
            """
        )
        # Unique constraint for UPSERT key: product_url + scrape_date
        cur.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'uq_product_url_scrape_date'
                ) THEN
                    ALTER TABLE raw.product_prices
                    ADD CONSTRAINT uq_product_url_scrape_date
                    UNIQUE (product_url, scrape_date);
                END IF;
            END $$;
            """
        )
    conn.commit()
    logger.info("Schema and table verified.")


def upsert_products(
    conn: psycopg2.extensions.connection, products: List[Dict[str, Any]]
) -> int:
    """
    UPSERT product records into raw.product_prices.

    Conflict target: (product_url, scrape_date).
    On conflict: update price fields and scraped_at timestamp.
    Returns the number of rows inserted/updated.
    """
    if not products:
        return 0

    sql = """
        INSERT INTO raw.product_prices
            (product_name, current_price_kes, old_price_kes, discount_pct,
             category, product_url, page_num)
        VALUES
            (%(product_name)s, %(current_price_kes)s, %(old_price_kes)s,
             %(discount_pct)s, %(category)s, %(product_url)s, %(page_num)s)
        ON CONFLICT (product_url, scrape_date) DO UPDATE SET
            product_name      = EXCLUDED.product_name,
            current_price_kes = EXCLUDED.current_price_kes,
            old_price_kes     = EXCLUDED.old_price_kes,
            discount_pct      = EXCLUDED.discount_pct,
            page_num          = EXCLUDED.page_num,
            scraped_at        = NOW();
    """

    with conn.cursor() as cur:
        cur.executemany(sql, products)
    conn.commit()
    logger.info("Upserted %d product rows.", len(products))
    return len(products)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_all_scrapers(pages_per_category: int = MIN_PAGES) -> Dict[str, int]:
    """
    Scrape all 6 categories and write to PostgreSQL.

    Returns a dict of {category: row_count}.
    """
    conn = get_db_connection()
    ensure_schema(conn)

    results: Dict[str, int] = {}

    for category, base_url in CATEGORIES.items():
        logger.info("=== Starting scrape: %s ===", category)
        products = scrape_category(category, base_url, pages=pages_per_category)
        count = upsert_products(conn, products)
        results[category] = count

    conn.close()
    logger.info("All categories complete. Summary: %s", results)
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_all_scrapers()
