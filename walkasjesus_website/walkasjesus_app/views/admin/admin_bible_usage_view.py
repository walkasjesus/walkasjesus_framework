from datetime import date
import csv

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View

from walkasjesus_app.models import BibleTranslationUsageDaily


class AdminBibleUsageView(View):
    @method_decorator(staff_member_required)
    def get(self, request):
        available_years = [value.year for value in BibleTranslationUsageDaily.objects.dates('usage_date', 'year', order='DESC')]

        current_year = date.today().year
        default_year = current_year - 1
        selected_year = request.GET.get('year', '')
        try:
            selected_year = int(selected_year)
        except (TypeError, ValueError):
            selected_year = default_year if default_year in available_years else (available_years[0] if available_years else current_year)

        selected_bible_ids = [str(value).strip() for value in request.GET.getlist('bible_ids') if str(value).strip()]

        base_qs = BibleTranslationUsageDaily.objects.filter(usage_date__year=selected_year)
        if selected_bible_ids:
            base_qs = base_qs.filter(bible_id__in=selected_bible_ids)

        export_csv = str(request.GET.get('export', '')).strip().lower() == 'csv'

        per_bible_rows = list(
            base_qs.values('bible_id', 'bible_name', 'bible_language')
            .annotate(
                api_requests=Sum('request_count', filter=Q(source=BibleTranslationUsageDaily.SOURCE_API)),
                api_verses=Sum('verse_count', filter=Q(source=BibleTranslationUsageDaily.SOURCE_API)),
                api_unique_users=Count('user_key', filter=Q(source=BibleTranslationUsageDaily.SOURCE_API), distinct=True),
                cache_requests=Sum('request_count', filter=Q(source=BibleTranslationUsageDaily.SOURCE_CACHE)),
                cache_verses=Sum('verse_count', filter=Q(source=BibleTranslationUsageDaily.SOURCE_CACHE)),
                cache_unique_users=Count('user_key', filter=Q(source=BibleTranslationUsageDaily.SOURCE_CACHE), distinct=True),
                total_requests=Sum('request_count'),
                total_verses=Sum('verse_count'),
                total_unique_users=Count('user_key', distinct=True),
            )
            .order_by('-total_requests', 'bible_name', 'bible_id')
        )

        totals = base_qs.aggregate(
            api_requests=Sum('request_count', filter=Q(source=BibleTranslationUsageDaily.SOURCE_API)),
            api_verses=Sum('verse_count', filter=Q(source=BibleTranslationUsageDaily.SOURCE_API)),
            api_unique_users=Count('user_key', filter=Q(source=BibleTranslationUsageDaily.SOURCE_API), distinct=True),
            cache_requests=Sum('request_count', filter=Q(source=BibleTranslationUsageDaily.SOURCE_CACHE)),
            cache_verses=Sum('verse_count', filter=Q(source=BibleTranslationUsageDaily.SOURCE_CACHE)),
            cache_unique_users=Count('user_key', filter=Q(source=BibleTranslationUsageDaily.SOURCE_CACHE), distinct=True),
            total_requests=Sum('request_count'),
            total_verses=Sum('verse_count'),
            total_unique_users=Count('user_key', distinct=True),
        )
        totals = {k: (v or 0) for k, v in totals.items()}

        user_rows = list(
            base_qs.values('bible_id', 'bible_name', 'bible_language', 'user_kind', 'user_key')
            .annotate(
                api_requests=Sum('request_count', filter=Q(source=BibleTranslationUsageDaily.SOURCE_API)),
                cache_requests=Sum('request_count', filter=Q(source=BibleTranslationUsageDaily.SOURCE_CACHE)),
                total_requests=Sum('request_count'),
                total_verses=Sum('verse_count'),
            )
            .order_by('bible_name', 'bible_id', '-total_requests', 'user_kind', 'user_key')[:1500]
        )

        bible_choices = list(
            BibleTranslationUsageDaily.objects
            .filter(usage_date__year=selected_year)
            .values('bible_id', 'bible_name', 'bible_language')
            .distinct()
            .order_by('bible_name', 'bible_id')
        )

        if export_csv:
            return self._export_csv(selected_year, per_bible_rows, totals, selected_bible_ids)

        return render(request, 'admin/bible_usage_report.html', {
            'available_years': available_years,
            'selected_year': selected_year,
            'selected_bible_ids': selected_bible_ids,
            'bible_choices': bible_choices,
            'per_bible_rows': per_bible_rows,
            'user_rows': user_rows,
            'totals': totals,
        })

    def _export_csv(self, selected_year, per_bible_rows, totals, selected_bible_ids):
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        suffix = 'all' if not selected_bible_ids else f'{len(selected_bible_ids)}-translations'
        response['Content-Disposition'] = f'attachment; filename="bible_usage_report_{selected_year}_{suffix}.csv"'

        writer = csv.writer(response)
        writer.writerow(['Bible usage report'])
        writer.writerow(['Year', selected_year])
        writer.writerow(['Selected translations', ', '.join(selected_bible_ids) if selected_bible_ids else 'All'])
        writer.writerow([])
        writer.writerow(['Totals'])
        writer.writerow(['Metric', 'API', 'Cache', 'Total'])
        writer.writerow(['Requests', totals.get('api_requests', 0), totals.get('cache_requests', 0), totals.get('total_requests', 0)])
        writer.writerow(['Verses delivered', totals.get('api_verses', 0), totals.get('cache_verses', 0), totals.get('total_verses', 0)])
        writer.writerow(['Unique users', totals.get('api_unique_users', 0), totals.get('cache_unique_users', 0), totals.get('total_unique_users', 0)])
        writer.writerow([])
        writer.writerow([
            'Bible ID',
            'Bible language',
            'Bible name',
            'API requests',
            'API verses',
            'API unique users',
            'Cache requests',
            'Cache verses',
            'Cache unique users',
            'Total requests',
            'Total verses',
            'Total unique users',
        ])
        for row in per_bible_rows:
            writer.writerow([
                row.get('bible_id', ''),
                row.get('bible_language', ''),
                row.get('bible_name', ''),
                row.get('api_requests', 0) or 0,
                row.get('api_verses', 0) or 0,
                row.get('api_unique_users', 0) or 0,
                row.get('cache_requests', 0) or 0,
                row.get('cache_verses', 0) or 0,
                row.get('cache_unique_users', 0) or 0,
                row.get('total_requests', 0) or 0,
                row.get('total_verses', 0) or 0,
                row.get('total_unique_users', 0) or 0,
            ])
        return response
