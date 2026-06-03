"""
Unit tests for scraper/jumia_scraper.py — HTML parsing logic.

These tests use static HTML fixtures to verify parsing behaviour
without making live HTTP requests.
"""

import sys
import os
import pytest
from unittest.mock import MagicMock, patch
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scraper.jumia_scraper import parse_products


# ---------------------------------------------------------------------------
# HTML fixture builders
# ---------------------------------------------------------------------------

def make_product_card(
    name="Samsung Galaxy A15",
    price="KSh 15,999",
    old_price="KSh 19,999",
    discount="-20%",
    href="/samsung-galaxy-a15-mlp123.html",
):
    """Return a minimal article.prd HTML string for one product."""
    old_html = f'<div class="old">{old_price}</div>' if old_price else ""
    discount_html = f'<div class="bdg _dsct">{discount}</div>' if discount else ""
    return f"""
    <article class="prd">
        <a class="core" href="{href}">
            <div class="info">
                <h3 class="name">{name}</h3>
                <div class="prc">{price}</div>
                {old_html}
                {discount_html}
            </div>
        </a>
    </article>
    """


def make_page_html(cards_html: str) -> BeautifulSoup:
    """Wrap cards in a minimal page structure."""
    html = f"<html><body><div class='products'>{cards_html}</div></body></html>"
    return BeautifulSoup(html, "html.parser")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestParseProducts:

    def test_single_product_parsed(self):
        soup = make_page_html(make_product_card())
        products = parse_products(soup, "Smartphones", 1)
        assert len(products) == 1
        p = products[0]
        assert p["product_name"] == "Samsung Galaxy A15"
        assert p["current_price_kes"] == 15999.0
        assert p["old_price_kes"] == 19999.0
        assert p["discount_pct"] == 20.0
        assert p["category"] == "Smartphones"
        assert p["page_num"] == 1
        assert "jumia.co.ke" in p["product_url"]

    def test_product_without_old_price(self):
        soup = make_page_html(make_product_card(old_price=None, discount=None))
        products = parse_products(soup, "Computing", 1)
        assert len(products) == 1
        assert products[0]["old_price_kes"] is None
        assert products[0]["discount_pct"] is None

    def test_product_without_discount(self):
        soup = make_page_html(make_product_card(discount=None))
        products = parse_products(soup, "Computing", 2)
        assert products[0]["discount_pct"] is None

    def test_multiple_products_on_page(self):
        cards_html = "".join(
            make_product_card(
                name=f"Product {i}",
                price=f"KSh {i * 1000}",
                href=f"/product-{i}.html",
            )
            for i in range(1, 6)
        )
        soup = make_page_html(cards_html)
        products = parse_products(soup, "Home Appliances", 1)
        assert len(products) == 5

    def test_empty_page_returns_empty_list(self):
        soup = make_page_html("")
        products = parse_products(soup, "Supermarket", 1)
        assert products == []

    def test_product_with_no_price_is_excluded(self):
        """Products with no parseable price must be filtered out."""
        card = make_product_card(price="")
        soup = make_page_html(card)
        products = parse_products(soup, "Men's Fashion", 1)
        assert len(products) == 0

    def test_category_field_set_correctly(self):
        soup = make_page_html(make_product_card())
        products = parse_products(soup, "TVs & Audio", 3)
        assert products[0]["category"] == "TVs & Audio"

    def test_page_num_stored(self):
        soup = make_page_html(make_product_card())
        products = parse_products(soup, "Smartphones", 2)
        assert products[0]["page_num"] == 2

    def test_product_url_is_absolute(self):
        soup = make_page_html(make_product_card(href="/some-product.html"))
        products = parse_products(soup, "Smartphones", 1)
        assert products[0]["product_url"].startswith("https://")

    def test_supermarket_category(self):
        soup = make_page_html(
            make_product_card(
                name="Omo Washing Powder 2kg",
                price="KSh 350",
                old_price=None,
                discount=None,
                href="/omo-washing-powder-mlp999.html",
            )
        )
        products = parse_products(soup, "Supermarket", 1)
        assert len(products) == 1
        assert products[0]["current_price_kes"] == 350.0
