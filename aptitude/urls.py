from django.urls import path

from . import views

app_name = "aptitude"

urlpatterns = [
    path("", views.overview, name="overview"),
    path("start/", views.start, name="start"),
    path("history/", views.history, name="history"),
    path("attempt/<int:pk>/", views.attempt_detail, name="attempt"),
    path("attempt/<int:pk>/answer/", views.answer, name="answer"),
    path("attempt/<int:pk>/submit/", views.submit, name="submit"),
]
