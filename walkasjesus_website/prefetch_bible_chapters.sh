#!/bin/bash
#
# Daily prefetch/refresh of whole Bible chapters in the api.bible cache.
#
# Schedule this from cron, e.g. (run at 03:15 every night):
#   15 3 * * * cd /path/to/walkasjesus_framework/walkasjesus_website && ./prefetch_bible_chapters.sh >> /var/log/walkasjesus/prefetch_bible_chapters.log 2>&1
#
# Each run performs at most BIBLE_PREFETCH_MAX_REQUESTS_PER_RUN api.bible requests
# (default 300, override with --max-requests) and refreshes cached chapters before
# the 25-day cache TTL expires, keeping the site within the api.bible requirement
# of refreshing cached content at least every 30 days.
#
# License-limited translations (e.g. NBV21/BGT: max 5 verses at a time) are never
# prefetched; see BIBLE_STUDY_MAX_VERSES_BY_BIBLE_ID in base_settings.py.
#
# Extra arguments are passed through, e.g.:
#   ./prefetch_bible_chapters.sh --dry-run
#   ./prefetch_bible_chapters.sh --bible-ids 89f6d2447cc48fbd-01 87f620660790371b-01
#   ./prefetch_bible_chapters.sh --books John Genesis
# Bible IDs and books are processed in the given order. By default, eligible
# Dutch translations come first, followed by KJV, Messianic/Jewish, and the rest.

set -e

cd "$(dirname "$0")"

if [[ -f ./venv/Scripts/activate ]]; then
	source ./venv/Scripts/activate
elif [[ -f ./venv/bin/activate ]]; then
	source ./venv/bin/activate
else
	echo "ERROR: cannot find environment binary"
	exit 1
fi

python3 manage.py prefetch_bible_chapters "$@"
