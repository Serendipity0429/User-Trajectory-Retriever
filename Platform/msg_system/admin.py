from django.contrib import admin
from .models import Message, MessageRecipient

class MessageRecipientInline(admin.TabularInline):
    model = MessageRecipient
    extra = 1
    raw_id_fields = ('user',)

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('subject', 'sender', 'timestamp', 'level')
    list_filter = ('level', 'timestamp')
    search_fields = ('subject', 'body', 'sender__username')
    raw_id_fields = ('sender',)
    readonly_fields = ('timestamp',)
    inlines = [MessageRecipientInline]
    fieldsets = (
        (None, {
            'fields': ('sender', 'subject', 'body', 'level')
        }),
        ('Date Information', {
            'fields': ('timestamp',)
        }),
    )

@admin.register(MessageRecipient)
class MessageRecipientAdmin(admin.ModelAdmin):
    list_display = ('message', 'user', 'is_read', 'is_pinned')
    list_filter = ('is_read', 'is_pinned')
    search_fields = ('message__subject', 'user__username')
    raw_id_fields = ('message', 'user')
