from django.urls import path

from . import views

app_name = "coding"

urlpatterns = [
    path("", views.problem_list, name="list"),
    path("runner/harness.py", views.harness, name="harness"),
    path("submissions/<int:pk>/", views.submission_detail, name="submission"),
    path("<slug:slug>/", views.problem_detail, name="detail"),
    path("<slug:slug>/submit/", views.problem_submit, name="submit"),
    path("<slug:slug>/local-test.py", views.local_script, name="local_script"),
]
