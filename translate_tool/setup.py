from setuptools import setup

setup(
   name='translate_tool',
   version='0.1.0',
   description='Simple script translate .po files',
   author='LV',
   author_email='verzend.aan@gmail.com',
   packages=['translate_tool'],
   test_suite="tests",
   install_requires=['google_trans', 'polib', 'requests'],
)