import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from job_tracker import extract_jobs, priority_score


INCLUDE = [
    "aerospace", "mechanical engineer", "systems engineer", "controls engineer",
    "gnc", "flight test", "uas", "autonomy", "propulsion", "structural engineer",
    "integration engineer", "new grad", "entry level", "engineer i",
    "associate engineer",
]
EXCLUDE = ["senior", "principal", "staff engineer", "lead engineer", "manager", "director"]
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
        """
        self.assertEqual([], self.extract(html))

    def test_rejects_non_engineering_jobs_with_domain_keywords(self):
        html = """
        <a href="/jobs/1">UAS Operator 3</a>
        <a href="/jobs/2">Flight Test Operator</a>
        <a href="/jobs/3">Autonomy Product Manager</a>
        """
        self.assertEqual([], self.extract(html))

    def test_rejects_relevant_title_without_application_url(self):
        html = '<a href="/stories/aerospace-engineer">Aerospace Engineer</a>'
        self.assertEqual([], self.extract(html))

    def test_new_grad_roles_sort_ahead_of_other_matches(self):
        self.assertGreater(priority_score("New Grad Systems Engineer"),
                           priority_score("Systems Engineer"))


if __name__ == "__main__":
    unittest.main()
