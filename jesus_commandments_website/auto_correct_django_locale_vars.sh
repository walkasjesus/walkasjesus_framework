#!/bin/bash
#
# This script will fix all these variables (works only when the same wrong pattern is used as in the example)
#
# When running auto_translate_files.sh Google will translate all django variables in a wrong format:
# By Example:
# msgid "%(model_name)s with this %(field_label)s already exists."
# msgstr "% (Model_name) s mit diesem% (FIELD_LABEL) s ist bereits vorhanden."
#
# 1) We need to change the '% (Model_name) s' to '%(model_name)s'
# 2) We need to change the '</ [A-Za-z]>' to '</[a-z]>'
# 3) We need to change the '<[A-Z]>' to '<[a-z]>'
#
# Known issue: Sometimes Google also translated the variable to a complete different word, in that case we can't fix this automatic
#
# Find more info on [jesus_commandments_translations/README.md](https://github.com/jesuscommandments/jesus_commandments_translations/blob/master/README.md)

today=$(date +%Y%m%d)
start=$(date)
log=log/translation.${today}.log

echo "INFO: ${start} - Start Auto correct Django locale vars" | tee -a ${log}

declare -a locale_paths=$(find translations -name "django.po")

for locale in ${locale_paths[@]}; do
	echo "Start parsing file: $locale" | tee -a ${log}
	if sed -i -r "s/\% \(([a-zA-Z0-9_.]+)\) s/\%(\L\1)s/g" $locale | tee -a ${log}; then
		echo "OK: Succesfully fixed '% (Model_name) s' to '%(model_name)s'" | tee -a ${log}
	else
		echo "ERROR: Something went wrong when fixing '% (Model_name) s' to '%(model_name)s'" | tee -a ${log}
	fi
	if sed -i -r "s/<\/ ([A-Za-z])>/<\/\L\1>/g" $locale | tee -a ${log}; then
		echo "OK: Succesfully fixed '</ [A-Za-z]>' to '</[a-z]>'" | tee -a ${log}
	else
		echo "ERROR: Something went wrong when fixing '</ [A-Za-z]>' to '</[a-z]>'" | tee -a ${log}
	fi
	if sed -i -r "s/<([A-Z])>/<\L\1>/g" $locale | tee -a ${log}; then
		echo "OK: Succesfully fixed '<[A-Z]>' to '<[a-z]>'" | tee -a ${log}
	else
		echo "ERROR: Something went wrong when fixing '<[A-Z]>' to '<[a-z]>'" | tee -a ${log}
	fi
done

end=$(date)
echo "INFO: ${end} - Ended Auto correct Django locale vars" | tee -a ${log}
