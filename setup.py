from setuptools import setup, find_packages

with open("README.md", "r", encoding='utf-8') as fh:
    long_description = fh.read()

setup(
    name="myrest",
    version="0.1.10",
    author="Xiaoye Xu",
    author_email="xiaoye.xu@outlook.com",
    description="A RESTful wrapper for django project",
    long_description=long_description,
    url="https://github.com/xiaoyexu/myrestengine",
    packages=find_packages('src'),
    package_dir={'': 'src'},
    package_data={
        '': ['*.py']
    },
    install_requires=[
        'django>=1.9.0'
    ],
    classifiers=[
        "Programming Language :: Python :: 3.6",
        "Framework :: Django :: 1.9",
        "License :: OSI Approved :: MIT License"
    ]
)
