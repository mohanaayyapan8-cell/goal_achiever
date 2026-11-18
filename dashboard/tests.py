from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class HomePageTests(TestCase):
    def test_home_page_loads_for_visitors(self):
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "GOAL ACHIEVER")
        self.assertContains(response, reverse("accounts:register"))

    def test_home_lists_all_ten_phases(self):
        response = self.client.get(reverse("dashboard:home"))
        for n in range(1, 11):
            self.assertContains(response, f"Phase {n}")

    def test_logged_in_user_goes_to_dashboard(self):
        user = get_user_model().objects.create_user("x", "x@example.com", "StrongPass#2026")
        self.client.force_login(user)
        self.assertRedirects(self.client.get(reverse("dashboard:home")), reverse("dashboard:index"))


class DashboardTests(TestCase):
    def test_dashboard_greets_user_by_name(self):
        user = get_user_model().objects.create_user("x", "x@example.com", "StrongPass#2026", first_name="Priya")
        self.client.force_login(user)
        response = self.client.get(reverse("dashboard:index"))
        self.assertContains(response, "Priya")
