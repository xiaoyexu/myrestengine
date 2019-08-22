from setuptools import setup, find_packages

setup(
    name="myrest",
    version="0.1.0",
    packages=find_packages('src'),
    package_dir={'': 'src'},
    package_data={
        '': ['*.py']
    },
    install_requires=[
        'django>=1.9.0'
    ]
)
