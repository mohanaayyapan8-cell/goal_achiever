import re
from datetime import datetime, timezone as dt_timezone

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import UserProfile
from .utils import get_user_today

User = get_user_model()

REGISTER_DATA = {
    "username": "asha", "first_name": "Asha", "email": "asha@example.com",
    "password1": "StrongPass#2026", "password2": "StrongPass#2026",
}


def make_user(username="u1", email=None, password="StrongPass#2026"):
    return User.objects.create_user(username, email or f"{username}@example.com", password, first_name=username.title())


class ModelTests(TestCase):
    def test_profile_created_automatically(self):
        user = make_user()
        self.assertTrue(UserProfile.objects.filter(user=user).exists())
        self.assertEqual(user.profile.timezone, "Asia/Kolkata")

    def test_superuser_also_gets_profile(self):
        admin = User.objects.create_superuser("boss", "boss@example.com", "StrongPass#2026")
        self.assertTrue(hasattr(admin, "profile"))

    def test_deleting_user_deletes_profile(self):
        user = make_user()
        user.delete()
        self.assertEqual(UserProfile.objects.count(), 0)

    def test_invalid_timezone_fails_validation(self):
        user = make_user()
        user.profile.timezone = "Mars/Olympus"
        with self.assertRaises(Exception):
            user.profile.full_clean()


class RegistrationTests(TestCase):
    def test_register_page_loads(self):
        self.assertEqual(self.client.get(reverse("accounts:register")).status_code, 200)

    def test_successful_registration_logs_user_in(self):
        response = self.client.post(reverse("accounts:register"), REGISTER_DATA)
        self.assertRedirects(response, reverse("dashboard:index"))
        user = User.objects.get(username="asha")
        self.assertEqual(user.email, "asha@example.com")
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)
        self.assertTrue(UserProfile.objects.filter(user=user).exists())

    def test_duplicate_email_rejected_case_insensitive(self):
        make_user("first", email="asha@example.com")
        data = {**REGISTER_DATA, "email": "ASHA@Example.com"}
        response = self.client.post(reverse("accounts:register"), data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already exists")
        self.assertFalse(User.objects.filter(username="asha").exists())

    def test_password_mismatch_rejected(self):
        response = self.client.post(reverse("accounts:register"), {**REGISTER_DATA, "password2": "different"})
        self.assertFalse(User.objects.filter(username="asha").exists())
        self.assertEqual(response.status_code, 200)

    def test_weak_password_rejected(self):
        data = {**REGISTER_DATA, "password1": "12345678", "password2": "12345678"}
        self.client.post(reverse("accounts:register"), data)
        self.assertFalse(User.objects.filter(username="asha").exists())

    def test_missing_email_rejected(self):
        self.client.post(reverse("accounts:register"), {**REGISTER_DATA, "email": ""})
        self.assertFalse(User.objects.filter(username="asha").exists())

    def test_logged_in_user_redirected_from_register(self):
        self.client.force_login(make_user())
        self.assertRedirects(self.client.get(reverse("accounts:register")), reverse("dashboard:index"))


class LoginLogoutTests(TestCase):
    def setUp(self):
        self.user = make_user("ravi")

    def test_login_success(self):
        response = self.client.post(reverse("accounts:login"), {"username": "ravi", "password": "StrongPass#2026"})
        self.assertRedirects(response, reverse("dashboard:index"))

    def test_login_wrong_password(self):
        response = self.client.post(reverse("accounts:login"), {"username": "ravi", "password": "nope"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_requires_post_and_logs_out(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(response, reverse("dashboard:home"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_next_redirect_back(self):
        url = reverse("accounts:login") + "?next=" + reverse("accounts:profile")
        response = self.client.post(url, {"username": "ravi", "password": "StrongPass#2026",
                                          "next": reverse("accounts:profile")})
        self.assertRedirects(response, reverse("accounts:profile"))

    def test_login_does_not_redirect_to_external_site(self):
        response = self.client.post(reverse("accounts:login"), {
            "username": "ravi", "password": "StrongPass#2026", "next": "https://evil.example.com/"})
        self.assertRedirects(response, reverse("dashboard:index"))


class PermissionTests(TestCase):
    """Pages that need a login must send visitors to the login page."""

    def test_protected_pages_redirect_anonymous(self):
        for name in ("dashboard:index", "accounts:profile", "accounts:profile_edit", "accounts:password_change"):
            url = reverse(name)
            response = self.client.get(url)
            self.assertRedirects(response, f"{reverse('accounts:login')}?next={url}", msg_prefix=name)

    def test_profile_page_shows_only_own_data(self):
        alice, bob = make_user("alice"), make_user("bob")
        alice.profile.college = "Alice College"; alice.profile.save()
        bob.profile.college = "Bob Institute"; bob.profile.save()
        self.client.force_login(alice)
        response = self.client.get(reverse("accounts:profile"))
        self.assertContains(response, "Alice College")
        self.assertNotContains(response, "Bob Institute")
        self.assertNotContains(response, "bob@example.com")

    def test_edit_changes_only_own_profile(self):
        alice, bob = make_user("alice"), make_user("bob")
        self.client.force_login(alice)
        self.client.post(reverse("accounts:profile_edit"), {
            "first_name": "Alice", "last_name": "", "email": "alice@example.com",
            "timezone": "Asia/Kolkata", "college": "Changed", "target_role": "", "bio": ""})
        bob.profile.refresh_from_db()
        self.assertEqual(bob.profile.college, "")
        alice.profile.refresh_from_db()
        self.assertEqual(alice.profile.college, "Changed")


class ProfileEditTests(TestCase):
    def setUp(self):
        self.user = make_user("meena")
        self.client.force_login(self.user)
        self.url = reverse("accounts:profile_edit")
        self.base = {"first_name": "Meena", "last_name": "K", "email": "meena@example.com",
                     "timezone": "Asia/Kolkata", "college": "", "target_role": "", "bio": ""}

    def test_edit_page_loads(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_update_saves_everything(self):
        data = {**self.base, "college": "NIT Trichy", "target_role": "Data Analyst",
                "timezone": "America/New_York", "daily_reminder_time": "07:30", "email_reminders": "on"}
        self.assertRedirects(self.client.post(self.url, data), reverse("accounts:profile"))
        self.user.refresh_from_db()
        p = self.user.profile
        self.assertEqual((p.college, p.target_role, p.timezone), ("NIT Trichy", "Data Analyst", "America/New_York"))
        self.assertTrue(p.email_reminders)
        self.assertEqual(p.daily_reminder_time.strftime("%H:%M"), "07:30")
        self.assertEqual(self.user.last_name, "K")

    def test_invalid_timezone_rejected(self):
        response = self.client.post(self.url, {**self.base, "timezone": "Mars/Olympus"})
        self.assertEqual(response.status_code, 200)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.timezone, "Asia/Kolkata")

    def test_cannot_take_another_users_email(self):
        make_user("other", email="taken@example.com")
        response = self.client.post(self.url, {**self.base, "email": "TAKEN@example.com"})
        self.assertContains(response, "already exists")

    def test_can_keep_own_email(self):
        self.assertRedirects(self.client.post(self.url, self.base), reverse("accounts:profile"))


class PasswordTests(TestCase):
    def setUp(self):
        self.user = make_user("kiran", email="kiran@example.com")

    def test_password_change(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("accounts:password_change"), {
            "old_password": "StrongPass#2026", "new_password1": "BrandNew#Pass77", "new_password2": "BrandNew#Pass77"})
        self.assertRedirects(response, reverse("accounts:profile"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("BrandNew#Pass77"))

    def test_password_change_wrong_old_password(self):
        self.client.force_login(self.user)
        self.client.post(reverse("accounts:password_change"), {
            "old_password": "wrong", "new_password1": "BrandNew#Pass77", "new_password2": "BrandNew#Pass77"})
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("StrongPass#2026"))

    def test_full_password_reset_flow(self):
        response = self.client.post(reverse("accounts:password_reset"), {"email": "kiran@example.com"})
        self.assertRedirects(response, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        link = re.search(r"http://testserver(/accounts/reset/\S+)", mail.outbox[0].body).group(1)
        response = self.client.get(link, follow=True)
        self.assertEqual(response.status_code, 200)
        set_url = response.redirect_chain[-1][0]
        response = self.client.post(set_url, {"new_password1": "Reset#Pass9876", "new_password2": "Reset#Pass9876"})
        self.assertRedirects(response, reverse("accounts:password_reset_complete"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Reset#Pass9876"))
        # the same link cannot be used twice
        self.assertContains(self.client.get(link, follow=True), "invalid or has already been used")

    def test_reset_for_unknown_email_sends_nothing_but_looks_same(self):
        response = self.client.post(reverse("accounts:password_reset"), {"email": "nobody@example.com"})
        self.assertRedirects(response, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)


class TimezoneTests(TestCase):
    # 2026-03-10 20:00 UTC is already 11 March in India but still 10 March in New York.
    MOMENT = datetime(2026, 3, 10, 20, 0, tzinfo=dt_timezone.utc)

    def test_same_moment_gives_different_dates_for_different_timezones(self):
        india, usa = make_user("india"), make_user("usa")
        usa.profile.timezone = "America/New_York"; usa.profile.save()
        self.assertEqual(str(get_user_today(india, self.MOMENT)), "2026-03-11")
        self.assertEqual(str(get_user_today(usa, self.MOMENT)), "2026-03-10")

    def test_changing_timezone_changes_today(self):
        user = make_user("mover")
        self.assertEqual(str(get_user_today(user, self.MOMENT)), "2026-03-11")
        user.profile.timezone = "America/Los_Angeles"; user.profile.save()
        user = User.objects.get(pk=user.pk)  # fresh object, no cached profile
        self.assertEqual(str(get_user_today(user, self.MOMENT)), "2026-03-10")

    def test_middleware_activates_user_timezone_and_resets(self):
        user = make_user("mw")
        user.profile.timezone = "Asia/Tokyo"; user.profile.save()
        self.client.force_login(user)
        self.client.get(reverse("dashboard:index"))
        # after the request finishes the timezone is deactivated again
        self.assertEqual(timezone.get_current_timezone_name(), "Asia/Kolkata")

    def test_dashboard_shows_users_timezone(self):
        user = make_user("tz")
        user.profile.timezone = "Asia/Tokyo"; user.profile.save()
        self.client.force_login(user)
        self.assertContains(self.client.get(reverse("dashboard:index")), "Asia/Tokyo")
