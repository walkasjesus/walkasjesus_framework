from bible_lib import BibleFactory
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.views import View

from commandments_app.models import BibleReferences


class AdminCacheBible(View):
    @method_decorator(staff_member_required)
    def post(self, request):
        bible_id = request.POST['bible_id']
        bible_references = BibleReferences()
        bible_references.bible = BibleFactory().create(bible_id)

        # Just retrieve the text of all references and it will automatically be cached by the bible_lib
        for ref in bible_references.primary():
            ref.text()

        for ref in bible_references.secondary():
            ref.text()

        for ref in bible_references.tertiary():
            ref.text()

        return HttpResponseRedirect(request.POST.get('next', '/'))
