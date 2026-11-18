from django.contrib import admin

from .models import Domain, LearningProgress, Technology, Topic

admin.site.register(Domain)
admin.site.register(Technology)
admin.site.register(Topic)
admin.site.register(LearningProgress)
