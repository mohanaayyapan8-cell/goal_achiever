from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("learning/", include("learning.urls")),
    path("planner/", include("planner.urls")),
    path("assessments/", include("assessments.urls")),
    path("aptitude/", include("aptitude.urls")),
    path("coding/", include("coding.urls")),
    path("resume/", include("resume_builder.urls")),
    path("streaks/", include("streaks.urls")),
    path("notifications/", include("notifications.urls")),
    path("", include("dashboard.urls")),
    # Later phases add: accounts/, learning/, planner/, assessments/,
    # aptitude/, coding/, streaks/, resume/, notifications/
]
