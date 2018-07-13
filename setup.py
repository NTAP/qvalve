from setuptools import setup

setup(name='qvalve',
      version='0.1',
      description='Predictably impair QUIC flows',
      url='https://github.com/larseggert/qvalve',
      author='Lars Eggert',
      author_email='lars@eggert.org',
      packages=setuptools.find_packages(),
      scripts=['bin/qvalve'],
      classifiers=(
              "Programming Language :: Python :: 3",
              "License :: OSI Approved :: BSD License",
              "Operating System :: POSIX",
      )
)
