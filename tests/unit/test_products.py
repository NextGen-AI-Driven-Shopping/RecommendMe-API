"""Unit tests for app/services/products.py"""

from app.services.products import inject_affiliate_tag


def test_inject_affiliate_tag_no_existing_params():
    url = "https://example.com/product/123"
    result = inject_affiliate_tag(url, "my-tag")
    assert result == "https://example.com/product/123?tag=my-tag"


def test_inject_affiliate_tag_existing_params():
    url = "https://example.com/product/123?color=black"
    result = inject_affiliate_tag(url, "my-tag")
    assert result == "https://example.com/product/123?color=black&tag=my-tag"


def test_inject_affiliate_tag_empty_tag_returns_original():
    url = "https://example.com/product/123"
    result = inject_affiliate_tag(url, "")
    assert result == url


def test_placeholder():
    """Placeholder — replace with full products service tests."""
    assert True
