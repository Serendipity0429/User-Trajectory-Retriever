from django import template
from django.utils.safestring import mark_safe
import json

register = template.Library()


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


@register.filter
def split(value, arg):
    return value.split(arg)


@register.filter
def div(value, arg):
    return value / arg


@register.filter
def mul(value, arg):
    return value * arg


@register.filter(is_safe=True)
def jsonify(obj):
    return mark_safe(json.dumps(obj))


@register.filter(is_safe=True)
def safe_json_string(s):
    """
    Escapes `</script>` in a string to make it safe for embedding in a `<script>` tag.
    """
    return mark_safe(s.replace("</script>", "<\\/script>"))


@register.filter
def parse_json(value):
    try:
        if isinstance(value, str):
            return json.loads(value)
        return value
    except (ValueError, TypeError):
        return value


@register.filter
def is_list(value):
    return isinstance(value, list)


@register.filter
def format_duration(duration):
    if duration is None:
        return ""
    seconds = duration.total_seconds()
    minutes = seconds / 60
    return f"{minutes:.1f} minutes"


@register.filter
def format_duration_short(duration):
    if duration is None:
        return ""
    seconds = int(duration.total_seconds())
    if seconds < 60:
        return f"{seconds} s"
    else:
        minutes = round(seconds / 60)
        return f"{minutes} m"
