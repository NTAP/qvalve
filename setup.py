from setuptools import setup, find_packages

setup(name='qvalve',
      version='0.1',
      description='Predictably impair QUIC flows',
      url='https://github.com/larseggert/qvalve',
      author='Lars Eggert',
      author_email='lars@eggert.org',
      packages=find_packages(),
      scripts=['bin/qvalve'],
      install_requires=['textx'],
      classifiers=(
              "Programming Language :: Python :: 3",
              "License :: OSI Approved :: BSD License",
              "Operating System :: POSIX",
      )
)
