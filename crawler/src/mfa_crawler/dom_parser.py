"""DOM metric extraction for crawl signal features."""

from __future__ import annotations

from typing import Any

from mfa.schemas.signals import SignalFeatures
from playwright.async_api import Page

# Injected into the page — returns raw metric dict for Python-side mapping.
_EXTRACT_DOM_METRICS_JS = """
() => {
  const adSelectors = [
    "iframe[src*='doubleclick']",
    "iframe[src*='googlesyndication']",
    "iframe[src*='ad.']",
    "ins.adsbygoogle",
    "[id*='ad-']",
    "[id*='_ad_']",
    "[class*='ad-slot']",
    "[class*='ad-container']",
    "[class*='advertisement']",
    "[data-ad]",
    "[data-ad-slot]",
  ];

  const contentRoot =
    document.querySelector("article") ||
    document.querySelector("main") ||
    document.body;

  const isVisible = (el) => {
    const rect = el.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return false;
    const style = window.getComputedStyle(el);
    return style.display !== "none" && style.visibility !== "hidden" && style.opacity !== "0";
  };

  const adElements = [];
  const seen = new Set();
  for (const selector of adSelectors) {
    for (const el of document.querySelectorAll(selector)) {
      if (!seen.has(el) && isVisible(el)) {
        seen.add(el);
        adElements.push(el);
      }
    }
  }

  const viewportHeight = window.innerHeight || document.documentElement.clientHeight;
  let adsAboveFold = 0;
  let stickyAdCount = 0;
  let adArea = 0;

  for (const el of adElements) {
    const rect = el.getBoundingClientRect();
    if (rect.top < viewportHeight && rect.bottom > 0) {
      adsAboveFold += 1;
    }
    const position = window.getComputedStyle(el).position;
    if (position === "fixed" || position === "sticky") {
      stickyAdCount += 1;
    }
    adArea += rect.width * rect.height;
  }

  const contentRect = contentRoot.getBoundingClientRect();
  const contentArea = Math.max(contentRect.width * contentRect.height, 1);
  const adToContentRatio = Math.min(adArea / contentArea, 1);

  const clone = contentRoot.cloneNode(true);
  for (const tag of ["script", "style", "noscript"]) {
    for (const el of clone.querySelectorAll(tag)) {
      el.remove();
    }
  }
  const text = (clone.textContent || "").replace(/\\s+/g, " ").trim();
  const contentWordCount = text ? text.split(" ").filter(Boolean).length : 0;

  return {
    ad_slots_count: adElements.length,
    ads_above_fold: adsAboveFold,
    sticky_ad_count: stickyAdCount,
    ad_to_content_ratio: adToContentRatio,
    content_word_count: contentWordCount,
  };
}
"""


async def extract_dom_metrics(page: Page) -> SignalFeatures:
    """Extract the five core crawl metrics from a loaded page."""
    raw: dict[str, Any] = await page.evaluate(_EXTRACT_DOM_METRICS_JS)
    return SignalFeatures(
        ad_slots_count=raw["ad_slots_count"],
        ads_above_fold=raw["ads_above_fold"],
        sticky_ad_count=raw["sticky_ad_count"],
        ad_to_content_ratio=raw["ad_to_content_ratio"],
        content_word_count=raw["content_word_count"],
    )
