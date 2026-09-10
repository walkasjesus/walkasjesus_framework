from django.shortcuts import render
from django.views import View

from walkasjesus_app.models import Commandment
from walkasjesus_app.views.detail_view import _allowed_media_languages, _allowed_target_audiences


class ListingView(View):
    def get(self, request):
        commandments_ordered = list(
            Commandment.objects.order_by('id').all().prefetch_related('drawing_set', 'shared_media_resources')
        )
        allowed_target_audiences = _allowed_target_audiences(request)
        allowed_media_languages = _allowed_media_languages(request)
        for commandment in commandments_ordered:
            commandment.media_type_badge_list = commandment.media_type_badges(allowed_target_audiences, allowed_media_languages)
        return render(request, 'commandments/listing.html', {'commandments': commandments_ordered})
