from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def pipeline_badge(pipeline_type):
    """
    Returns a styled HTML badge for the pipeline type.
    """
    config = {
        'vanilla_llm': {
            'icon': 'bi-chat-square-text',
            'color': 'text-primary',
            'bg': 'bg-primary',
            'label': 'Vanilla'
        },
        'rag': {
            'icon': 'bi-database-gear',
            'color': 'text-warning',
            'bg': 'bg-warning',
            'label': 'RAG'
        },
        'vanilla_agent': {
            'icon': 'bi-robot',
            'color': 'text-info',
            'bg': 'bg-info',
            'label': 'Agent'
        },
        'browser_agent': {
            'icon': 'bi-browser-chrome',
            'color': 'text-success',
            'bg': 'bg-success',
            'label': 'Browser'
        }
    }
    
    style = config.get(pipeline_type, {
        'icon': 'bi-question-circle', 
        'color': 'text-secondary', 
        'bg': 'bg-secondary', 
        'label': pipeline_type
    })
    
    html = f"""
    <span class="d-inline-flex align-items-center {style['color']} bg-white border border-{style['color'].replace('text-', '')} border-opacity-25 rounded px-2 py-0 ms-1 shadow-sm" style="font-size: 0.75em; height: 20px;">
        <i class="bi {style['icon']} me-1"></i>
        <span class="fw-medium text-uppercase" style="letter-spacing: 0.5px; font-size: 0.9em;">{style['label']}</span>
    </span>
    """
    return mark_safe(html)
