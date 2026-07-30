from calendar import month_name
from datetime import date
import csv

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Sum
from django.db.models.functions import ExtractMonth
from django.http import HttpResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View

from walkasjesus_app.models import PageVisitDaily


class AdminPageUsageView(View):
    @method_decorator(staff_member_required)
    def get(self, request):
        available_years = [value.year for value in PageVisitDaily.objects.dates('usage_date', 'year', order='DESC')]

        current_year = date.today().year
        default_year = current_year - 1
        selected_year = request.GET.get('year', '')
        try:
            selected_year = int(selected_year)
        except (TypeError, ValueError):
            selected_year = default_year if default_year in available_years else (available_years[0] if available_years else current_year)

        selected_paths = [str(value).strip() for value in request.GET.getlist('page_paths') if str(value).strip()]

        base_qs = PageVisitDaily.objects.filter(usage_date__year=selected_year)
        if selected_paths:
            base_qs = base_qs.filter(page_path__in=selected_paths)

        page_rows = list(
            base_qs.values('page_path', 'page_label', 'language_code')
            .annotate(
                total_visits=Sum('visit_count'),
                unique_users=Count('user_key', distinct=True),
            )
            .order_by('-total_visits', 'page_path', 'language_code')
        )

        totals = base_qs.aggregate(
            total_visits=Sum('visit_count'),
            unique_users=Count('user_key', distinct=True),
        )
        totals = {k: (v or 0) for k, v in totals.items()}

        monthly_rows_raw = list(
            base_qs
            .annotate(month=ExtractMonth('usage_date'))
            .values('month')
            .annotate(
                total_visits=Sum('visit_count'),
                unique_users=Count('user_key', distinct=True),
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
                'total_visits': row.get('total_visits', 0) or 0,
                'unique_users': row.get('unique_users', 0) or 0,
            })

        visits_chart_markup = self._build_svg_chart(monthly_rows, 'total_visits', 'Visits')

        user_rows = list(
            base_qs.values('page_path', 'page_label', 'language_code', 'user_kind', 'user_key')
            .annotate(total_visits=Sum('visit_count'))
            .order_by('page_path', 'language_code', '-total_visits', 'user_kind', 'user_key')[:1500]
        )

        page_choices = list(
            PageVisitDaily.objects
            .filter(usage_date__year=selected_year)
            .values('page_path', 'page_label', 'language_code')
            .distinct()
            .order_by('page_path', 'language_code')
        )

        export_csv = str(request.GET.get('export', '')).strip().lower() == 'csv'
        if export_csv:
            return self._export_csv(selected_year, selected_paths, page_rows, totals)

        return render(request, 'admin/page_usage_report.html', {
            'available_years': available_years,
            'selected_year': selected_year,
            'selected_paths': selected_paths,
            'page_choices': page_choices,
            'page_rows': page_rows,
            'monthly_rows': monthly_rows,
            'visits_chart_markup': visits_chart_markup,
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
            svg_parts.append(f'<rect x="{x}" y="{y}" width="{bar_width}" height="{bar_height}" fill="#2563eb" rx="3" ry="3"/>')
            svg_parts.append(f'<text x="{x + 6}" y="{offset_top + chart_height + 18}" fill="#475569" font-size="11" font-family="Arial, sans-serif">{month_name[index + 1][:3]}</text>')
            if value:
                svg_parts.append(f'<text x="{x + 4}" y="{y - 6}" fill="#0f172a" font-size="10" font-family="Arial, sans-serif">{value}</text>')
        svg_parts.append('</svg>')
        return ''.join(svg_parts)

    def _export_csv(self, selected_year, selected_paths, page_rows, totals):
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        suffix = 'all' if not selected_paths else f'{len(selected_paths)}-pages'
        response['Content-Disposition'] = f'attachment; filename="page_usage_report_{selected_year}_{suffix}.csv"'

        writer = csv.writer(response)
        writer.writerow(['Page usage report'])
        writer.writerow(['Year', selected_year])
        writer.writerow(['Selected pages', ', '.join(selected_paths) if selected_paths else 'All'])
        writer.writerow([])
        writer.writerow(['Totals'])
        writer.writerow(['Total visits', totals.get('total_visits', 0)])
        writer.writerow(['Unique users', totals.get('unique_users', 0)])
        writer.writerow([])
        writer.writerow(['Page path', 'Page label', 'Language', 'Total visits', 'Unique users'])

        for row in page_rows:
            writer.writerow([
                row.get('page_path', ''),
                row.get('page_label', ''),
                row.get('language_code', ''),
                row.get('total_visits', 0) or 0,
                row.get('unique_users', 0) or 0,
            ])

        return response
