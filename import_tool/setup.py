from setuptools import setup

setup(
   name='import_tool',
   version='0.1.0',
   description='Simple script to import data into the database',
   author='LV',
   author_email='verzend.aan@gmail.com',
   packages=['import_tool'],
   test_suite="tests",
   install_requires=['pandas'],
)