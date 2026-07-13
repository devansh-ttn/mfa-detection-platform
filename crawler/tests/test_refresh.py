"""Unit tests for refresh detection during dwell."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from mfa_crawler.refresh import observe_refresh_events


@pytest.mark.asyncio
async def test_observe_refresh_events_zero_dwell_returns_null() -> None:
    page = MagicMock()
    events, avg_interval = await observe_refresh_events(page, 0)
    assert events is None
    assert avg_interval is None
    page.evaluate.assert_not_called()


@pytest.mark.asyncio
async def test_observe_refresh_events_no_increase_returns_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    page = MagicMock()
    page.evaluate = AsyncMock(return_value=3)

    async def fast_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("mfa_crawler.refresh.asyncio.sleep", fast_sleep)

    events, avg_interval = await observe_refresh_events(page, 10)
    assert events == 0
    assert avg_interval is None


@pytest.mark.asyncio
async def test_observe_refresh_events_counts_slot_increases(monkeypatch: pytest.MonkeyPatch) -> None:
    page = MagicMock()
    counts = [2, 2, 4, 5]
    page.evaluate = AsyncMock(side_effect=counts)

    async def fast_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("mfa_crawler.refresh.asyncio.sleep", fast_sleep)

    events, avg_interval = await observe_refresh_events(page, 15)
    assert events == 3
    assert avg_interval is not None
    assert avg_interval > 0
