# coding: utf-8

from setuptools import setup, find_packages

NAME = "easy_earth"
VERSION = "0.0.1"

# To install the library, run the following
#
# python setup.py install
#
# prerequisite: setuptools
# http://pypi.python.org/pypi/setuptools

REQUIRES = ["connexion"]

setup(
    name=NAME,
    version=VERSION,
    description="Connexion example",
    author_email="ankit.ky@gmail.com",
    url="",
    keywords=["Swagger", "Connexion"],
    install_requires=REQUIRES,
    packages=find_packages(),
    package_data={'easyearth': ['openapi/swagger.yaml']},
    include_package_data=True,
    entry_points={
        'console_scripts': ['swagger_server=swagger_server.__main__:main']},
    long_description="""\
    Basic example to easyearth using Connexion
    """
)
