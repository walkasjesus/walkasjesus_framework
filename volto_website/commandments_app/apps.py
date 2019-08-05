from django.apps import AppConfig

from commandments_app.translation import register_translations


class CommandmentsAppConfig(AppConfig):
    name = 'commandments_app'

    def ready(self):
        register_translations(self)
