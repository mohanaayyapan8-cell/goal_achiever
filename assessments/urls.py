from django.urls import path

from . import views

app_name = "assessments"

urlpatterns = [
    path("", views.overview, name="overview"),
    path("topic/<int:topic_pk>/", views.topic_hub, name="topic_hub"),
    path("topic/<int:topic_pk>/written/start/", views.written_start, name="written_start"),
    path("written/<int:pk>/", views.written_detail, name="written_detail"),
    path("written/<int:pk>/result/", views.written_result, name="written_result"),
    path("written/answers/<int:answer_pk>/ai/", views.written_ai, name="written_ai"),
    path("topic/<int:topic_pk>/speaking/start/", views.speaking_start, name="speaking_start"),
    path("speaking/<int:pk>/", views.speaking_detail, name="speaking_detail"),
    path("speaking/<int:pk>/result/", views.speaking_result, name="speaking_result"),
]
