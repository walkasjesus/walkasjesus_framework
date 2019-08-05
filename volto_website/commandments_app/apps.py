from django.apps import AppConfig
import vinaigrette


class CommandmentsAppConfig(AppConfig):
    name = 'commandments_app'

    def ready(self):
        print('AppReady')
        # Is this required by vinaigrette?
        from commandments_app.models import Commandment
        comm = self.get_model("Commandment")

        # Register fields to translate
        vinaigrette.register(comm, ['title', 'description'])
