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
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/127.0 Safari/537.36"
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

    def contains(term: str) -> bool:
        escaped = re.escape(term.lower())
        prefix = r"(?<!\w)" if term and term[0].isalnum() else ""
        suffix = r"(?!\w)" if term and term[-1].isalnum() else ""
        return bool(re.search(f"{prefix}{escaped}{suffix}", haystack))

    return any(contains(term) for term in include) and not any(
        contains(term) for term in exclude
    )


JOB_HOSTS = (
    "boards.greenhouse.io", "job-boards.greenhouse.io", "jobs.lever.co",
    "myworkdayjobs.com", "smartrecruiters.com", "icims.com", "ashbyhq.com",
)
JOB_URL_RE = re.compile(
    r"(?:^|/)(?:job|jobs|position|positions|opening|openings|role|roles|"
    r"requisition|req)(?:/|-|$)|[?&](?:job_?id|gh_jid|req_?id|requisitionid)=",
    re.IGNORECASE,
)
NON_JOB_TITLE_RE = re.compile(
    r"\b(?:opportunities|join (?:our|the) team|search|learn more|"
    r"read more|view all|students?|internships?|benefits|culture|life at|"
    r"talent community|job alerts?|engineering careers?)\b",
    re.IGNORECASE,
)
NON_JOB_URL_RE = re.compile(
    r"(?:/blog/|/news/|/stories/|/article/|/events?/|/benefits/|/culture/|"
    r"/about/|/contact/|/students?/|/talent-community|/job-alerts?)",
    re.IGNORECASE,
)
ENGINEERING_ROLE_RE = re.compile(
    r"\b(?:engineer(?:ing)?|aerodynamicist|flight sciences?)\b", re.IGNORECASE
)
SENIORITY_RE = re.compile(
    r"\b(?:sr\.?|senior|principal|staff|lead|chief|manager|director|"
    r"head|vice president|vp|engineer(?:ing)?\s+(?:ii|iii|iv|v|[2-9]))\b",
    re.IGNORECASE,
)


def is_job_detail_url(url: str, source_url: str) -> bool:
    """Require a detail-page-shaped URL, not a careers/search/content page."""
    parsed = urlparse(url)
    if NON_JOB_URL_RE.search(parsed.path) or url.rstrip("/") == source_url.rstrip("/"):
        return False
    host = parsed.netloc.lower()
    if any(job_host in host for job_host in JOB_HOSTS):
        return len([part for part in parsed.path.split("/") if part]) >= 2
    return bool(JOB_URL_RE.search(f"{parsed.path}?{parsed.query}"))


def is_relevant_job_title(title: str, include: list[str], exclude: list[str]) -> bool:
    """Classify the link title; surrounding marketing copy is not job evidence."""
    normalized = normalize_space(title).lower()
    return (
        bool(ENGINEERING_ROLE_RE.search(normalized))
        and not NON_JOB_TITLE_RE.search(normalized)
        and not SENIORITY_RE.search(normalized)
        and keyword_match(normalized, include, exclude)
    )


def priority_score(title: str) -> int:
    """Put explicit early-career roles first, followed by target disciplines."""
    value = title.lower()
    score = 0
    if re.search(r"\b(?:new grad(?:uate)?|entry[ -]level|early career|engineer i|"
                 r"associate engineer|university grad(?:uate)?|rotational)\b", value):
        score += 100
    priorities = (
        "aerospace", "mechanical", "systems", "controls", "gnc", "guidance",
        "navigation", "flight test", "uas", "uav", "autonomy", "propulsion",
        "structures", "structural", "integration",
    )
    score += 10 * sum(term in value for term in priorities)
    return score


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

        if not is_relevant_job_title(title, include, exclude):
            continue
        if not is_job_detail_url(href, source_url):
            continue

        job = Job(company=company, title=title[:180], url=href, source_url=source_url)
        jobs[job.key] = job
        if len(jobs) >= limit:
            break

    return list(jobs.values())


def fetch_workday_jobs(
    session: requests.Session,
    source: dict,
    include: list[str],
    exclude: list[str],
    limit: int,
    timeout: int,
) -> list[Job]:
    """Read a public Workday job feed instead of a branded, bot-blocked page."""
    jobs: dict[str, Job] = {}
    offset = 0
    page_size = 20  # Workday rejects larger page sizes.

    while offset < limit:
        response = session.post(
            source["api_url"],
            json={
                "appliedFacets": {},
                "limit": page_size,
                "offset": offset,
                "searchText": "",
            },
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        postings = payload.get("jobPostings", [])
        if not postings:
            break

        for posting in postings:
            title = normalize_space(str(posting.get("title", "")))
            path = str(posting.get("externalPath", ""))
            url = urljoin(source["base_url"], path)
            if not title or not is_relevant_job_title(title, include, exclude):
                continue
            if not is_job_detail_url(url, source["url"]):
                continue
            job = Job(
                company=source["company"],
                title=title[:180],
                url=url,
                source_url=source["url"],
            )
            jobs[job.key] = job

        offset += len(postings)
        total = min(int(payload.get("total", offset)), limit)
        if offset >= total:
            break

    return list(jobs.values())


def fetch_greenhouse_jobs(
    session: requests.Session,
    source: dict,
    include: list[str],
    exclude: list[str],
    limit: int,
    timeout: int,
) -> list[Job]:
    """Read titles and application URLs from a public Greenhouse board feed."""
    response = session.get(source["api_url"], timeout=timeout)
    response.raise_for_status()
    jobs: dict[str, Job] = {}
    for posting in response.json().get("jobs", [])[:limit]:
        title = normalize_space(str(posting.get("title", "")))
        url = str(posting.get("absolute_url", ""))
        if not title or not is_relevant_job_title(title, include, exclude):
            continue
        if not is_job_detail_url(url, source["url"]):
            continue
        job = Job(
            company=source["company"],
            title=title[:180],
            url=url,
            source_url=source["url"],
        )
        jobs[job.key] = job
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
        for job in sorted(
            new_jobs,
            key=lambda item: (-priority_score(item.title), item.company, item.title),
        ):
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
            if source.get("adapter") == "workday":
                current_jobs.extend(
                    fetch_workday_jobs(
                        session, source, include, exclude, limit, timeout
                    )
                )
            elif source.get("adapter") == "greenhouse":
                current_jobs.extend(
                    fetch_greenhouse_jobs(
                        session, source, include, exclude, limit, timeout
                    )
                )
            else:
                response = session.get(url, timeout=timeout, allow_redirects=True)
                response.raise_for_status()
                current_jobs.extend(
                    extract_jobs(
                        company, response.url, response.text, include, exclude, limit
                    )
                )
        except (requests.RequestException, ValueError) as exc:
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
