"""DOM metric extraction for crawl signal features."""

from __future__ import annotations

from typing import Any

from mfa.schemas.signals import SignalFeatures
from playwright.async_api import Page

# Core metrics extracted in baseline crawl.
CORE_DOM_METRIC_NAMES: tuple[str, ...] = (
    "ad_to_content_ratio",
    "ads_above_fold",
    "ad_slots_count",
    "sticky_ad_count",
    "content_word_count",
)

EXTENDED_DOM_METRIC_NAMES: tuple[str, ...] = (
    "iframe_ad_count",
    "native_ad_count",
    "outbound_link_count",
    "video_autoplay_count",
    "image_to_text_ratio",
    "content_uniqueness_score",
    "author_page_exists",
)

DOM_METRIC_NAMES: tuple[str, ...] = CORE_DOM_METRIC_NAMES + EXTENDED_DOM_METRIC_NAMES

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

  const iframeAdSelectors = [
    "iframe[src*='doubleclick']",
    "iframe[src*='googlesyndication']",
    "iframe[src*='ad.']",
    "iframe[id*='google_ads']",
  ];

  const nativeAdSelectors = [
    "[class*='native-ad']",
    "[class*='sponsored']",
    "[data-native-ad]",
    "[data-sponsored]",
    "a[rel*='sponsored']",
    ".OUTBRAIN",
    ".taboola",
  ];

  const authorLinkSelectors = [
    "a[rel='author']",
    "a[href*='/author/']",
    "a[href*='/authors/']",
    "a[href*='/by/']",
    ".author a",
    ".byline a",
    "[class*='author'] a",
    "[class*='byline'] a",
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

  const countVisible = (selectors) => {
    const seen = new Set();
    let count = 0;
    for (const selector of selectors) {
      for (const el of document.querySelectorAll(selector)) {
        if (!seen.has(el) && isVisible(el)) {
          seen.add(el);
          count += 1;
        }
      }
    }
    return count;
  };

  const adElements = [];
  const seenAds = new Set();
  for (const selector of adSelectors) {
    for (const el of document.querySelectorAll(selector)) {
      if (!seenAds.has(el) && isVisible(el)) {
        seenAds.add(el);
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
  const words = text ? text.split(" ").filter(Boolean) : [];
  const contentWordCount = words.length;
  const uniqueWords = new Set(words.map((w) => w.toLowerCase()));
  const contentUniquenessScore =
    contentWordCount > 0 ? uniqueWords.size / contentWordCount : null;

  const imageCount = contentRoot.querySelectorAll("img").length;
  const imageToTextRatio =
    contentWordCount > 0 ? imageCount / contentWordCount : null;

  let authorPageExists = false;
  for (const selector of authorLinkSelectors) {
    for (const el of document.querySelectorAll(selector)) {
      if (isVisible(el)) {
        authorPageExists = true;
        break;
      }
    }
    if (authorPageExists) break;
  }

  const pageHost = window.location.hostname;
  let outboundLinkCount = 0;
  const seenLinks = new Set();
  for (const anchor of document.querySelectorAll("a[href]")) {
    if (!isVisible(anchor) || seenLinks.has(anchor)) continue;
    seenLinks.add(anchor);
    try {
      const href = anchor.href;
      if (!href || href.startsWith("#") || href.startsWith("javascript:")) continue;
      const linkHost = new URL(href, window.location.href).hostname;
      if (linkHost && linkHost !== pageHost) {
        outboundLinkCount += 1;
      }
    } catch (_err) {
      continue;
    }
  }

  let videoAutoplayCount = 0;
  for (const video of document.querySelectorAll("video")) {
    if (!isVisible(video)) continue;
    if (video.autoplay || video.hasAttribute("autoplay")) {
      videoAutoplayCount += 1;
    }
  }

  const paginationSelectors = [
    "[class*='pagination'] button",
    "[class*='slideshow'] button",
    "[class*='carousel'] [class*='dot']",
    "[class*='gallery'] [class*='page']",
    "button[aria-label*='page']",
    "button[aria-label*='slide']",
  ];
  let slideshowPaginationDepth = 0;
  for (const selector of paginationSelectors) {
    slideshowPaginationDepth += document.querySelectorAll(selector).length;
  }

  let pageLoadAdLatencyMs = null;
  try {
    const perf = window.performance;
    if (perf && perf.timing && perf.timing.loadEventEnd > 0) {
      pageLoadAdLatencyMs = perf.timing.loadEventEnd - perf.timing.navigationStart;
    }
  } catch (_err) {
    pageLoadAdLatencyMs = null;
  }

  return {
    ad_slots_count: adElements.length,
    ads_above_fold: adsAboveFold,
    sticky_ad_count: stickyAdCount,
    ad_to_content_ratio: adToContentRatio,
    content_word_count: contentWordCount,
    iframe_ad_count: countVisible(iframeAdSelectors),
    native_ad_count: countVisible(nativeAdSelectors),
    outbound_link_count: outboundLinkCount,
    video_autoplay_count: videoAutoplayCount,
    image_to_text_ratio: imageToTextRatio,
    content_uniqueness_score: contentUniquenessScore,
    author_page_exists: authorPageExists,
    slideshow_pagination_depth: slideshowPaginationDepth,
    page_load_ad_latency_ms: pageLoadAdLatencyMs,
  };
}
"""


async def extract_dom_metrics(page: Page) -> SignalFeatures:
    """Extract crawl DOM metrics from a loaded page."""
    raw: dict[str, Any] = await page.evaluate(_EXTRACT_DOM_METRICS_JS)
    return SignalFeatures(
        ad_slots_count=raw["ad_slots_count"],
        ads_above_fold=raw["ads_above_fold"],
        sticky_ad_count=raw["sticky_ad_count"],
        ad_to_content_ratio=raw["ad_to_content_ratio"],
        content_word_count=raw["content_word_count"],
        iframe_ad_count=raw["iframe_ad_count"],
        native_ad_count=raw["native_ad_count"],
        outbound_link_count=raw["outbound_link_count"],
        video_autoplay_count=raw["video_autoplay_count"],
        image_to_text_ratio=raw["image_to_text_ratio"],
        content_uniqueness_score=raw["content_uniqueness_score"],
        author_page_exists=raw["author_page_exists"],
        slideshow_pagination_depth=raw.get("slideshow_pagination_depth"),
        page_load_ad_latency_ms=raw.get("page_load_ad_latency_ms"),
    )
