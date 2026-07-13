"""Ad-slot refresh detection during dwell window."""

from __future__ import annotations

import asyncio
from typing import Any

from playwright.async_api import Page

# Lightweight ad-slot counter reused during dwell polling.
_COUNT_AD_SLOTS_JS = """
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

  const isVisible = (el) => {
    const rect = el.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return false;
    const style = window.getComputedStyle(el);
    return style.display !== "none" && style.visibility !== "hidden" && style.opacity !== "0";
  };

  const seen = new Set();
  let count = 0;
  for (const selector of adSelectors) {
    for (const el of document.querySelectorAll(selector)) {
      if (!seen.has(el) && isVisible(el)) {
        seen.add(el);
        count += 1;
      }
    }
  }
  return count;
}
"""

POLL_INTERVAL_SEC = 5


async def _count_ad_slots(page: Page) -> int:
    result: Any = await page.evaluate(_COUNT_AD_SLOTS_JS)
    return int(result)


async def observe_refresh_events(
    page: Page,
    dwell_sec: float,
) -> tuple[int | None, float | None]:
    """Poll ad slot count every 5s; slot increases indicate refresh events.

    Returns ``(refresh_events_60s, avg_refresh_interval_sec)``. Both are ``None``
    when *dwell_sec* is zero (dwell not measured).
    """
    if dwell_sec <= 0:
        return None, None

    refresh_events = 0
    refresh_timestamps: list[float] = []
    previous_count = await _count_ad_slots(page)
    elapsed = 0.0

    while elapsed < dwell_sec:
        sleep_for = min(POLL_INTERVAL_SEC, dwell_sec - elapsed)
        await asyncio.sleep(sleep_for)
        elapsed += sleep_for

        current_count = await _count_ad_slots(page)
        if current_count > previous_count:
            delta = current_count - previous_count
            refresh_events += delta
            refresh_timestamps.extend([elapsed] * delta)
            previous_count = current_count

    if refresh_events == 0:
        return 0, None

    if len(refresh_timestamps) == 1:
        avg_interval = float(dwell_sec)
    else:
        intervals = [
            refresh_timestamps[i] - refresh_timestamps[i - 1]
            for i in range(1, len(refresh_timestamps))
        ]
        avg_interval = sum(intervals) / len(intervals)

    return refresh_events, avg_interval
