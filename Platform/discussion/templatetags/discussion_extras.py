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
        'Bugs & Issues': 'badge-warning-custom',
        'Important': 'badge-important-custom',
        'System Update': 'badge-update-custom',
        'Technical Support': 'badge-support-custom',
        'Feedback & Suggestions': 'badge-feedback-custom',
        'Maintenance': 'badge-maintenance-custom',
        'Event': 'badge-event-custom',
    }.get(category, 'badge-general-custom')

@register.filter
def category_btn_class(category):
    return {
        'Warning': 'btn-warning-custom',
        'Bugs & Issues': 'btn-issues-custom',
        'Important': 'btn-important-custom',
        'System Update': 'btn-update-custom',
        'Technical Support': 'btn-support-custom',
        'Feedback & Suggestions': 'btn-feedback-custom',
        'Maintenance': 'btn-maintenance-custom',
        'Event': 'btn-event-custom',
    }.get(category, 'btn-general-custom')

@register.filter
def to_outline_btn(btn_class):
    return btn_class.replace('btn-', 'btn-outline-')
