from django.contrib import admin

from .models import AptitudeAttempt, AptitudeQuestion

admin.site.register(AptitudeQuestion)
admin.site.register(AptitudeAttempt)
