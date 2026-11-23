import pytest

from pricewatch.parse import Blocked, ParseError, extract_price, parse_price_text


@pytest.mark.parametrize("text,expected", [
    ("€ 209,00", 209.00),
    ("209,00 €", 209.00),
    ("1.299,00 €", 1299.00),
    ("1,299.00", 1299.00),
    ("EUR 1.299", 1299.00),
    ("209,-", 209.00),
    ("209.99", 209.99),
    ("ab € 199,95*", 199.95),
    ("2.499.000,50", 2499000.50),
    (" 89\xa0€ ", 89.0),
])
def test_parse_price_text(text, expected):
    assert parse_price_text(text) == expected


@pytest.mark.parametrize("text", ["", "kostenlos", "0,00 €"])
def test_parse_price_text_invalid(text):
    with pytest.raises((ParseError, ValueError)):
        parse_price_text(text)


def page(body: str) -> str:
    return f"<html><head></head><body>{body}</body></html>"


def test_jsonld_offer():
    html = page('<script type="application/ld+json">{"@type":"Product","name":"X",'
                '"offers":{"@type":"Offer","price":"219.00","priceCurrency":"EUR"}}</script>')
    assert extract_price(html, "https://shop.example/x") == 219.00


def test_jsonld_aggregate_in_graph():
    html = page('<script type="application/ld+json">{"@graph":[{"@type":"WebPage"},'
                '{"@type":"Product","offers":{"@type":"AggregateOffer","lowPrice":199.9,"highPrice":260}}]}'
                '</script>')
    assert extract_price(html, "https://shop.example/x") == 199.90


def test_jsonld_list_of_offers_takes_min():
    html = page('<script type="application/ld+json">{"@type":"Product","offers":['
                '{"@type":"Offer","price":"230"},{"@type":"Offer","price":"215.5"}]}</script>')
    assert extract_price(html, "https://shop.example/x") == 215.50


def test_microdata_and_meta():
    assert extract_price(page('<span itemprop="price" content="149.00">149 €</span>'),
                         "https://s.example") == 149.0
    html = '<html><head><meta property="product:price:amount" content="99.95"></head><body></body></html>'
    assert extract_price(html, "https://s.example") == 99.95


def test_amazon_selector():
    html = page('<div id="corePrice_feature_div"><span class="a-price">'
                '<span class="a-offscreen">209,00&nbsp;€</span></span></div>')
    assert extract_price(html, "https://www.amazon.de/dp/B000TEST") == 209.00


def test_geizhals_fallback_first_gh_price():
    html = page('<div class="offer"><span class="gh_price">€ 209,00</span></div>'
                '<div class="offer"><span class="gh_price">€ 219,00</span></div>')
    assert extract_price(html, "https://geizhals.de/x-a3587143.html") == 209.00


def test_custom_selector_wins():
    html = page('<span itemprop="price" content="300"></span><b class="deal">249,99 €</b>')
    assert extract_price(html, "https://s.example", selector=".deal") == 249.99


def test_blocked_page():
    html = page("<form action='/errors/validateCaptcha'>Robot Check</form>")
    with pytest.raises(Blocked):
        extract_price(html, "https://www.amazon.de/dp/B000TEST")


def test_no_price():
    with pytest.raises(ParseError):
        extract_price(page("<p>Hallo</p>"), "https://s.example")
