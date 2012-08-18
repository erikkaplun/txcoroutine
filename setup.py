from setuptools import setup, find_packages

with open('README.rst') as file:
    long_description = file.read()

setup(
    name="txcoroutine",
    long_description=long_description,
    version="1.0.6",
    packages=find_packages(),

    install_requires=[
        'twisted',
    ],

    author="Erik Allik",
    author_email="eallik@gmail.com",
    url="http://github.com/eallik/txcoroutine/"
)
