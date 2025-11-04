from django import template
from django.forms.widgets import Input, Select, Textarea

register = template.Library()

@register.filter(name='addclass')
def addclass(field, css_class):
    """Add CSS classes to form field."""
    if field.errors:
        css_class = f"{css_class} error"
    return field.as_widget(attrs={'class': css_class})

@register.filter(name='widget_type')
def widget_type(field):
    """Return the widget type of a form field."""
    return field.field.widget.__class__.__name__

@register.filter(name='is_checkbox')
def is_checkbox(field):
    """Check if field is a checkbox input."""
    return field.field.widget.__class__.__name__ == 'CheckboxInput'

@register.filter(name='add_error_class')
def add_error_class(field):
    """Add error class if field has errors."""
    if field.errors:
        return 'error'
    return ''