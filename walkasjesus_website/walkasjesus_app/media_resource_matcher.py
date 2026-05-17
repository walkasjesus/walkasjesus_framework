from walkasjesus_app.models import LawOfMessiahDrawing


def _normalized_text(value):
    return str(value or '').strip()


def _shared_media_filter_kwargs(media_type, title, description, target_audience, language, img_url, url, author, is_public):
    return {
        'media_type': _normalized_text(media_type).lower() or LawOfMessiahDrawing.MEDIA_TYPE_DRAWING,
        'title': _normalized_text(title),
        'description': _normalized_text(description),
        'target_audience': _normalized_text(target_audience) or 'any',
        'language': _normalized_text(language) or 'en',
        'img_url': _normalized_text(img_url),
        'url': _normalized_text(url),
        'author': _normalized_text(author),
        'is_public': bool(is_public),
    }


def has_shared_commandment_media(commandment_id, *, media_type, title='', description='', target_audience='any', language='en', img_url='', url='', author='', is_public=False):
    if not commandment_id:
        return False

    return LawOfMessiahDrawing.objects.filter(
        commandment_id=commandment_id,
        **_shared_media_filter_kwargs(
            media_type=media_type,
            title=title,
            description=description,
            target_audience=target_audience,
            language=language,
            img_url=img_url,
            url=url,
            author=author,
            is_public=is_public,
        ),
    ).exists()


def has_shared_lesson_media(lesson_id, *, media_type, title='', description='', target_audience='any', language='en', img_url='', url='', author='', is_public=False):
    if not lesson_id:
        return False

    return LawOfMessiahDrawing.objects.filter(
        lesson_id=lesson_id,
        **_shared_media_filter_kwargs(
            media_type=media_type,
            title=title,
            description=description,
            target_audience=target_audience,
            language=language,
            img_url=img_url,
            url=url,
            author=author,
            is_public=is_public,
        ),
    ).exists()