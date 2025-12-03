from django.contrib import admin
from .models import InteractiveSessionGroup, InteractiveSession

# Register your models here.
admin.site.register(InteractiveSessionGroup)
admin.site.register(InteractiveSession)
