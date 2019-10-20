if [[ -f ./venv/Scripts/activate ]]; then
	source ./venv/Scripts/activate
elif [[ -f ./venv/bin/activate ]]; then 
	source ./venv/bin/activate
else
	echo "error: cannot find environment binary"
fi

echo "Translating files."
python manage.py auto_translate
echo "Compiling the .po files. Run this also after changing the .po files."
django-admin compilemessages
echo "
# When running auto_translate_files.sh Google will translate all django variables in a wrong format:
# By Example:
# msgid %(model_name)s with this %(field_label)s already exists.
# msgstr % (Model_name) s mit diesem% (FIELD_LABEL) s ist bereits vorhanden.
"
echo ""
echo "To fix most of the vars run this script: auto_correct_django_locale_vars.sh"
