from django.contrib import admin

from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "timezone", "target_role", "email_reminders")
    search_fields = ("user__username", "user__email", "target_role")
