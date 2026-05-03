from collections import defaultdict

from django.db.models import Q
from django.shortcuts import render
from django.views import View

from walkasjesus_app.models import LawOfMessiah, Maimonides


def _build_lom_by_maimonides_id():
    """Return a dict mapping each Maimonides ID to the LOM objects that reference it."""
    lom_rows = (
        LawOfMessiah.objects
        .exclude(maimonides=[])
        .only('id', 'title', 'commandment_type', 'maimonides')
    )
    lom_by_mai = defaultdict(list)
    # Index LOM objects by id so we attach the full object
    lom_map = {lom.id: lom for lom in lom_rows}
    for lom in lom_rows:
        for mai_id in lom.maimonides or []:
            lom_by_mai[str(mai_id)].append(lom_map[lom.id])
    return lom_by_mai


class MaimonidesList(View):
    def get(self, request):
        search_query = request.GET.get('q', '').strip()
        type_filter = request.GET.get('commandment_type', '').strip().lower()

        commandments_qs = Maimonides.objects.all()

        if search_query:
            commandments_qs = commandments_qs.filter(
                Q(id__icontains=search_query) | Q(commandment__icontains=search_query)
            )
        if type_filter in {Maimonides.COMMANDMENT_TYPE_POSITIVE, Maimonides.COMMANDMENT_TYPE_NEGATIVE}:
            commandments_qs = commandments_qs.filter(commandment_type=type_filter)

        commandments = list(commandments_qs)
        lom_by_mai = _build_lom_by_maimonides_id()

        for cmd in commandments:
            # Attach related LOM objects, de-duplicated by id
            seen = set()
            related = []
            for lom in lom_by_mai.get(cmd.id, []):
                if lom.id not in seen:
                    seen.add(lom.id)
                    related.append(lom)
            cmd.related_lawofmessiah = related

        return render(request, 'maimonides/listing.html', {
            'commandments': commandments,
            'commandments_count': len(commandments),
            'selected_q': search_query,
            'selected_commandment_type': type_filter,
        })
