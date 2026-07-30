from calendar import month_name
from datetime import date
import csv

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q, Sum
from django.db.models.functions import ExtractMonth
from django.http import HttpResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View

from walkasjesus_app.models import BibleTranslationUsageDaily


class AdminBibleUsageView(View):
    @method_decorator(staff_member_required)
    def get(self, request):
        available_years = [value.year for value in BibleTranslationUsageDaily.objects.dates('usage_date', 'year', order='DESC')]
        month_choices = [{'value': month, 'label': month_name[month]} for month in range(1, 13)]

        current_year = date.today().year
        default_year = current_year - 1
        selected_year = request.GET.get('year', '')
        try:
            selected_year = int(selected_year)
        except (TypeError, ValueError):
            selected_year = default_year if default_year in available_years else (available_years[0] if available_years else current_year)

        selected_bible_ids = [str(value).strip() for value in request.GET.getlist('bible_ids') if str(value).strip()]

        selected_month = request.GET.get('month', '')
        try:
            selected_month = int(selected_month)
            if selected_month < 1 or selected_month > 12:
                selected_month = None
        except (TypeError, ValueError):
            selected_month = None

        year_qs = BibleTranslationUsageDaily.objects.filter(usage_date__year=selected_year)
        if selected_bible_ids:
            year_qs = year_qs.filter(bible_id__in=selected_bible_ids)

        base_qs = year_qs
        if selected_month:
            base_qs = base_qs.filter(usage_date__month=selected_month)

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

        monthly_rows_raw = list(
            year_qs
            .annotate(month=ExtractMonth('usage_date'))
            .values('month')
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
            .order_by('month')
        )
        monthly_lookup = {row['month']: row for row in monthly_rows_raw}
        monthly_rows = []
        for month in range(1, 13):
            row = monthly_lookup.get(month, {})
            monthly_rows.append({
                'month': month,
                'month_label': month_name[month],
                'api_requests': row.get('api_requests', 0) or 0,
                'api_verses': row.get('api_verses', 0) or 0,
                'api_unique_users': row.get('api_unique_users', 0) or 0,
                'cache_requests': row.get('cache_requests', 0) or 0,
                'cache_verses': row.get('cache_verses', 0) or 0,
                'cache_unique_users': row.get('cache_unique_users', 0) or 0,
                'total_requests': row.get('total_requests', 0) or 0,
                'total_verses': row.get('total_verses', 0) or 0,
                'total_unique_users': row.get('total_unique_users', 0) or 0,
            })

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

        report_period_label = f'{month_name[selected_month]} {selected_year}' if selected_month else str(selected_year)

        if export_csv:
            return self._export_csv(selected_year, selected_month, per_bible_rows, totals, selected_bible_ids, monthly_rows)

        requests_chart_markup = self._build_svg_chart(monthly_rows, 'total_requests', 'Requests')

        return render(request, 'admin/bible_usage_report.html', {
            'available_years': available_years,
            'month_choices': month_choices,
            'selected_year': selected_year,
            'selected_month': selected_month,
            'report_period_label': report_period_label,
            'selected_bible_ids': selected_bible_ids,
            'bible_choices': bible_choices,
            'monthly_rows': monthly_rows,
            'requests_chart_markup': requests_chart_markup,
            'per_bible_rows': per_bible_rows,
            'user_rows': user_rows,
            'totals': totals,
        })

    def _build_svg_chart(self, monthly_rows, value_key, title):
        values = [row.get(value_key, 0) or 0 for row in monthly_rows]
        max_value = max(values) if values else 1
        width = 620
        height = 180
        chart_height = 120
        bar_width = 34
        gap = 16
        offset_left = 36
        offset_top = 24
        svg_parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            f'<rect x="0" y="0" width="{width}" height="{height}" fill="#f8fafc" rx="8" ry="8"/>',
            f'<text x="24" y="20" fill="#334155" font-size="14" font-family="Arial, sans-serif">{title}</text>',
        ]
        for index, value in enumerate(values):
            bar_height = int(round((value / max_value) * chart_height)) if max_value else 0
            bar_height = max(bar_height, 2 if value else 0)
            x = offset_left + index * (bar_width + gap)
            y = offset_top + chart_height - bar_height
            svg_parts.append(f'<rect x="{x}" y="{y}" width="{bar_width}" height="{bar_height}" fill="#16a34a" rx="3" ry="3"/>')
            svg_parts.append(f'<text x="{x + 6}" y="{offset_top + chart_height + 18}" fill="#475569" font-size="11" font-family="Arial, sans-serif">{month_name[index + 1][:3]}</text>')
            if value:
                svg_parts.append(f'<text x="{x + 4}" y="{y - 6}" fill="#0f172a" font-size="10" font-family="Arial, sans-serif">{value}</text>')
        svg_parts.append('</svg>')
        return ''.join(svg_parts)

    def _export_csv(self, selected_year, selected_month, per_bible_rows, totals, selected_bible_ids, monthly_rows):
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        period_suffix = f'{selected_year}-{selected_month:02d}' if selected_month else str(selected_year)
        suffix = 'all' if not selected_bible_ids else f'{len(selected_bible_ids)}-translations'
        response['Content-Disposition'] = f'attachment; filename="bible_usage_report_{period_suffix}_{suffix}.csv"'

        writer = csv.writer(response)
        writer.writerow(['Bible usage report'])
        writer.writerow(['Year', selected_year])
        writer.writerow(['Month', month_name[selected_month] if selected_month else 'All'])
        writer.writerow(['Selected translations', ', '.join(selected_bible_ids) if selected_bible_ids else 'All'])
        writer.writerow([])
        writer.writerow(['Totals'])
        writer.writerow(['Metric', 'API', 'Cache', 'Total'])
        writer.writerow(['Requests', totals.get('api_requests', 0), totals.get('cache_requests', 0), totals.get('total_requests', 0)])
        writer.writerow(['Verses delivered', totals.get('api_verses', 0), totals.get('cache_verses', 0), totals.get('total_verses', 0)])
        writer.writerow(['Unique users', totals.get('api_unique_users', 0), totals.get('cache_unique_users', 0), totals.get('total_unique_users', 0)])
        writer.writerow([])
        writer.writerow(['Year breakdown per month'])
        writer.writerow(['Month', 'API requests', 'Cache requests', 'Total requests', 'API verses', 'Cache verses', 'Total verses', 'API unique users', 'Cache unique users', 'Total unique users'])
        for month_row in monthly_rows:
            writer.writerow([
                month_row.get('month_label', ''),
                month_row.get('api_requests', 0),
                month_row.get('cache_requests', 0),
                month_row.get('total_requests', 0),
                month_row.get('api_verses', 0),
                month_row.get('cache_verses', 0),
                month_row.get('total_verses', 0),
                month_row.get('api_unique_users', 0),
                month_row.get('cache_unique_users', 0),
                month_row.get('total_unique_users', 0),
            ])
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
