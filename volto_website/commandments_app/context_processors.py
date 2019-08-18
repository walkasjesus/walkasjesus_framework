from commandments_app.models import BibleTranslation, UserPreferences


def bible_translation(request):
    return {
        'bible_translation': BibleTranslation(),
    }


def user_preferences(request):
    return {
        'user_preferences': UserPreferences(request.session),
    }
