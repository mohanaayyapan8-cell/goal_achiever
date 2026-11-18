from django.contrib import admin

from .models import DailyGoal, DailyPlan

admin.site.register(DailyPlan)
admin.site.register(DailyGoal)
