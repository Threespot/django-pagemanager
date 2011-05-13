import os
from distutils.core import setup

VERSION = '0.1'

classifiers = [
    "Intended Audience :: Developers",
    "Programming Language :: Python",
    "Operating System :: OS Independent",
    "Topic :: Software Development :: Libraries",
    "Environment :: Web Environment",
    "Framework :: Django",
]

setup(
    name='django-pagemanager',
    version=VERSION,
    url='https://github.com/Threespot/django-pagemanager',
    author='Chuck Harmston',
    author_email='chuck.harmston@threespot.com',
    packages=['pagemanager'],
    package_dir={'pagemanager': 'pagemanager'},
    description=(
        'Robust and flexible page management system using Django\'s '
        'admin interface'
    ),
    classifiers=classifiers,
    install_requires=[
        'django>=1.3',
        'django-mptt>=0.4.2',
        'django-reversion>=1.4',
    ],
)