import os
from django import template

register = template.Library()

@register.filter
def filename(value):
    return os.path.basename(value.name)

@register.filter
def is_video(filename):
    video_extensions = ['.mp4', '.webm', '.ogg']
    return any(filename.lower().endswith(ext) for ext in video_extensions)

@register.filter
def videos(attachments):
    return [a for a in attachments if is_video(a.file.name)]

@register.filter
def is_image(filename):
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif']
    return any(filename.lower().endswith(ext) for ext in image_extensions)

@register.filter
def category_color_class(category):
    return {
        'Warning': 'badge-warning-custom',
        'Bugs & Issues': 'badge-issues-custom',
        'Important': 'badge-important-custom',
        'System Update': 'badge-update-custom',
        'Feedback & Suggestions': 'badge-feedback-custom',
    }.get(category, 'badge-general-custom')

@register.filter
def category_badge_class(category):
    return {
        'Warning': 'badge-warning-custom',
        'Bugs & Issues': 'badge-issues-custom',
        'Important': 'badge-important-custom',
        'System Update': 'badge-update-custom',
        'Feedback & Suggestions': 'badge-feedback-custom',
    }.get(category, 'badge-general-custom')

@register.filter
def category_badge_subtle_class(category):
    return {
        'Warning': 'bg-dark-subtle text-dark-emphasis border border-dark-subtle',
        'Bugs & Issues': 'bg-warning-subtle text-warning-emphasis border border-warning-subtle',
        'Important': 'bg-danger-subtle text-danger-emphasis border border-danger-subtle',
        'System Update': 'bg-primary-subtle text-primary-emphasis border border-primary-subtle',
        'Feedback & Suggestions': 'bg-success-subtle text-success-emphasis border border-success-subtle',
    }.get(category, 'bg-secondary-subtle text-secondary-emphasis border border-secondary-subtle')

@register.filter
def category_button_class(category):
    return {
        'Warning': 'discussion-orange',
        'Bugs & Issues': 'discussion-pink',
        'Important': 'discussion-purple',
        'System Update': 'discussion-teal',
        'Feedback & Suggestions': 'discussion-lime',
    }.get(category, 'secondary')

@register.filter
def discussion_category_badge_subtle_class(category):
    return {
        'Warning': 'badge-discussion-orange',
        'Bugs & Issues': 'badge-discussion-pink',
        'Important': 'badge-discussion-purple',
        'System Update': 'badge-discussion-teal',
        'Feedback & Suggestions': 'badge-discussion-lime',
    }.get(category, 'bg-secondary-subtle text-secondary-emphasis border border-secondary-subtle')
@register.filter
def to_outline_badge(badge_class):
    return badge_class.replace('badge-', 'badge-outline-')

@register.filter
def was_updated(obj):
    if not hasattr(obj, 'updated_at') or not hasattr(obj, 'created_at'):
        return False
    return (obj.updated_at - obj.created_at).total_seconds() > 1

@register.filter
def get_icon_for_file(filename):
    extension = str(filename).split('.')[-1].lower()
    if extension in ['pdf']:
        return 'bi bi-file-earmark-pdf-fill'
    if extension in ['doc', 'docx']:
        return 'bi bi-file-earmark-word-fill'
    if extension in ['xls', 'xlsx']:
        return 'bi bi-file-earmark-excel-fill'
    if extension in ['ppt', 'pptx']:
        return 'bi bi-file-earmark-ppt-fill'
    if extension in ['zip', 'rar']:
        return 'bi bi-file-earmark-zip-fill'
    if extension in ['jpg', 'jpeg', 'png', 'gif']:
        return 'bi bi-file-earmark-image-fill'
    if extension in ['mp3', 'wav', 'ogg']:
        return 'bi bi-file-earmark-music-fill'
    if extension in ['c', 'h', 'cpp', 'py', 'js', 'java']:
        return 'bi bi-file-earmark-code-fill'
    return 'bi bi-file-earmark-fill'

from django.utils.timezone import now

@register.filter
def short_timesince(value):
    if not value:
        return ""
    
    time_now = now()
    if value > time_now:
        return "now"

    delta = time_now - value

    if delta.days >= 365:
        years = delta.days // 365
        return f"{years}y"
    if delta.days >= 30:
        months = delta.days // 30
        return f"{months}mo"
    if delta.days > 0:
        return f"{delta.days}d"
    
    seconds = delta.seconds
    if seconds < 60:
        return "now"
    
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
        
    hours = minutes // 60
    return f"{hours}h"

@register.filter
def abbreviate_category(category):
    return {
        'Bugs & Issues': 'Bugs',
        'Feedback & Suggestions': 'Feedback',
        'System Update': 'Update',
    }.get(category, category)
        
    