from setuptools import setup

setup(
   name='bible_lib',
   version='0.1.0',
   description='Library to retrieve bible texts',
   author='LV',
   author_email='verzend.aan@gmail.com',
   packages=['bible_lib'],
   test_suite="tests",
   install_requires=['requests'],
)