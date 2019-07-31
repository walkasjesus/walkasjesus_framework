from modeltranslation.translator import translator, TranslationOptions

from commandments_app.models import Commandment


class CommandmentTranslationOptions(TranslationOptions):
    fields = ('title', 'description',)


translator.register(Commandment, CommandmentTranslationOptions)
