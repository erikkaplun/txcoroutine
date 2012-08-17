from setuptools import setup, find_packages

with open('README') as file:
    long_description = file.read()

setup(
    name="twisted-coroutine",
    long_description=long_description,
    version="1.0.3",
    packages=find_packages(),

    install_requires=[
        'twisted',
    ],

    author="Erik Allik",
    author_email="eallik@gmail.com",
    url="http://github.com/eallik/twisted-coroutine/"
)

