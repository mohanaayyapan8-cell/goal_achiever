from django.urls import path

from . import views

app_name = "streaks"

urlpatterns = [path("", views.overview, name="overview")]
