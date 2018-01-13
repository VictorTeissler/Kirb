#!/usr/bin/env python

from setuptools import setup

setup(name="kirb",
      version='0.1',
      description='Async directory buster',
      author='Victor Teissler',
      author_email='nope@nope.nope',
      url='zombo.com',
      packages=['kirb'],
      scripts=['bin/kirb-dirb'],
      install_requires=[
            'aiohttp',
            'async-timeout',
            'asyncio',
            'chardet',
            'idna',
            'multidict',
            'yarl'
      ]

)

