#!/bin/bash
#
# This script will EXPORT all commandments and media items from the current database into the CSV and upload it as a pull request to github.
#
# There is made a separation between 'Commandments' and 'Media'.
#
# The 'Commandments' is a CSV with all:
# - Jesus Commandments
# - Bible references
# - Questions
# - Quotes
# This CSV source is stored in a git submodule with its origin from [data/biblereferences/commandments.csv](https://github.com/jesuscommandments/jesus_commandments_biblereferences)
#
# The 'Media' is a CSV with all:
# - Songs, Blogs, Movies, Drawings, Pictures, Superbook, etc.
#   Based on their:
# -- language
# -- target audience

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
	start=$(date '+%Y-%m-%d %H:%M:%S')
	now_epoch=$(date +%s)
	cur=$(dirname "$(realpath $0)")
	log=log/commandments.${today}.log
	last_import=$(grep 'Start importing Commandments' log/commandments.*.log | tail -1 | grep -Eo '[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}')
	rsakey=/home/jesuscommandments/.ssh/id_rsa
	
	# Get Changelog information from last import date until now
	mysql jcdatabase -e "select user_id,comment from reversion_revision where date_created >= '${last_import}' and date_created <= '${start}' INTO OUTFILE '/tmp/changes_${now_epoch}.csv' FIELDS TERMINATED BY ';';"
	mysql jcdatabase -e "select id,username,first_name,last_name,email from auth_user INTO OUTFILE '/tmp/users_${now_epoch}.csv' FIELDS TERMINATED BY ';';"

	# Replace user_id to human readable name
	IFS=$'\n'
	for line in $(cat /tmp/users_${now_epoch}.csv); do
		id=$(echo $line | awk -F ";" '{print $1}')
		username=$(echo $line | awk -F ";" '{print $2}')
		firstname=$(echo $line | awk -F ";" '{print $3}')
		lastname=$(echo $line | awk -F ";" '{print $4}')
		email=$(echo $line | awk -F ";" '{print $5}')

		if [[ -z ${firstname} ]] || [[ -z ${lastname} ]] || [[ -z ${email} ]]; then
			sed -i "s/^${id};/${firstname} ${lastname} (${email});/" /tmp/changes_${now_epoch}.csv
		else
			sed -i "s/^${id};/${username};/" /tmp/changes_${now_epoch}.csv
		fi
	done

	# Information used for commit messages
	title=$(echo "Changes from ${last_import} until ${today}")
	message_subtitle=$(echo "A summary of all the changes made: (name;changes)")
	submessage=$(cat /tmp/changes_${now_epoch}.csv)

	# Setup SSH agent to connect to Github
	eval $(ssh-agent)
	ssh-add ${rsakey}

	####################
	### Commandments ###
	####################

	# Export Commandments from Database to CSV
	cd ${cur}/data/biblereferences
	git checkout -b ${today}
	echo "INFO: ${start} - Start exporting Commandments" | tee -a ${log}
	python manage.py export_commandments data/biblereferences/commandments.csv | tee -a ${log}
	end=$(date '+%Y-%m-%d %H:%M:%S')
	echo "INFO: ${end} - Ended exporting Commandments" | tee -a ${log}

	# Git commit Commandments and create a pull request 
	git add commandments.csv
	git commit -m "Changes from ${last_import} until ${today}" -m "${message_subtitle}" -m "${submessage}"
	git push -u origin ${today}
	hub pull-request -h ${today} -F - <<MSG
${title}

${message_subtitle}

${submessage}
MSG

	#############
	### Media ###
	#############

	# Export Media from Database to CSV
	cd ${cur}/data/media
	git checkout -b ${today}
	echo "INFO: ${start} - Start exporting Media Resources" | tee -a ${log}
	python manage.py export_media data/media/media.csv | tee -a ${log}
	end=$(date '+%Y-%m-%d %H:%M:%S')
	echo "INFO: ${end} - Ended exporting Media Resources" | tee -a ${log}

	# Git commit Media and create a pull request 
	git add media.csv
	git commit -m "Changes from ${last_import} until ${today}" -m "${message_subtitle}" -m "${submessage}"
	git push -u origin ${today}
	hub pull-request -h ${today} -F - <<MSG2
${title}

${message_subtitle}

${submessage}
MSG2

	# Kill SSH agent
	pkill ssh-agent

else
	echo "INFO: Start exporting Commandments"
	python manage.py export_commandments data/biblereferences/commandments.csv
	echo "INFO: Ended exporting Commandments"

	echo "INFO: Start exporting Media Resources"
	python manage.py export_media data/media/media.csv
	echo "INFO: Ended exporting Media Resources"
fi
