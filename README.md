# walkasjesus_framework

This repository is the heart of the application which will show all the different components of the Walk as Jesus Application in a fancy Python Framework [Django](https://www.djangoproject.com/)

## Installation steps to run the application

To run this website on a local machine please run the following steps:

**Prerequisites**  
If you want to run a lightweight local database for test purposes, please comment out the `mysqlclient>=1.4.4` as a requirement in the `./walkasjesus_website/requirements.txt`

1. Install all required Python tools  
_This will install all configured applications from `./walkasjesus_website/requirements.txt` in a virtual environment_  

`./walkasjesus_website/install.sh`

2. Initialize database  
_This will initialize a first database structure with all required tables, or update existing tables with the latest migrations to apply_  

`./walkasjesus_website/update_database.sh`

3. Import all steps, law of Messiah, Lessons and Media resources into the database  
_This will import the following repositories into the database:_  

`./walkasjesus_website/IMPORT.sh`

* [walkasjesus_biblereferences](https://github.com/walkasjesus/walkasjesus_biblereferences/commandments.csv)
  _Repository for the Walk as Jesus Framework where all the commandments with all their related Bible References are stored in a CSV_  

* [walkasjesus_media](https://github.com/walkasjesus/walkasjesus_media)
  _Repository for the Walk as Jesus Framework where all the resources (movies, songs, blogs, sermons, testimonies, etc) in all languages are stored in a CSV_  

* [walkasjesus_lessons](https://github.com/walkasjesus/walkasjesus_biblereferences/lessons.csv)
  _Repository for the Walk as Jesus Framework where all the lessons are stored in a CSV_

* [lawofmessiah](https://github.com/walkasjesus/LawofMessiah/collected_ids_titles.yaml)
  _Digitalized version for all Law of Messiah commandments from the book 'Torah from a New Covenant Perspective* by Michael Rudolph and Daniel C. Juster'_

4. Create admin user  
_This will create an admin user_  

Copy an example file to create the admin user:
`cp ./walkasjesus_website/account_app/management/commands/import_users.py.example ./walkasjesus_website/account_app/management/commands/import_users.py`  

Then you need to configure your admin credentials in this file:  
`./walkasjesus_website/account_app/management/commands/import_users.py`  

Now run the script to create the admin in the database:   
`./walkasjesus_website/create_admin_user.sh`  

5. Run the server
_This will run the server on your local machine on port 8000_  

`./walkasjesus_website/run_server.sh`

6. You can visit http://localhost:8000 to see the website on your local machine

## Development instructions

The following extra information might be helpfull when helping to improve this application. 

### Scripts

The following scripts can be used:

This script can be used to generate all translation files with all the content together from the CSV's and the framework.
`./walkasjesus_website/update_translation_files.sh`  

Auto translate all static files into the other configured languages (in settings.py)  
`./walkasjesus_website/auto_translate_files.sh`  

When files are auto translated Google will translate all django variables in a wrong format.  
This script will fix most errors:  
`./walkasjesus_website/auto_correct_django_locale_vars.sh`

```
# By Example:
# msgid "%(model_name)s with this %(field_label)s already exists."
# msgstr "% (Model_name) s mit diesem% (FIELD_LABEL) s ist bereits vorhanden."
# 1) We need to change the '% (Model_name) s' to '%(model_name)s'
# 2) We need to change the '</ [A-Za-z]>' to '</[a-z]>'
# 3) We need to change the '<[A-Z]>' to '<[a-z]>'
#
# This script will fix all these variables (works only when the same wrong pattern is used as in the example)
#
# Known issue: Sometimes Google also translated the variable to a complete different word, in that case we can't fix this automaticaly.
```

This will cache all Bible translations which are called from api.bible.  
`./walkasjesus_website/cache_bible_translation.sh`  

For each commandment there is a illustration. We use thumbnail caches to display those. To clear the caches run this script:   
`./walkasjesus_website/clean_thumbnail_cache.sh`  

When database structure is changed in code, you can run this script to automatically create migration scripts for Django.  
`./walkasjesus_website/make_migration.sh`

## Related projects and repositories

The following projects are related to this repository.

### walkasjesus_server

This repository contains IT Automation tools for [Ansible](https://docs.ansible.com/ansible/latest/index.html) to install & configure all the server components which are required to serve the [Walk as Jesus Framework](https://github.com/walkasjesus/walkasjesus_framework)

### walkasjesus_biblereferences

Repository for the Walk as Jesus Framework where all the commandments with all their related Bible References are stored in a CSV. This CSV can be imported/exported with the [Walk as Jesus Framework](https://github.com/walkasjesus/walkasjesus_framework) and the [Walk as Jesus Server](https://github.com/walkasjesus/walkasjesus_server)

### walkasjesus_media

Repository for the [Walk as Jesus Framework](https://github.com/walkasjesus/walkasjesus_framework) where all the resources (movies, songs, blogs, sermons, testimonies, etc) in all languages are stored in a CSV. This CSV can be imported/exported with the [Walk as Jesus Framework](https://github.com/walkasjesus/walkasjesus_framework) and the [Walk as Jesus Server](https://github.com/walkasjesus/walkasjesus_server)

### walkasjesus_translations

This repository contains all translation files from English to other languages. We use Google translate to make a first automated translation. The next step for the translator is to review all translated items and acknowledge them through the admin panel of the website.

### LawofMessiah

This repository contains the structured content and scripts for processing the commandments (*mitzvot*) derived from the Bible, as presented in the book series *The Law of Messiah - Torah from a New Covenant Perspective* by Michael Rudolph and Daniel C. Juster. The goal of this project is to make the commandments more accessible by organizing them into structured formats (e.g., YAML) and providing tools for filtering, searching, and studying them.
