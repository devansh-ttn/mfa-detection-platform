#!/usr/bin/env python3
"""Build gold-label URL seed dataset for MFA detection platform.

Generates CSV + JSONL with real domains from publicly documented industry sources.
Run: python scripts/seed/build_gold_labels.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = REPO_ROOT / "data" / "seed"
SOURCE_BATCH_ID = "seed-v1-2026-07-03"
CREATED_AT = datetime.now(UTC).isoformat()

# Domains confirmed in Adalytics (Jan 2024) as meeting ANA/WFA/ISBA/4A's + Jounce/DeepSee MFA criteria.
# https://adalytics.io/blog/ads-observed-on-made-for-advertising-sites-in-january-2024
MFA_HIGH_ADALYTICS_2024: list[tuple[str, str]] = [
    ("wealthydriver.com", "finance"),
    ("daily-stuff.com", "lifestyle"),
    ("globetip.com", "news"),
    ("heraldweekly.com", "news"),
    ("heroinvesting.com", "finance"),
    ("kueez.com", "entertainment"),
    ("lifestyle1st.com", "lifestyle"),
    ("followsports.com", "sports"),
    ("petsreporter.com", "pets"),
    ("kaleandcardio.com", "health"),
    ("livestly.com", "lifestyle"),
    ("sciencepicker.com", "science"),
    ("smartworldmag.com", "technology"),
    ("travelroo.com", "travel"),
    ("worthly.com", "lifestyle"),
    ("moneytreestudio.com", "finance"),
    ("natureworldtoday.com", "nature"),
    ("travelerdoor.com", "travel"),
    ("excellenttown.com", "news"),
    ("sizzify.com", "entertainment"),
    ("za.investing.com", "finance"),
    ("go.reference.com", "reference"),
]

# Additional MFA-style domains cited in Pixalate Q1 2024 MFA report and industry coverage.
MFA_HIGH_INDUSTRY: list[tuple[str, str]] = [
    ("iwastesomuchmoney.com", "shopping"),
    ("thesportsdrop.com", "sports"),
    ("worldemand.com", "entertainment"),
    ("shareably.net", "entertainment"),
    ("parentingisnteasy.co", "parenting"),
    ("icepop.com", "entertainment"),
    ("bonvoyaged.com", "travel"),
    ("cookingpanda.com", "food"),
    ("giveitlove.com", "lifestyle"),
    ("alwayspets.com", "pets"),
    ("playsstar.com", "entertainment"),
    ("novelodge.com", "lifestyle"),
    ("yourdailylama.com", "entertainment"),
    ("yourdailydish.com", "food"),
    ("dailyforest.com", "nature"),
    ("foodisinthehouse.com", "food"),
    ("twentytwowords.com", "entertainment"),
    ("relieved.co", "health"),
    ("seeitlive.co", "entertainment"),
    ("sportinal.com", "sports"),
    ("vitaminews.com", "health"),
    ("gloriousa.com", "entertainment"),
    ("journalistate.com", "news"),
    ("historydaily.org", "history"),
    ("thefashionball.com", "fashion"),
    ("hightally.com", "entertainment"),
]

# Borderline / page-section MFA patterns on otherwise legitimate parent domains.
MFA_MEDIUM: list[tuple[str, str, str]] = [
    ("www.forbes.com", "business", "Legitimate main domain; contrast with historical www3 MFA subdomain patterns"),
    ("www.investing.com", "finance", "Main domain; contrast with za.investing.com MFA subdomain"),
    ("www.reference.com", "reference", "Main domain; contrast with go.reference.com MFA subdomain"),
]

# Established legitimate publishers — Non_MFA gold labels for training negatives.
NON_MFA_PUBLISHERS: list[tuple[str, str]] = [
    # News — national / international
    ("nytimes.com", "news"),
    ("washingtonpost.com", "news"),
    ("wsj.com", "news"),
    ("ft.com", "news"),
    ("bbc.co.uk", "news"),
    ("bbc.com", "news"),
    ("theguardian.com", "news"),
    ("reuters.com", "news"),
    ("apnews.com", "news"),
    ("npr.org", "news"),
    ("pbs.org", "news"),
    ("economist.com", "news"),
    ("bloomberg.com", "news"),
    ("cnbc.com", "news"),
    ("aljazeera.com", "news"),
    ("time.com", "news"),
    ("theatlantic.com", "news"),
    ("newyorker.com", "news"),
    ("politico.com", "news"),
    ("axios.com", "news"),
    ("propublica.org", "news"),
    ("latimes.com", "news"),
    ("chicagotribune.com", "news"),
    ("sfchronicle.com", "news"),
    ("bostonglobe.com", "news"),
    ("independent.co.uk", "news"),
    ("telegraph.co.uk", "news"),
    ("dailymail.co.uk", "news"),
    ("scmp.com", "news"),
    ("straitstimes.com", "news"),
    ("hindustantimes.com", "news"),
    ("thehindu.com", "news"),
    ("japantimes.co.jp", "news"),
    ("lemonde.fr", "news"),
    ("spiegel.de", "news"),
    ("elpais.com", "news"),
    # Technology
    ("wired.com", "technology"),
    ("arstechnica.com", "technology"),
    ("techcrunch.com", "technology"),
    ("theverge.com", "technology"),
    ("engadget.com", "technology"),
    ("cnet.com", "technology"),
    ("zdnet.com", "technology"),
    ("tomshardware.com", "technology"),
    ("anandtech.com", "technology"),
    ("theregister.com", "technology"),
    ("infoq.com", "technology"),
    ("oreilly.com", "technology"),
    # Business / finance (editorial)
    ("marketwatch.com", "finance"),
    ("fortune.com", "business"),
    ("businessinsider.com", "business"),
    ("hbr.org", "business"),
    ("fastcompany.com", "business"),
    ("inc.com", "business"),
    ("seekingalpha.com", "finance"),
    ("morningstar.com", "finance"),
    # Sports
    ("espn.com", "sports"),
    ("sports.yahoo.com", "sports"),
    ("bleacherreport.com", "sports"),
    ("theathletic.com", "sports"),
    ("skysports.com", "sports"),
    ("nba.com", "sports"),
    ("nfl.com", "sports"),
    ("mlb.com", "sports"),
    # Science / health (editorial)
    ("nature.com", "science"),
    ("science.org", "science"),
    ("scientificamerican.com", "science"),
    ("newscientist.com", "science"),
    ("statnews.com", "health"),
    ("healthline.com", "health"),
    ("mayoclinic.org", "health"),
    ("webmd.com", "health"),
    ("nih.gov", "health"),
    ("cdc.gov", "health"),
    # Lifestyle / culture (legitimate)
    ("vogue.com", "fashion"),
    ("bonappetit.com", "food"),
    ("seriouseats.com", "food"),
    ("foodnetwork.com", "food"),
    ("nationalgeographic.com", "nature"),
    ("smithsonianmag.com", "culture"),
    ("mentalfloss.com", "culture"),
    # Education / reference
    ("wikipedia.org", "reference"),
    ("britannica.com", "reference"),
    ("khanacademy.org", "education"),
    ("mit.edu", "education"),
    ("stanford.edu", "education"),
    ("harvard.edu", "education"),
    # Entertainment (legitimate)
    ("variety.com", "entertainment"),
    ("hollywoodreporter.com", "entertainment"),
    ("deadline.com", "entertainment"),
    ("ign.com", "entertainment"),
    ("gamespot.com", "entertainment"),
    ("polygon.com", "entertainment"),
    # Regional / local
    ("seattletimes.com", "news"),
    ("denverpost.com", "news"),
    ("miamiherald.com", "news"),
    ("dallasnews.com", "news"),
    ("philly.com", "news"),
    ("startribune.com", "news"),
    ("oregonlive.com", "news"),
    # Automotive (editorial)
    ("caranddriver.com", "automotive"),
    ("motortrend.com", "automotive"),
    ("edmunds.com", "automotive"),
    # Travel (editorial)
    ("lonelyplanet.com", "travel"),
    ("cntraveler.com", "travel"),
    ("afar.com", "travel"),
    ("tripadvisor.com", "travel"),
    # Parenting (legitimate)
    ("parents.com", "parenting"),
    ("babycenter.com", "parenting"),
    ("whattoexpect.com", "parenting"),
]

# Stable section/category paths per vertical for page-section granularity.
SECTION_PATHS: dict[str, list[str]] = {
    "news": ["/", "/world/", "/politics/", "/business/", "/technology/", "/us/"],
    "finance": ["/", "/markets/", "/investing/", "/personal-finance/", "/news/"],
    "technology": ["/", "/reviews/", "/news/", "/features/", "/how-to/"],
    "sports": ["/", "/nba/", "/nfl/", "/soccer/", "/mlb/", "/news/"],
    "entertainment": ["/", "/movies/", "/tv/", "/music/", "/celebrity/"],
    "lifestyle": ["/", "/health/", "/relationships/", "/home/", "/beauty/"],
    "travel": ["/", "/destinations/", "/hotels/", "/tips/", "/guides/"],
    "food": ["/", "/recipes/", "/restaurants/", "/cooking/", "/healthy-eating/"],
    "health": ["/", "/conditions/", "/wellness/", "/nutrition/", "/fitness/"],
    "science": ["/", "/biology/", "/physics/", "/space/", "/environment/"],
    "nature": ["/", "/animals/", "/environment/", "/science/", "/photography/"],
    "pets": ["/", "/dogs/", "/cats/", "/care/", "/training/"],
    "parenting": ["/", "/baby/", "/toddler/", "/family/", "/pregnancy/"],
    "shopping": ["/", "/deals/", "/products/", "/reviews/", "/guides/"],
    "fashion": ["/", "/trends/", "/style/", "/runway/", "/beauty/"],
    "history": ["/", "/world-war-ii/", "/ancient/", "/medieval/", "/modern/"],
    "reference": ["/", "/world/", "/science/", "/history/", "/dictionary/"],
    "business": ["/", "/leadership/", "/strategy/", "/innovation/", "/markets/"],
    "culture": ["/", "/history/", "/science/", "/arts/", "/travel/"],
    "education": ["/", "/courses/", "/research/", "/admissions/", "/news/"],
    "automotive": ["/", "/reviews/", "/news/", "/buying-guide/", "/electric/"],
}

# Article-style slugs typical of MFA clickbait vs editorial.
MFA_ARTICLE_SLUGS = [
    "/article/you-wont-believe-what-happened-next/",
    "/news/shocking-celebrity-transformation-revealed/",
    "/story/91-year-old-gets-revenge-on-bikers/",
    "/slideshow/celebrity-photos-recreated/",
    "/gallery/amazing-homes-you-must-see/",
    "/list/17-things-nobody-told-you/",
    "/viral/woman-finds-secret-in-attic/",
    "/trivia/can-you-pass-this-quiz/",
    "/life/hilarious-moments-caught-on-camera/",
    "/trending/what-doctors-dont-want-you-to-know/",
]

EDITORIAL_ARTICLE_SLUGS = [
    "/2024/06/15/global-markets-rally-on-inflation-data/",
    "/article/climate-summit-agreement-analysis/",
    "/story/local-election-results-mayor-race/",
    "/news/technology-ai-regulation-debate/",
    "/features/investigation-supply-chain-ethics/",
    "/opinion/editorial-democracy-and-media/",
    "/science/new-study-biodiversity-decline/",
    "/sports/championship-finals-recap/",
    "/health/public-health-vaccination-campaign/",
    "/business/earnings-report-quarterly-results/",
]


@dataclass
class GoldLabelRecord:
    record_id: str
    url: str
    domain: str
    gold_label: str
    label_source: str
    label_confidence: str
    page_type: str
    content_category: str
    notes: str
    source_batch_id: str
    created_at: str


def normalize_url_id(url: str) -> str:
    """Stable url_id hash for deduplication (matches planned ingestion convention)."""
    parsed = urlparse(url.lower().rstrip("/"))
    canonical = f"{parsed.scheme or 'https'}://{parsed.netloc}{parsed.path}"
    if parsed.query:
        canonical += f"?{parsed.query}"
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def make_record_id(url: str) -> str:
    return f"gl_{normalize_url_id(url)}"


def _paths_for_category(category: str) -> list[str]:
    return SECTION_PATHS.get(category, SECTION_PATHS["news"])


def _expand_domain_urls(
    domain: str,
    category: str,
    gold_label: str,
    label_source: str,
    label_confidence: str,
    notes: str,
    *,
    article_slugs: list[str],
    max_per_domain: int = 5,
) -> list[GoldLabelRecord]:
    records: list[GoldLabelRecord] = []
    paths = _paths_for_category(category)[:3]
    paths.extend(article_slugs[: max_per_domain - len(paths)])

    for path in paths[:max_per_domain]:
        url = f"https://{domain}{path}"
        page_type = "article" if "/article/" in path or "/story/" in path or "/202" in path else (
            "homepage" if path == "/" else "category"
        )
        if "/slideshow/" in path or "/gallery/" in path:
            page_type = "slideshow"

        records.append(
            GoldLabelRecord(
                record_id=make_record_id(url),
                url=url,
                domain=domain,
                gold_label=gold_label,
                label_source=label_source,
                label_confidence=label_confidence,
                page_type=page_type,
                content_category=category,
                notes=notes,
                source_batch_id=SOURCE_BATCH_ID,
                created_at=CREATED_AT,
            )
        )
    return records


def build_records() -> list[GoldLabelRecord]:
    records: list[GoldLabelRecord] = []

    for domain, category in MFA_HIGH_ADALYTICS_2024:
        records.extend(
            _expand_domain_urls(
                domain,
                category,
                "MFA_High",
                "adalytics_2024_jounce_deepsee",
                "high",
                "Confirmed MFA per Adalytics Jan 2024 study (ANA/WFA/ISBA/4A's + Jounce + DeepSee.io)",
                article_slugs=MFA_ARTICLE_SLUGS,
                max_per_domain=4,
            )
        )

    for domain, category in MFA_HIGH_INDUSTRY:
        label_source = "pixalate_2024_industry_research"
        notes = "Cited in Pixalate Q1 2024 MFA report or industry MFA coverage"
        records.extend(
            _expand_domain_urls(
                domain,
                category,
                "MFA_High",
                label_source,
                "high",
                notes,
                article_slugs=MFA_ARTICLE_SLUGS,
                max_per_domain=3,
            )
        )

    for domain, category, note in MFA_MEDIUM:
        records.extend(
            _expand_domain_urls(
                domain,
                category,
                "Non_MFA",
                "ad_ops_contrast_set",
                "high",
                note,
                article_slugs=EDITORIAL_ARTICLE_SLUGS,
                max_per_domain=3,
            )
        )

    for domain, category in NON_MFA_PUBLISHERS:
        records.extend(
            _expand_domain_urls(
                domain,
                category,
                "Non_MFA",
                "editorial_publisher_allowlist",
                "high",
                "Established editorial publisher; legitimate ad inventory baseline",
                article_slugs=EDITORIAL_ARTICLE_SLUGS,
                max_per_domain=4,
            )
        )

    # Deduplicate by record_id preserving first occurrence
    seen: set[str] = set()
    unique: list[GoldLabelRecord] = []
    for rec in records:
        if rec.record_id in seen:
            continue
        seen.add(rec.record_id)
        unique.append(rec)
    return unique


def validate_records(records: list[GoldLabelRecord]) -> list[str]:
    errors: list[str] = []
    valid_labels = {"MFA_High", "MFA_Medium", "MFA_Low", "Non_MFA", "Uncertain"}
    url_pattern = re.compile(r"^https://[a-zA-Z0-9][-a-zA-Z0-9.]*[a-zA-Z0-9](/.*)?$")

    ids: set[str] = set()
    urls: set[str] = set()
    for i, rec in enumerate(records):
        if rec.gold_label not in valid_labels:
            errors.append(f"Row {i}: invalid gold_label {rec.gold_label}")
        if not url_pattern.match(rec.url):
            errors.append(f"Row {i}: invalid URL {rec.url}")
        if rec.record_id in ids:
            errors.append(f"Duplicate record_id: {rec.record_id}")
        ids.add(rec.record_id)
        if rec.url in urls:
            errors.append(f"Duplicate url: {rec.url}")
        urls.add(rec.url)

    label_counts: dict[str, int] = {}
    for rec in records:
        label_counts[rec.gold_label] = label_counts.get(rec.gold_label, 0) + 1

    if len(records) < 100:
        errors.append(f"Dataset has only {len(records)} records; minimum is 100")
    if label_counts.get("MFA_High", 0) < 50:
        errors.append("Insufficient MFA_High records (need >= 50)")
    if label_counts.get("Non_MFA", 0) < 50:
        errors.append("Insufficient Non_MFA records (need >= 50)")

    return errors


def write_outputs(records: list[GoldLabelRecord]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    csv_path = OUTPUT_DIR / "gold_labels.csv"
    jsonl_path = OUTPUT_DIR / "gold_labels.jsonl"
    manifest_path = OUTPUT_DIR / "manifest.json"

    fieldnames = list(asdict(records[0]).keys()) if records else []
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for rec in records:
            writer.writerow(asdict(rec))

    with jsonl_path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(asdict(rec), ensure_ascii=False) + "\n")

    label_counts: dict[str, int] = {}
    domain_counts: dict[str, int] = {}
    for rec in records:
        label_counts[rec.gold_label] = label_counts.get(rec.gold_label, 0) + 1
        domain_counts[rec.domain] = domain_counts.get(rec.domain, 0) + 1

    manifest = {
        "dataset": "gold_labels",
        "version": SOURCE_BATCH_ID,
        "created_at": CREATED_AT,
        "record_count": len(records),
        "unique_domains": len(domain_counts),
        "label_distribution": label_counts,
        "files": {
            "csv": "gold_labels.csv",
            "jsonl": "gold_labels.jsonl",
            "schema": "schema/gold_label_record.schema.json",
        },
        "sources": [
            "Adalytics (Jan 2024) — ANA/WFA/ISBA/4A's MFA definition + Jounce/DeepSee confirmation",
            "Pixalate Q1 2024 MFA Websites Ad Spend Report",
            "Industry MFA coverage (ExchangeWire, AdExchanger, Campaign US)",
            "Editorial publisher allowlist (established news, tech, sports, health publishers)",
        ],
        "caveats": [
            "MFA classifications change daily; re-validate with Ad Ops before production blocking",
            "Some URLs use representative article paths; verify reachability before crawl jobs",
            "Contrast-set entries (forbes.com, investing.com, reference.com) are Non_MFA main domains",
        ],
    }
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    print(f"Wrote {len(records)} records to {OUTPUT_DIR}")
    print(f"  Label distribution: {label_counts}")
    print(f"  Unique domains: {len(domain_counts)}")


def main() -> None:
    records = build_records()
    errors = validate_records(records)
    if errors:
        for err in errors:
            print(f"ERROR: {err}")
        raise SystemExit(1)
    write_outputs(records)


if __name__ == "__main__":
    main()
