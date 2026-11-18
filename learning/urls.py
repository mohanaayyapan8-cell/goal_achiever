from django.urls import path

from . import views

app_name = "learning"

urlpatterns = [
    path("", views.domain_list, name="domain_list"),
    path("defaults/load/", views.load_defaults, name="load_defaults"),
    path("domains/add/", views.domain_create, name="domain_create"),
    path("domains/<int:pk>/", views.domain_detail, name="domain_detail"),
    path("domains/<int:pk>/edit/", views.domain_update, name="domain_update"),
    path("domains/<int:pk>/delete/", views.domain_delete, name="domain_delete"),
    path("domains/<int:domain_pk>/technologies/add/", views.technology_create, name="technology_create"),
    path("technologies/<int:pk>/", views.technology_detail, name="technology_detail"),
    path("technologies/<int:pk>/edit/", views.technology_update, name="technology_update"),
    path("technologies/<int:pk>/delete/", views.technology_delete, name="technology_delete"),
    path("technologies/<int:technology_pk>/topics/add/", views.topic_create, name="topic_create"),
    path("topics/<int:pk>/", views.topic_detail, name="topic_detail"),
    path("topics/<int:pk>/content/edit/", views.content_edit, name="content_edit"),
    path("topics/<int:pk>/notes/add/", views.note_create, name="note_create"),
    path("notes/<int:pk>/edit/", views.note_update, name="note_update"),
    path("notes/<int:pk>/delete/", views.note_delete, name="note_delete"),
    path("topics/<int:pk>/edit/", views.topic_update, name="topic_update"),
    path("topics/<int:pk>/delete/", views.topic_delete, name="topic_delete"),
    path("topics/<int:pk>/status/", views.topic_set_status, name="topic_set_status"),
]
