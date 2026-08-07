# Aerospace Job Tracker

A lightweight Python and GitHub Actions project that checks selected aerospace and defense career pages once per week and opens a GitHub issue when it detects new entry-level or 2027-relevant engineering opportunities.

## What it does

- Runs automatically every Sunday.
- Checks the employer search pages listed in `config.yml`.
- Filters links using aerospace, GNC, flight-test, systems, controls, avionics, propulsion, embedded, autonomy, and new-graduate keywords.
- Excludes obviously senior roles.
- Remembers previously detected listings in `data/seen_jobs.json`.
- Updates `reports/latest.md` after each run.
- Opens a GitHub issue only when new matching listings are detected.

## Installation in your portfolio repository

Place this entire folder at:

```text
jacobgarry.github.io/aerospace-job-tracker/
```

The workflow path must remain at the repository root, not inside this folder. Therefore, copy:

```text
aerospace-job-tracker/.github/workflows/weekly-job-tracker.yml
```

to:

```text
jacobgarry.github.io/.github/workflows/weekly-job-tracker.yml
```

Keep the rest of the files inside `aerospace-job-tracker/`.

## First run

1. Open your repository on GitHub.
2. Select **Actions**.
3. Select **Weekly Aerospace Job Tracker**.
4. Select **Run workflow**.
5. After it finishes, open `aerospace-job-tracker/reports/latest.md`.

## Customize the search

Edit `config.yml`.

The most effective source URL is a specific search-results page with filters already applied, such as entry-level engineering roles in the United States. Replace generic career homepages with those filtered URLs whenever possible.

Add companies using:

```yaml
sources:
  - company: Example Aerospace
    url: https://example.com/careers/search?keyword=engineer
```

Adjust matching terms under `keywords.include` and `keywords.exclude`.

## Notifications

GitHub will notify you when the workflow opens an issue, provided repository issue notifications are enabled. This avoids storing email passwords or third-party API keys.

## Important limitation

Some career sites render listings entirely with JavaScript or block automated requests. Those sources may appear under **Sources Needing Attention** in the report. In that case, use a more specific public search URL or add a dedicated API adapter for that employer.
