if [[ -f ./venv/Scripts/activate ]]; then
	source ./venv/Scripts/activate
elif [[ -f ./venv/bin/activate ]]; then 
	source ./venv/bin/activate
else
	echo "error: cannot find environment binary"
fi
python manage.py list_bible_translations
read -p "Please provide a bible id " bible_id
python manage.py cache_bible_translation $bible_id