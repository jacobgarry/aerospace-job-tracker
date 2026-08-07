from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config.yml"
SEEN_PATH = ROOT / "data" / "seen_jobs.json"
LATEST_REPORT = ROOT / "reports" / "latest.md"
NEW_JOBS_JSON = ROOT / "data" / "new_jobs.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; AerospaceJobTracker/1.0; "
        "+https://github.com/)"
    )
}


@dataclass(frozen=True)
class Job:
    company: str
    title: str
    url: str
    source_url: str

    @property
    def key(self) -> str:
        normalized = f"{self.company}|{self.title}|{self.url}".lower().strip()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def is_http_url(url: str) -> bool:
    return urlparse(url).scheme in {"http", "https"}


def keyword_match(text: str, include: list[str], exclude: list[str]) -> bool:
    haystack = text.lower()
    return any(term.lower() in haystack for term in include) and not any(
        term.lower() in haystack for term in exclude
    )


def extract_jobs(
    company: str,
    source_url: str,
    html: str,
    include: list[str],
    exclude: list[str],
    limit: int,
) -> list[Job]:
    soup = BeautifulSoup(html, "html.parser")
    jobs: dict[str, Job] = {}

    for anchor in soup.find_all("a", href=True):
        title = normalize_space(anchor.get_text(" ", strip=True))
        href = urljoin(source_url, anchor["href"])
        if not title or len(title) < 4 or not is_http_url(href):
            continue

        context = title
        parent = anchor.find_parent(["li", "article", "div"])
        if parent:
            context = normalize_space(parent.get_text(" ", strip=True))[:800]

        if not keyword_match(context, include, exclude):
            continue

        job = Job(company=company, title=title[:180], url=href, source_url=source_url)
        jobs[job.key] = job
        if len(jobs) >= limit:
            break

    return list(jobs.values())


def load_seen() -> dict[str, dict]:
    if not SEEN_PATH.exists():
        return {}
    try:
        return json.loads(SEEN_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def write_report(all_jobs: list[Job], new_jobs: list[Job], errors: list[str]) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Aerospace Job Tracker — Latest Run",
        "",
        f"Generated: **{now}**",
        f"",
        f"Matched listings found: **{len(all_jobs)}**  ",
        f"New listings since the previous successful run: **{len(new_jobs)}**",
        "",
    ]

    if new_jobs:
        lines.extend(["## New Matches", ""])
        for job in sorted(new_jobs, key=lambda item: (item.company, item.title)):
            lines.append(f"- **{job.company} — {job.title}**  ")
            lines.append(f"  [Open application]({job.url})")
        lines.append("")
    else:
        lines.extend(["## New Matches", "", "No new matching links were detected.", ""])

    if errors:
        lines.extend(["## Sources Needing Attention", ""])
        lines.extend(f"- {error}" for error in errors)
        lines.append("")

    lines.extend(
        [
            "## Notes",
            "",
            "Career sites frequently change or block automated requests. A source error does not necessarily mean the employer has no openings. Update `config.yml` with a more specific employer search URL when needed.",
            "",
        ]
    )
    LATEST_REPORT.parent.mkdir(parents=True, exist_ok=True)
    LATEST_REPORT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    include = config["keywords"]["include"]
    exclude = config["keywords"]["exclude"]
    timeout = int(config["settings"].get("request_timeout_seconds", 25))
    limit = int(config["settings"].get("maximum_links_per_source", 250))

    seen = load_seen()
    current_jobs: list[Job] = []
    errors: list[str] = []

    session = requests.Session()
    session.headers.update(HEADERS)

    for source in config["sources"]:
        company = source["company"]
        url = source["url"]
        try:
            response = session.get(url, timeout=timeout, allow_redirects=True)
            response.raise_for_status()
            current_jobs.extend(
                extract_jobs(company, response.url, response.text, include, exclude, limit)
            )
        except requests.RequestException as exc:
            errors.append(f"**{company}:** {type(exc).__name__} while checking `{url}`")

    deduped = {job.key: job for job in current_jobs}
    current_jobs = list(deduped.values())
    new_jobs = [job for job in current_jobs if job.key not in seen]

    now = datetime.now(timezone.utc).isoformat()
    for job in current_jobs:
        if job.key not in seen:
            seen[job.key] = {**asdict(job), "first_seen": now}
        seen[job.key]["last_seen"] = now

    SEEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    SEEN_PATH.write_text(json.dumps(seen, indent=2, sort_keys=True), encoding="utf-8")
    NEW_JOBS_JSON.write_text(
        json.dumps([asdict(job) for job in new_jobs], indent=2), encoding="utf-8"
    )
    write_report(current_jobs, new_jobs, errors)

    print(f"Found {len(current_jobs)} matching links; {len(new_jobs)} are new.")
    if errors:
        print(f"Completed with {len(errors)} source errors.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
