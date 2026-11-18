from django.urls import path

from . import views

app_name = "resume_builder"

urlpatterns = [
    path("", views.resume_list, name="list"),
    path("ats-guide/", views.ats_guide, name="ats_guide"),
    path("new/", views.resume_create, name="create"),
    path("reviews/", views.review_list, name="reviews"),
    path("reviews/<int:pk>/", views.review_detail, name="review"),
    path("reviews/<int:pk>/delete/", views.review_delete, name="review_delete"),
    path("uploads/new/", views.upload_create, name="upload_create"),
    path("uploads/<int:pk>/download/", views.upload_download, name="upload_download"),
    path("uploads/<int:pk>/delete/", views.upload_delete, name="upload_delete"),
    path("uploads/<int:pk>/review/", views.upload_review, name="upload_review"),
    path("section/<str:kind>/<int:pk>/edit/", views.section_update, name="section_update"),
    path("section/<str:kind>/<int:pk>/delete/", views.section_delete, name="section_delete"),
    path("<int:pk>/", views.resume_editor, name="editor"),
    path("<int:pk>/edit/", views.resume_update, name="update"),
    path("<int:pk>/delete/", views.resume_delete, name="delete"),
    path("<int:pk>/add/<str:kind>/", views.section_create, name="section_create"),
    path("<int:pk>/preview/", views.resume_preview, name="preview"),
    path("<int:pk>/pdf/", views.resume_pdf, name="pdf"),
    path("<int:pk>/review/", views.resume_review, name="review_resume"),
]
