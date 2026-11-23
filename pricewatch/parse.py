"""Preis-Auslese aus HTML.

Reihenfolge:
1. eigener CSS-Selektor aus der Watchlist (falls gesetzt)
2. shopspezifische Regeln (Amazon, Geizhals)
3. strukturierte Daten: JSON-LD (schema.org), Microdata, Meta-Tags
"""

from __future__ import annotations

import json
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup


class ParseError(Exception):
    """Kein Preis gefunden."""


class Blocked(Exception):
    """Seite liefert Captcha/Bot-Sperre statt Inhalt."""


_BLOCK_MARKERS = (
    "validatecaptcha",
    "robot check",
    "geben sie die zeichen unten ein",
    "cf-challenge",
    "challenge-platform",
    "access denied",
    "zugriff verweigert",
)


def parse_price_text(text: str) -> float:
    """'€ 1.299,00' / '1,299.00 €' / '209,-' / '209.00' -> float."""
    if text is None:
        raise ParseError("leerer Preis")
    s = str(text).strip()
    s = s.replace("\xa0", " ").replace("–", "").replace(",-", ",00")
    m = re.search(r"\d[\d.,\s]*", s)
    if not m:
        raise ParseError(f"keine Zahl in {text!r}")
    num = m.group(0).strip().replace(" ", "").rstrip(".,")
    if "," in num and "." in num:
        # Letztes Trennzeichen ist das Dezimalzeichen
        if num.rfind(",") > num.rfind("."):
            num = num.replace(".", "").replace(",", ".")
        else:
            num = num.replace(",", "")
    elif "," in num:
        head, _, tail = num.rpartition(",")
        num = (head.replace(",", "") + "." + tail) if len(tail) <= 2 else num.replace(",", "")
    elif num.count(".") == 1:
        head, _, tail = num.partition(".")
        if len(tail) == 3:  # '1.299' = Tausenderpunkt
            num = head + tail
    elif num.count(".") > 1:
        num = num.replace(".", "")
    value = float(num)
    if value <= 0:
        raise ParseError(f"unplausibler Preis {value}")
    return round(value, 2)


def _check_blocked(html: str) -> None:
    low = html[:200_000].lower()
    if any(marker in low for marker in _BLOCK_MARKERS):
        raise Blocked("Bot-Sperre/Captcha erkannt")


# --- strukturierte Daten -------------------------------------------------


def _iter_jsonld(soup: BeautifulSoup):
    for tag in soup.find_all("script", type="application/ld+json"):
        raw = tag.string or tag.get_text() or ""
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        stack = [data]
        while stack:
            node = stack.pop()
            if isinstance(node, list):
                stack.extend(node)
            elif isinstance(node, dict):
                yield node
                for key in ("@graph", "offers", "mainEntity", "itemOffered"):
                    if key in node:
                        stack.append(node[key])


def _price_from_offer(node: dict) -> float | None:
    types = node.get("@type")
    types = types if isinstance(types, list) else [types]
    if "AggregateOffer" in types and node.get("lowPrice") not in (None, ""):
        return parse_price_text(str(node["lowPrice"]))
    if "Offer" in types:
        for key in ("price", "lowPrice"):
            if node.get(key) not in (None, ""):
                return parse_price_text(str(node[key]))
        spec = node.get("priceSpecification")
        specs = spec if isinstance(spec, list) else [spec]
        for sp in specs:
            if isinstance(sp, dict) and sp.get("price") not in (None, ""):
                return parse_price_text(str(sp["price"]))
    return None


def price_from_jsonld(soup: BeautifulSoup) -> float | None:
    prices = []
    for node in _iter_jsonld(soup):
        try:
            p = _price_from_offer(node)
        except (ParseError, ValueError):
            p = None
        if p is not None:
            prices.append(p)
    return min(prices) if prices else None


def price_from_microdata(soup: BeautifulSoup) -> float | None:
    for prop in ("lowPrice", "price"):
        for tag in soup.find_all(attrs={"itemprop": prop}):
            val = tag.get("content") or tag.get_text(" ", strip=True)
            try:
                return parse_price_text(val)
            except (ParseError, ValueError):
                continue
    return None


def price_from_meta(soup: BeautifulSoup) -> float | None:
    for name in ("product:price:amount", "og:price:amount", "twitter:data1"):
        tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            try:
                return parse_price_text(tag["content"])
            except (ParseError, ValueError):
                continue
    return None


# --- shopspezifisch ------------------------------------------------------


def _first_selector(soup: BeautifulSoup, selectors) -> float | None:
    for sel in selectors:
        for tag in soup.select(sel):
            text = tag.get("content") or tag.get_text(" ", strip=True)
            try:
                return parse_price_text(text)
            except (ParseError, ValueError):
                continue
    return None


def price_amazon(soup: BeautifulSoup) -> float | None:
    return _first_selector(
        soup,
        [
            "#corePrice_feature_div .a-price .a-offscreen",
            "#corePriceDisplay_desktop_feature_div .a-price .a-offscreen",
            "#apex_desktop .a-price .a-offscreen",
            "#priceblock_dealprice",
            "#priceblock_ourprice",
            "#price_inside_buybox",
        ],
    )


def price_geizhals(soup: BeautifulSoup) -> float | None:
    # Geizhals sortiert Angebote standardmäßig nach Preis; günstigstes zuerst.
    p = price_from_jsonld(soup) or price_from_microdata(soup)
    if p:
        return p
    return _first_selector(soup, [".gh_price", "[class*='gh_price']", ".variant__header__pricehistory .price"])


_SHOP_RULES = {
    "amazon.": price_amazon,
    "geizhals.": price_geizhals,
    "preisvergleich.heise.de": price_geizhals,
}


def extract_price(html: str, url: str, selector: str | None = None) -> float:
    soup = BeautifulSoup(html, "lxml")

    if selector:
        p = _first_selector(soup, [selector])
        if p is not None:
            return p

    host = urlparse(url).netloc.lower()
    for key, fn in _SHOP_RULES.items():
        if key in host:
            p = fn(soup)
            if p is not None:
                return p

    for fn in (price_from_jsonld, price_from_microdata, price_from_meta):
        p = fn(soup)
        if p is not None:
            return p

    # Erst wenn nichts gefunden wurde, auf Sperrseite prüfen – echte
    # Produktseiten enthalten manchmal harmlose 'captcha'-Strings.
    _check_blocked(html)
    raise ParseError("kein Preis auf der Seite gefunden")
