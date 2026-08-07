import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from job_tracker import (
    extract_jobs,
    fetch_greenhouse_jobs,
    fetch_workday_jobs,
    priority_score,
)


INCLUDE = [
    "aerospace", "mechanical engineer", "systems engineer", "controls engineer",
    "gnc", "flight test", "uas", "autonomy", "propulsion", "structural engineer",
    "integration engineer", "new grad", "entry level", "engineer i",
    "associate engineer",
]
EXCLUDE = [
    "senior", "principal", "staff engineer", "lead engineer", "manager",
    "director", "2026 early career", "intern", "internship", "co-op",
]
SOURCE = "https://example.com/careers/search-jobs"


class JobExtractionTests(unittest.TestCase):
    def extract(self, html):
        return extract_jobs("Example Aerospace", SOURCE, html, INCLUDE, EXCLUDE, 100)

    def test_accepts_real_relevant_job_details(self):
        html = """
        <a href="/jobs/1234/entry-level-gnc-engineer">Entry Level GNC Engineer</a>
        <a href="https://jobs.lever.co/example/abc">Mechanical Engineer I</a>
        <a href="/positions/55/flight-test-engineer">Flight Test Engineer</a>
        """
        self.assertEqual(3, len(self.extract(html)))

    def test_rejects_marketing_and_career_content(self):
        html = """
        <div>Aerospace engineering opportunities
          <a href="/careers">Careers</a>
          <a href="/blog/day-in-the-life">Read more</a>
          <a href="/students">Students and graduates</a>
        </div>
        <a href="/jobs">Search jobs</a>
        """
        self.assertEqual([], self.extract(html))

    def test_does_not_use_parent_marketing_copy_as_the_title(self):
        html = '<div>Build aerospace systems with us <a href="/jobs/42">Learn more</a></div>'
        self.assertEqual([], self.extract(html))

    def test_rejects_senior_and_manager_roles(self):
        html = """
        <a href="/jobs/1">Senior Propulsion Engineer</a>
        <a href="/jobs/2">Systems Engineering Manager</a>
        <a href="/jobs/3">Principal Autonomy Engineer</a>
        <a href="/jobs/4">Lead, Systems Engineer</a>
        <a href="/jobs/5">Sr. Associate Systems Engineer</a>
        <a href="/jobs/6">Mechanical Engineer II</a>
        <a href="/jobs/7">Flight Test Engineer III</a>
        """
        self.assertEqual([], self.extract(html))

    def test_engineer_i_keyword_does_not_match_engineer_ii(self):
        jobs = extract_jobs(
            "Example",
            SOURCE,
            '<a href="/jobs/1">Manufacturing Engineer II</a>',
            ["engineer i"],
            [],
            10,
        )
        self.assertEqual([], jobs)

    def test_rejects_non_engineering_jobs_with_domain_keywords(self):
        html = """
        <a href="/jobs/1">UAS Operator 3</a>
        <a href="/jobs/2">Flight Test Operator</a>
        <a href="/jobs/3">Autonomy Product Manager</a>
        """
        self.assertEqual([], self.extract(html))

    def test_rejects_internships_and_2026_starts_for_a_2027_graduate(self):
        html = """
        <a href="/jobs/1">2027 Mechanical Engineer Intern</a>
        <a href="/jobs/2">2026 Early Career Flight Test Engineer</a>
        """
        self.assertEqual([], self.extract(html))

    def test_rejects_relevant_title_without_application_url(self):
        html = '<a href="/stories/aerospace-engineer">Aerospace Engineer</a>'
        self.assertEqual([], self.extract(html))

    def test_new_grad_roles_sort_ahead_of_other_matches(self):
        self.assertGreater(priority_score("New Grad Systems Engineer"),
                           priority_score("Systems Engineer"))


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, pages):
        self.pages = iter(pages)
        self.offsets = []

    def post(self, url, json, timeout):
        self.offsets.append(json["offset"])
        return FakeResponse(next(self.pages))


class WorkdayTests(unittest.TestCase):
    def test_reads_pages_and_filters_workday_results(self):
        session = FakeSession([
            {
                "total": 3,
                "jobPostings": [
                    {"title": "Entry Level GNC Engineer", "externalPath": "/job/a/gnc_R1"},
                    {"title": "Senior Systems Engineer", "externalPath": "/job/a/systems_R2"},
                ],
            },
            {
                "total": 3,
                "jobPostings": [
                    {"title": "Mechanical Engineer I", "externalPath": "/job/b/mech_R3"},
                ],
            },
        ])
        source = {
            "company": "Example",
            "url": SOURCE,
            "api_url": "https://example.com/wday/jobs",
            "base_url": "https://example.myworkdayjobs.com/en-US/Careers/",
        }

        jobs = fetch_workday_jobs(session, source, INCLUDE, EXCLUDE, 100, 10)

        self.assertEqual([0, 2], session.offsets)
        self.assertEqual(
            ["Entry Level GNC Engineer", "Mechanical Engineer I"],
            [job.title for job in jobs],
        )


class GreenhouseSession:
    def get(self, url, timeout):
        return FakeResponse({
            "jobs": [
                {
                    "title": "2027 Early Career Flight Test Engineer",
                    "absolute_url": "https://boards.greenhouse.io/example/jobs/123",
                },
                {
                    "title": "Principal GNC Engineer",
                    "absolute_url": "https://boards.greenhouse.io/example/jobs/456",
                },
            ]
        })


class GreenhouseTests(unittest.TestCase):
    def test_filters_public_board_results(self):
        source = {
            "company": "Example",
            "url": SOURCE,
            "api_url": "https://boards-api.greenhouse.io/v1/boards/example/jobs",
        }

        jobs = fetch_greenhouse_jobs(
            GreenhouseSession(), source, INCLUDE, EXCLUDE, 100, 10
        )

        self.assertEqual(["2027 Early Career Flight Test Engineer"],
                         [job.title for job in jobs])


if __name__ == "__main__":
    unittest.main()
