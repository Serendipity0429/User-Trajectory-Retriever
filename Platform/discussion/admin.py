from django.contrib import admin
from django import forms
from .models import Bulletin, Post

class BulletinAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'created_at', 'pinned')

class PostAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'category', 'created_at', 'pinned')

admin.site.register(Bulletin, BulletinAdmin)
admin.site.register(Post, PostAdmin)
