from django import template
from msg_system.models import Message, MessageRecipient

register = template.Library()

@register.inclusion_tag('partials/unread_message_count.html', takes_context=True)
def unread_message_count(context):
    if context.request.user.is_authenticated:
        count = MessageRecipient.objects.filter(user=context.request.user, is_read=False).count()
    else:
        count = 0
    return {'unread_count': count}

@register.inclusion_tag('partials/message_popover.html', takes_context=True)
def message_popover(context):
    if context.request.user.is_authenticated:
        # Get unread messages for the user, annotated with their pinned status
        messages = Message.objects.filter(
            messagerecipient__user=context.request.user,
            messagerecipient__is_read=False
        ).order_by('-messagerecipient__is_pinned', '-timestamp')[:5]
    else:
        messages = []
    return {'messages': messages}