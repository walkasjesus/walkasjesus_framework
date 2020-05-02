#!/bin/bash
#
# This script can be used to Auto translate all static files into the other configured languages (in settings.py)  
#
# Find more info on [jesus_commandments_translations/README.md](https://github.com/jesuscommandments/jesus_commandments_translations/blob/master/README.md)

if [[ -f ./venv/Scripts/activate ]]; then
	source ./venv/Scripts/activate
elif [[ -f ./venv/bin/activate ]]; then 
	source ./venv/bin/activate
else
	echo "ERROR: cannot find environment binary"
fi

# If Linux based servers. This is the preferred Operating System.
if which tee > /dev/null 2>&1 && which date > /dev/null 2>&1; then
	today=$(date +%Y%m%d)
	start=$(date)
	log=log/translation.${today}.log
	
	echo "INFO: ${start} - Start Auto Translating Files" | tee -a ${log}

	echo "Translating files." | tee -a ${log}
	python manage.py auto_translate | tee -a ${log}
	echo "Compiling the .po files. Run this also after changing the .po files." | tee -a ${log}
	django-admin compilemessages | tee -a ${log}
	echo "
	# When running auto_translate_files.sh Google will translate all django variables in a wrong format:
	# By Example:
	# msgid %(model_name)s with this %(field_label)s already exists.
	# msgstr % (Model_name) s mit diesem% (FIELD_LABEL) s ist bereits vorhanden.
	" | tee -a ${log}
	echo "" | tee -a ${log}
	echo "To fix most of the vars run this script: auto_correct_django_locale_vars.sh" | tee -a ${log}

	end=$(date)
	echo "INFO: ${end} - Ended Auto Translating Files" | tee -a ${log}

# Other Operating Systems like Windows
else
	echo "INFO: Start Auto Translating Files"
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
	echo "INFO: Ended Auto Translating Files"
fi