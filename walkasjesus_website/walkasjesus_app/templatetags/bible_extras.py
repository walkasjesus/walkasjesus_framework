from django import template

register = template.Library()


@register.filter(name='get_item')
def get_item(value, key):
    if value is None:
        return ''
    try:
        return value.get(str(key), value.get(key, ''))
    except AttributeError:
        try:
            return value[str(key)]
        except Exception:
            try:
                return value[key]
            except Exception:
                return ''
