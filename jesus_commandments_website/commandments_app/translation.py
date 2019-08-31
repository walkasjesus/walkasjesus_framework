import vinaigrette


def register_translations(app_config):
    comm = app_config.get_model("Commandment")

    # Register fields to translate
    vinaigrette.register(comm, ['title', 'devotional'])
