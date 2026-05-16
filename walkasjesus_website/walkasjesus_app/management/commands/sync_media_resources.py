from django.core.management import BaseCommand

from walkasjesus_app.models import (
    Blog,
    Book,
    Drawing,
    Henkieshow,
    LawOfMessiahDrawing,
    LessonDrawing,
    LessonHenkieshow,
    LessonPicture,
    LessonShortMovie,
    LessonSong,
    LessonSuperbook,
    LessonTestimony,
    Movie,
    Picture,
    Sermon,
    ShortMovie,
    Song,
    Superbook,
    Testimony,
    WaJVideo,
)


class Command(BaseCommand):
    help = 'Sync legacy commandment/lesson media into shared Media Resources and deduplicate shared rows.'

    def handle(self, *args, **options):
        created = 0
        created += self._sync_commandment_media(Song, LawOfMessiahDrawing.MEDIA_TYPE_SONG)
        created += self._sync_commandment_media(Superbook, LawOfMessiahDrawing.MEDIA_TYPE_SUPERBOOK)
        created += self._sync_commandment_media(Henkieshow, LawOfMessiahDrawing.MEDIA_TYPE_HENKIESHOW)
        created += self._sync_commandment_media(Movie, LawOfMessiahDrawing.MEDIA_TYPE_MOVIE)
        created += self._sync_commandment_media(ShortMovie, LawOfMessiahDrawing.MEDIA_TYPE_SHORTMOVIE)
        created += self._sync_commandment_media(WaJVideo, LawOfMessiahDrawing.MEDIA_TYPE_WAJVIDEO)
        created += self._sync_commandment_media(Drawing, LawOfMessiahDrawing.MEDIA_TYPE_DRAWING)
        created += self._sync_commandment_media(Testimony, LawOfMessiahDrawing.MEDIA_TYPE_TESTIMONY)
        created += self._sync_commandment_media(Blog, LawOfMessiahDrawing.MEDIA_TYPE_BLOG)
        created += self._sync_commandment_media(Picture, LawOfMessiahDrawing.MEDIA_TYPE_PICTURE)
        created += self._sync_commandment_media(Sermon, LawOfMessiahDrawing.MEDIA_TYPE_SERMON)
        created += self._sync_commandment_media(Book, LawOfMessiahDrawing.MEDIA_TYPE_BOOK)

        created += self._sync_lesson_media(LessonSong, LawOfMessiahDrawing.MEDIA_TYPE_SONG)
        created += self._sync_lesson_media(LessonSuperbook, LawOfMessiahDrawing.MEDIA_TYPE_SUPERBOOK)
        created += self._sync_lesson_media(LessonHenkieshow, LawOfMessiahDrawing.MEDIA_TYPE_HENKIESHOW)
        created += self._sync_lesson_media(LessonShortMovie, LawOfMessiahDrawing.MEDIA_TYPE_SHORTMOVIE)
        created += self._sync_lesson_media(LessonDrawing, LawOfMessiahDrawing.MEDIA_TYPE_DRAWING)
        created += self._sync_lesson_media(LessonTestimony, LawOfMessiahDrawing.MEDIA_TYPE_TESTIMONY)
        created += self._sync_lesson_media(LessonPicture, LawOfMessiahDrawing.MEDIA_TYPE_PICTURE)

        deleted = self._dedupe_shared_media()
        self.stdout.write(f'Created shared media rows: {created}')
        self.stdout.write(f'Deleted duplicate shared rows: {deleted}')

    def _sync_commandment_media(self, model_cls, media_type):
        created = 0
        for media in model_cls.objects.select_related('commandment').all():
            _, is_new = LawOfMessiahDrawing.objects.get_or_create(
                law_of_messiah=None,
                commandment=media.commandment,
                lesson=None,
                media_type=media_type,
                title=media.title,
                description=media.description,
                target_audience=media.target_audience,
                language=media.language,
                img_url=media.img_url,
                url=media.url,
                author=media.author,
                is_public=media.is_public,
            )
            if is_new:
                created += 1
        return created

    def _sync_lesson_media(self, model_cls, media_type):
        created = 0
        for media in model_cls.objects.select_related('lesson').all():
            _, is_new = LawOfMessiahDrawing.objects.get_or_create(
                law_of_messiah=None,
                commandment=None,
                lesson=media.lesson,
                media_type=media_type,
                title=media.title,
                description=media.description,
                target_audience=media.target_audience,
                language=media.language,
                img_url=media.img_url,
                url=media.url,
                author=media.author,
                is_public=media.is_public,
            )
            if is_new:
                created += 1
        return created

    def _dedupe_shared_media(self):
        seen = {}
        to_delete_ids = []
        for media in LawOfMessiahDrawing.objects.order_by('id'):
            key = (
                media.law_of_messiah_id,
                media.commandment_id,
                media.lesson_id,
                str(media.media_type or '').strip().lower(),
                str(media.title or '').strip(),
                str(media.description or '').strip(),
                str(media.target_audience or '').strip(),
                str(media.language or '').strip(),
                str(media.img_url or '').strip(),
                str(media.url or '').strip(),
                str(media.author or '').strip(),
                bool(media.is_public),
            )
            if key in seen:
                to_delete_ids.append(media.id)
            else:
                seen[key] = media.id

        if not to_delete_ids:
            return 0

        deleted_count, _ = LawOfMessiahDrawing.objects.filter(id__in=to_delete_ids).delete()
        return deleted_count
