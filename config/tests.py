from django.apps import apps
from django.conf import settings
from django.test import SimpleTestCase

EXPECTED_APPS = [
    "accounts", "dashboard", "learning", "planner", "assessments",
    "aptitude", "coding", "streaks", "resume_builder", "notifications",
]


class ProjectSetupTests(SimpleTestCase):
    def test_all_project_apps_installed(self):
        for name in EXPECTED_APPS:
            self.assertTrue(apps.is_installed(name), f"{name} is not installed")

    def test_timezone_support_enabled(self):
        self.assertTrue(settings.USE_TZ)

    def test_media_is_not_under_static(self):
        # Private resumes must never be publicly served.
        self.assertNotIn("static", str(settings.MEDIA_ROOT))
