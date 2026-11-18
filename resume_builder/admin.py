from django.contrib import admin

from .models import Achievement, Certification, Education, Experience, Project, Resume, ResumeReview, ResumeUpload

for model in (Resume, Education, Experience, Project, Certification, Achievement, ResumeReview):
    admin.site.register(model)


@admin.register(ResumeUpload)
class ResumeUploadAdmin(admin.ModelAdmin):
    list_display = ("original_name", "user", "kind", "size", "uploaded_at")
    exclude = ("file",)          # the admin never links to the private file
