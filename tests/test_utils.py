"""
Unit tests for scraper/utils.py — price parsing and URL building.
"""

import pytest
import sys
import os

# Ensure the project root is on the path when running from /opt/airflow
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scraper.utils import parse_price, parse_discount, build_full_url


# ---------------------------------------------------------------------------
# parse_price
# ---------------------------------------------------------------------------

class TestParsePrice:

    def test_standard_format_with_space(self):
        assert parse_price("KSh 15,000") == 15000.0

    def test_standard_format_no_space(self):
        assert parse_price("KSh1,200") == 1200.0

    def test_large_amount(self):
        assert parse_price("KSh 125,000") == 125000.0

    def test_small_amount_no_comma(self):
        assert parse_price("KSh 999") == 999.0

    def test_decimal_price(self):
        assert parse_price("KSh 1,499.50") == 1499.50

    def test_na_string(self):
        assert parse_price("N/A") is None

    def test_empty_string(self):
        assert parse_price("") is None

    def test_none_input(self):
        assert parse_price(None) is None

    def test_whitespace_only(self):
        assert parse_price("   ") is None

    def test_zero_returns_none(self):
        assert parse_price("KSh 0") is None

    def test_kes_prefix(self):
        """Handle KES prefix variants."""
        assert parse_price("KES 3,500") == 3500.0

    def test_ksh_lowercase(self):
        assert parse_price("ksh 8,000") == 8000.0


# ---------------------------------------------------------------------------
# parse_discount
# ---------------------------------------------------------------------------

class TestParseDiscount:

    def test_standard_discount(self):
        assert parse_discount("-23%") == 23.0

    def test_discount_no_sign(self):
        assert parse_discount("15%") == 15.0

    def test_high_discount(self):
        assert parse_discount("-70%") == 70.0

    def test_none_input(self):
        assert parse_discount(None) is None

    def test_empty_string(self):
        assert parse_discount("") is None

    def test_zero_discount_returns_none(self):
        assert parse_discount("-0%") is None

    def test_whitespace_around_value(self):
        assert parse_discount("  -45%  ") == 45.0


# ---------------------------------------------------------------------------
# build_full_url
# ---------------------------------------------------------------------------

class TestBuildFullUrl:

    def test_relative_url_gets_base(self):
        result = build_full_url("/samsung-galaxy-a55-mlp358696.html")
        assert result == "https://www.jumia.co.ke/samsung-galaxy-a55-mlp358696.html"

    def test_absolute_url_unchanged(self):
        url = "https://www.jumia.co.ke/some-product.html"
        assert build_full_url(url) == url

    def test_none_returns_none(self):
        assert build_full_url(None) is None

    def test_empty_string_returns_none(self):
        assert build_full_url("") is None

    def test_no_double_slash(self):
        result = build_full_url("/product.html")
        assert "//" not in result.replace("https://", "")
