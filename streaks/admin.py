from django.contrib import admin

from .models import Achievement, StreakRecord

admin.site.register(StreakRecord)
admin.site.register(Achievement)
