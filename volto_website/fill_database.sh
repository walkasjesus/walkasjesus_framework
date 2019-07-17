source ./venv/Scripts/activate
python manage.py shell < ./tools/create_users.py
python manage.py shell < ./tools/create_callings.py