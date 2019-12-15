from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.views import View

from commandments_app.models.bibles import BibleTranslationMetaData


class AdminEnableBible(View):
    @method_decorator(staff_member_required)
    def post(self, request):
        bible_id = request.POST.get('bible_id', '')
        is_enabled = request.POST.get('enable', 'enable')

        meta_data = BibleTranslationMetaData.objects.get(bible_id=bible_id)

        meta_data.is_enabled = is_enabled
        print(f'Updating {meta_data.bible_id} to is_enabled = {meta_data.is_enabled}')
        meta_data.save()

        return HttpResponseRedirect(request.POST.get('next', '/'))
