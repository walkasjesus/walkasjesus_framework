#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

UWSGI_CONFIG="${WAJ_UWSGI_CONFIG:-/etc/uwsgi/apps-enabled/walkasjesus.ini}"
if [[ -e "$UWSGI_CONFIG" ]]; then
	if [[ ! -r "$UWSGI_CONFIG" ]]; then
		printf 'ERROR: Cannot read uWSGI config: %s\n' "$UWSGI_CONFIG" >&2
		exit 1
	fi
	while IFS= read -r config_line || [[ -n "$config_line" ]]; do
		if [[ "$config_line" =~ ^[[:space:]]*env[[:space:]]*=[[:space:]]*(DJANGO_CACHE_BACKEND|DJANGO_CACHE_LOCATION|DISABLE_CACHE_FOR_DEBUG)[[:space:]]*=[[:space:]]*(.*)$ ]]; then
			cache_key="${BASH_REMATCH[1]}"
			cache_value="${BASH_REMATCH[2]}"
			cache_value="${cache_value%"${cache_value##*[![:space:]]}"}"
			if ! declare -p "$cache_key" >/dev/null 2>&1; then
				export "$cache_key=$cache_value"
			fi
		fi
	done < "$UWSGI_CONFIG"
elif [[ -n "${WAJ_UWSGI_CONFIG:-}" ]]; then
	printf 'ERROR: uWSGI config not found: %s\n' "$UWSGI_CONFIG" >&2
	exit 1
fi

if [[ -x "$SCRIPT_DIR/venv/bin/python" ]]; then
	PYTHON_BIN="$SCRIPT_DIR/venv/bin/python"
elif [[ -x "$SCRIPT_DIR/../venv/bin/python" ]]; then
	PYTHON_BIN="$SCRIPT_DIR/../venv/bin/python"
else
	PYTHON_BIN="python3"
fi

"$PYTHON_BIN" manage.py shell -c "from django.conf import settings; from django.core.cache import cache; print('Clearing Django cache backend:', settings.CACHES['default']['BACKEND']); cache.clear(); print('Django cache cleared.')"
