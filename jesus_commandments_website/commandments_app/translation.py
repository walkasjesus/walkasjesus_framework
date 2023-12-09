import vinaigrette


def register_translations(app_config):
    translatable_model_fields = {
        'Commandment': ['title', 'title_negative', 'quote'],
        'Drawing': ['description'],
        'Picture': ['description'],
        'Question': ['text'],
        'Lesson': ['title', 'related_step_description', 'story', 'activities'],
        'LessonDrawing': ['description'],
        'LessonPicture': ['description'],
        'LessonQuestion': ['text'],
    }

    # Register fields to translate
    for model, fields in translatable_model_fields.items():
        vinaigrette.register(app_config.get_model(model), fields)
