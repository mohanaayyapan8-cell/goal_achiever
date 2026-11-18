from django.urls import path

from . import views

app_name = "planner"

urlpatterns = [
    path("", views.overview, name="overview"),
    path("start/", views.start_challenge, name="start"),
    path("start-date/", views.change_start_date, name="change_start_date"),
    path("today/", views.today_redirect, name="today"),
    path("auto-schedule/", views.auto_schedule, name="auto_schedule"),
    path("day/<int:day>/", views.day_detail, name="day_detail"),
    path("day/<int:day>/title/", views.day_title, name="day_title"),
    path("goals/add/", views.goal_create, name="goal_create"),
    path("goals/<int:pk>/edit/", views.goal_update, name="goal_update"),
    path("goals/<int:pk>/delete/", views.goal_delete, name="goal_delete"),
    path("goals/<int:pk>/toggle/", views.goal_toggle, name="goal_toggle"),
    path("goals/<int:pk>/reschedule/", views.goal_reschedule, name="goal_reschedule"),
]
