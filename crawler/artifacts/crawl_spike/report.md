# Crawler spike report

- Generated: `2026-07-06T11:00:39.666852+00:00`
- Domains: **100**
- Success rate: **84.0%** (84/100)
- Median crawl time: **2.8822s**
- P95 crawl time: **9.3503s**

## Top DOM metrics (median)

| Metric | Median | P95 |
|--------|--------|-----|
| `content_word_count` | 426.0 | 2106.25 |
| `ad_to_content_ratio` | 0.0 | 0.9399 |
| `ads_above_fold` | 0.0 | 2.0 |
| `ad_slots_count` | 0.0 | 7.25 |
| `sticky_ad_count` | 0.0 | 0.0 |

## By gold label

| Label | Attempted | Success rate | Median crawl (s) |
|-------|-----------|--------------|------------------|
| `MFA_High` | 29 | 82.8% | 2.9827 |
| `Non_MFA` | 71 | 84.5% | 2.8822 |

## Failures

- `bloomberg.com` — https://bloomberg.com/2024/06/15/global-markets-rally-on-inflation-data/: navigation failed for 'https://bloomberg.com/2024/06/15/global-markets-rally-on-inflation-data/' (status=403); https://bloomberg.com/politics/: navigation failed for 'https://bloomberg.com/politics/' (status=403); https://bloomberg.com/world/: navigation failed for 'https://bloomberg.com/world/' (status=403); https://bloomberg.com/: navigation failed for 'https://bloomberg.com/' (status=403)
- `bonvoyaged.com` — https://bonvoyaged.com/destinations/: Page.goto: net::ERR_NAME_NOT_RESOLVED at https://bonvoyaged.com/destinations/
Call log:
  - navigating to "https://bonvoyaged.com/destinations/", waiting until "domcontentloaded"
; https://bonvoyaged.com/hotels/: Page.goto: net::ERR_NAME_NOT_RESOLVED at https://bonvoyaged.com/hotels/
Call log:
  - navigating to "https://bonvoyaged.com/hotels/", waiting until "domcontentloaded"
; https://bonvoyaged.com/: Page.goto: net::ERR_NAME_NOT_RESOLVED at https://bonvoyaged.com/
Call log:
  - navigating to "https://bonvoyaged.com/", waiting until "domcontentloaded"

- `dailyforest.com` — https://dailyforest.com/animals/: Page.goto: Timeout 30000ms exceeded.
Call log:
  - navigating to "https://dailyforest.com/animals/", waiting until "domcontentloaded"
; https://dailyforest.com/environment/: Page.goto: Timeout 30000ms exceeded.
Call log:
  - navigating to "https://dailyforest.com/environment/", waiting until "domcontentloaded"
; https://dailyforest.com/: Page.goto: Timeout 30000ms exceeded.
Call log:
  - navigating to "https://dailyforest.com/", waiting until "domcontentloaded"

- `dailymail.co.uk` — https://dailymail.co.uk/2024/06/15/global-markets-rally-on-inflation-data/: navigation failed for 'https://dailymail.co.uk/2024/06/15/global-markets-rally-on-inflation-data/' (status=403); https://dailymail.co.uk/politics/: navigation failed for 'https://dailymail.co.uk/politics/' (status=403); https://dailymail.co.uk/world/: navigation failed for 'https://dailymail.co.uk/world/' (status=403); https://dailymail.co.uk/: navigation failed for 'https://dailymail.co.uk/' (status=403)
- `edmunds.com` — https://edmunds.com/2024/06/15/global-markets-rally-on-inflation-data/: navigation failed for 'https://edmunds.com/2024/06/15/global-markets-rally-on-inflation-data/' (status=403); https://edmunds.com/news/: navigation failed for 'https://edmunds.com/news/' (status=403); https://edmunds.com/reviews/: navigation failed for 'https://edmunds.com/reviews/' (status=403); https://edmunds.com/: navigation failed for 'https://edmunds.com/' (status=403)
- `fastcompany.com` — https://fastcompany.com/2024/06/15/global-markets-rally-on-inflation-data/: navigation failed for 'https://fastcompany.com/2024/06/15/global-markets-rally-on-inflation-data/' (status=403); https://fastcompany.com/leadership/: navigation failed for 'https://fastcompany.com/leadership/' (status=403); https://fastcompany.com/strategy/: navigation failed for 'https://fastcompany.com/strategy/' (status=403); https://fastcompany.com/: navigation failed for 'https://fastcompany.com/' (status=403)
- `globetip.com` — https://globetip.com/article/you-wont-believe-what-happened-next/: Page.goto: Timeout 30000ms exceeded.
Call log:
  - navigating to "https://globetip.com/article/you-wont-believe-what-happened-next/", waiting until "domcontentloaded"
; https://globetip.com/politics/: Page.goto: Timeout 30000ms exceeded.
Call log:
  - navigating to "https://globetip.com/politics/", waiting until "domcontentloaded"
; https://globetip.com/world/: Page.goto: Timeout 30000ms exceeded.
Call log:
  - navigating to "https://globetip.com/world/", waiting until "domcontentloaded"
; https://globetip.com/: Page.goto: Timeout 30000ms exceeded.
Call log:
  - navigating to "https://globetip.com/", waiting until "domcontentloaded"

- `go.reference.com` — https://go.reference.com/article/you-wont-believe-what-happened-next/: Page.goto: net::ERR_NAME_NOT_RESOLVED at https://go.reference.com/article/you-wont-believe-what-happened-next/
Call log:
  - navigating to "https://go.reference.com/article/you-wont-believe-what-happened-next/", waiting until "domcontentloaded"
; https://go.reference.com/science/: Page.goto: net::ERR_NAME_NOT_RESOLVED at https://go.reference.com/science/
Call log:
  - navigating to "https://go.reference.com/science/", waiting until "domcontentloaded"
; https://go.reference.com/world/: Page.goto: net::ERR_NAME_NOT_RESOLVED at https://go.reference.com/world/
Call log:
  - navigating to "https://go.reference.com/world/", waiting until "domcontentloaded"
; https://go.reference.com/: Page.goto: net::ERR_NAME_NOT_RESOLVED at https://go.reference.com/
Call log:
  - navigating to "https://go.reference.com/", waiting until "domcontentloaded"

- `icepop.com` — https://icepop.com/movies/: Page.goto: net::ERR_CERT_DATE_INVALID at https://icepop.com/movies/
Call log:
  - navigating to "https://icepop.com/movies/", waiting until "domcontentloaded"
; https://icepop.com/tv/: Page.goto: net::ERR_CERT_DATE_INVALID at https://icepop.com/tv/
Call log:
  - navigating to "https://icepop.com/tv/", waiting until "domcontentloaded"
; https://icepop.com/: Page.goto: net::ERR_CERT_DATE_INVALID at https://icepop.com/
Call log:
  - navigating to "https://icepop.com/", waiting until "domcontentloaded"

- `inc.com` — https://inc.com/2024/06/15/global-markets-rally-on-inflation-data/: navigation failed for 'https://inc.com/2024/06/15/global-markets-rally-on-inflation-data/' (status=403); https://inc.com/leadership/: navigation failed for 'https://inc.com/leadership/' (status=403); https://inc.com/strategy/: navigation failed for 'https://inc.com/strategy/' (status=403); https://inc.com/: navigation failed for 'https://inc.com/' (status=403)
- `japantimes.co.jp` — https://japantimes.co.jp/2024/06/15/global-markets-rally-on-inflation-data/: navigation failed for 'https://japantimes.co.jp/2024/06/15/global-markets-rally-on-inflation-data/' (status=403); https://japantimes.co.jp/politics/: navigation failed for 'https://japantimes.co.jp/politics/' (status=403); https://japantimes.co.jp/world/: navigation failed for 'https://japantimes.co.jp/world/' (status=403); https://japantimes.co.jp/: navigation failed for 'https://japantimes.co.jp/' (status=403)
- `marketwatch.com` — https://marketwatch.com/2024/06/15/global-markets-rally-on-inflation-data/: navigation failed for 'https://marketwatch.com/2024/06/15/global-markets-rally-on-inflation-data/' (status=403); https://marketwatch.com/investing/: navigation failed for 'https://marketwatch.com/investing/' (status=401); https://marketwatch.com/markets/: navigation failed for 'https://marketwatch.com/markets/' (status=401); https://marketwatch.com/: navigation failed for 'https://marketwatch.com/' (status=401)
- `mayoclinic.org` — https://mayoclinic.org/2024/06/15/global-markets-rally-on-inflation-data/: navigation failed for 'https://mayoclinic.org/2024/06/15/global-markets-rally-on-inflation-data/' (status=403); https://mayoclinic.org/conditions/: navigation failed for 'https://mayoclinic.org/conditions/' (status=403); https://mayoclinic.org/wellness/: navigation failed for 'https://mayoclinic.org/wellness/' (status=403); https://mayoclinic.org/: navigation failed for 'https://mayoclinic.org/' (status=403)
- `miamiherald.com` — https://miamiherald.com/2024/06/15/global-markets-rally-on-inflation-data/: Page.goto: net::ERR_HTTP2_PROTOCOL_ERROR at https://miamiherald.com/2024/06/15/global-markets-rally-on-inflation-data/
Call log:
  - navigating to "https://miamiherald.com/2024/06/15/global-markets-rally-on-inflation-data/", waiting until "domcontentloaded"
; https://miamiherald.com/politics/: Page.goto: net::ERR_HTTP2_PROTOCOL_ERROR at https://miamiherald.com/politics/
Call log:
  - navigating to "https://miamiherald.com/politics/", waiting until "domcontentloaded"
; https://miamiherald.com/world/: Page.goto: net::ERR_HTTP2_PROTOCOL_ERROR at https://miamiherald.com/world/
Call log:
  - navigating to "https://miamiherald.com/world/", waiting until "domcontentloaded"
; https://miamiherald.com/: Page.goto: net::ERR_HTTP2_PROTOCOL_ERROR at https://miamiherald.com/
Call log:
  - navigating to "https://miamiherald.com/", waiting until "domcontentloaded"

- `nba.com` — https://nba.com/2024/06/15/global-markets-rally-on-inflation-data/: navigation failed for 'https://nba.com/2024/06/15/global-markets-rally-on-inflation-data/' (status=403); https://nba.com/nba/: navigation failed for 'https://nba.com/nba/' (status=403); https://nba.com/nfl/: navigation failed for 'https://nba.com/nfl/' (status=403); https://nba.com/: navigation failed for 'https://nba.com/' (status=403)
- `oregonlive.com` — https://oregonlive.com/2024/06/15/global-markets-rally-on-inflation-data/: navigation failed for 'https://oregonlive.com/2024/06/15/global-markets-rally-on-inflation-data/' (status=403); https://oregonlive.com/politics/: navigation failed for 'https://oregonlive.com/politics/' (status=403); https://oregonlive.com/world/: navigation failed for 'https://oregonlive.com/world/' (status=403); https://oregonlive.com/: navigation failed for 'https://oregonlive.com/' (status=403)
