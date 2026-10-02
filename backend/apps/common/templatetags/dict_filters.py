"""
Custom template filters for working with dictionaries in Django templates.
"""

from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """
    Template filter to get an item from a dictionary.

    Usage in template:
        {{ my_dict|get_item:"key_name" }}

    Args:
        dictionary: Dictionary to get value from
        key: Key to look up

    Returns:
        Value from dictionary or None if key doesn't exist
    """
    if not isinstance(dictionary, dict):
        return None
    return dictionary.get(key)
