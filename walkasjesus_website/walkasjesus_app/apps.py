from django.apps import AppConfig

from walkasjesus_app.translation import register_translations


class CommandmentsAppConfig(AppConfig):
    name = 'walkasjesus_app'
    label = 'commandments_app'

    def ready(self):
        register_translations(self)
