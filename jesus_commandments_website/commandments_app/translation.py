import vinaigrette


def register_translations(app_config):
    translatable_model_fields = {
        'Commandment': ['title', 'title_negative', 'devotional'],
        'Drawing': ['description'],
        'Song': ['description'],
        'Movie': ['description'],
        'ShortMovie': ['description'],
        'Sermon': ['description'],
        'Picture': ['description'],
        'Testimony': ['description'],
        'Blog': ['description'],
        'Book': ['description'],
        'Question': ['text'],
     }

    # Register fields to translate
    for model, fields in translatable_model_fields.items():
        vinaigrette.register(app_config.get_model(model), fields)
