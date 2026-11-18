from django.contrib import admin

from .models import SpeakingAnswer, SpeakingAssessment, WrittenAnswer, WrittenAssessment

admin.site.register(WrittenAssessment)
admin.site.register(WrittenAnswer)
admin.site.register(SpeakingAssessment)
admin.site.register(SpeakingAnswer)
