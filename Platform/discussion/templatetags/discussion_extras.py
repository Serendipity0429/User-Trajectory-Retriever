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