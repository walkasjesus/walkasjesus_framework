# walkasjesus_framework

This repository is the heart of the application which will show all the different components of the Walk as Jesus Application in a fancy Python Framework [Django](https://www.djangoproject.com/)

## Installation steps to run the application

To run this website on a local machine please run the following steps:

**Prerequisites**  
If you want to run a lightweight local database for test purposes, please comment out the `mysqlclient>=1.4.4` as a requirement in the `./jesus_commandments_website/requirements.txt`

1. Install all required Python tools  
_This will install all configured applications from `./jesus_commandments_website/requirements.txt` in a virtual environment_  

`./jesus_commandments_website/install.sh`

2. Initialize database  
_This will initialize a first database structure with all required tables, or update existing tables with the latest migrations to apply_  

`./jesus_commandments_website/update_database.sh`

3. Import all commandments into the database  
_This will import the following commandments CSV into the database:_  

* [walkasjesus_biblereferences](https://github.com/walkasjesus/walkasjesus_biblereferences)
  _Repository for the Walk as Jesus Framework where all the commandments with all their related Bible References are stored in a CSV_  

`./jesus_commandments_website/import_commandments.sh`  

4. Import all media resources into the database  
_This will import the following media CSV into the database:_  

* [walkasjesus_media](https://github.com/walkasjesus/walkasjesus_media)
  _Repository for the Walk as Jesus Framework where all the resources (movies, songs, blogs, sermons, testimonies, etc) in all languages are stored in a CSV_  

`./jesus_commandments_website/import_media.sh`  

5. Create admin user  
_This will create an admin user_  

Copy an example file to create the admin user:
`cp ./jesus_commandments_website/account_app/management/commands/import_users.py.example ./jesus_commandments_website/account_app/management/commands/import_users.py`  

Then you need to configure your admin credentials in this file:  
`./jesus_commandments_website/account_app/management/commands/import_users.py`  

Now run the script to create the admin in the database:   
`./jesus_commandments_website/create_admin_user.sh`  

6. Run the server
_This will run the server on your local machine on port 8000_  

`./jesus_commandments_website/run_server.sh`

7. You can visit http://localhost:8000 to see the website on your local machine

8. Export all commandments into the CSV  
_This will export all commandments from the current database into the CSV:_  

* [walkasjesus_biblereferences](https://github.com/walkasjesus/walkasjesus_biblereferences)
  _Repository for the Walk as Jesus Framework where all the commandments with all their related Bible References are stored in a CSV_  

`./jesus_commandments_website/export_commandments.sh`  

9. Export all media resources into the CSV  
_This will export all media resources from the database into the CSV:_  

* [walkasjesus_media](https://github.com/walkasjesus/walkasjesus_media)
  _Repository for the Walk as Jesus Framework where all the resources (movies, songs, blogs, sermons, testimonies, etc) in all languages are stored in a CSV_  

`./jesus_commandments_website/export_media.sh`  

9. Export all media lessons into the CSV  
_This will export all media lessons from the database into the CSV:_  

`./jesus_commandments_website/export_media_lessons.sh`

## Development instructions

The following extra information might be helpfull when helping to improve this application. 

### Scripts

The following scripts can be used:

This script can be used to generate all translation files with all the content together from the CSV's and the framework.
`./jesus_commandments_website/update_translation_files.sh`  

Auto translate all static files into the other configured languages (in settings.py)  
`./jesus_commandments_website/auto_translate_files.sh`  

When files are auto translated Google will translate all django variables in a wrong format.  
This script will fix most errors:  
`./jesus_commandments_website/auto_correct_django_locale_vars.sh`

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
`./jesus_commandments_website/cache_bible_translation.sh`  

For each commandment there is a illustration. We use thumbnail caches to display those. To clear the caches run this script:   
`./jesus_commandments_website/clean_thumbnail_cache.sh`  

When database structure is changed in code, you can run this script to automatically create migration scripts for Django.  
`./jesus_commandments_website/make_migration.sh`

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
