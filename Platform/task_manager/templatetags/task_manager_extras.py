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
