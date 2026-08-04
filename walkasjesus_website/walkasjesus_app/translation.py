import vinaigrette


TRANSLATABLE_MODEL_FIELDS = {
    'Commandment': ['title', 'title_negative', 'quote'],
    'Drawing': ['description'],
    'Picture': ['description'],
    'Question': ['text'],
    'Lesson': ['title', 'related_step_description', 'story', 'activities'],
    'LessonDrawing': ['description'],
    'LessonPicture': ['description'],
    'LessonQuestion': ['text'],
    # Keep concise labels translatable via PO, but keep long commentary bodies out of PO.
    'LawOfMessiah': ['title', 'commandment'],
}


def register_translations(app_config):
    # Register fields to translate
    for model, fields in TRANSLATABLE_MODEL_FIELDS.items():
        vinaigrette.register(app_config.get_model(model), fields)
