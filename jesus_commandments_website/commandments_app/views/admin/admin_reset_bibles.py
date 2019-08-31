from bible_lib.bible_api.cache_controller import CacheController
from bible_lib.bible_api.services import Services
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.views import View


class AdminResetBibles(View):
    @method_decorator(staff_member_required)
    def post(self, request):
        cache = Services().cache
        cache_controller = CacheController(cache)
        cache_controller.clear_bible_list()

        return HttpResponseRedirect(request.POST.get('next', '/'))
