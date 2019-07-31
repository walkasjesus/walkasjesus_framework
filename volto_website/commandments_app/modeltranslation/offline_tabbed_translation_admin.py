from modeltranslation.admin import TranslationAdmin


class OfflineTabbedTranslationAdmin(TranslationAdmin):
    """" The regular TabbedTranslationAdmin refers to it js from google,
    This version refers to files we host ourselves."""

    class Media:
        js = (
            'js/jquery.min.js',
            'js/jquery-ui.min.js',
            'modeltranslation/js/tabbed_translation_fields.js',
        )
        css = {
            'screen': ('modeltranslation/css/tabbed_translation_fields.css',),
        }