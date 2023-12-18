from setuptools import setup, find_packages
from utilmeta import __version__

with open("README.md", "r", encoding='UTF-8') as fh:
    long_description = fh.read()


setup(
    name='UtilMeta',
    version=__version__,
    description='UtilMeta - Progressive Meta framework for backend application',
    long_description=long_description,
    long_description_content_type="text/markdown",
    author='周煦林 (XuLin Zhou)',
    author_email='zxl@utilmeta.com',
    keywords="utilmeta util meta django api backend devops restful framework",
    python_requires='>=3.7',
    install_requires=['utype'],
    license="https://utilmeta.com/terms/license",
    url="https://utilmeta.com",
    project_urls={
        "Project Home": "https://utilmeta.com",
        "Documentation": "https://docs.utilmeta.com/framework-py/zh/2.0/get-started/quick-start",
        "Source Code": "https://github.com/utilmeta/utilmeta-py",
    },
    include_package_data=True,
    package_data={
        '': ['*.tmp', '*.html', '*.css', '*.js', '*.png', '*.log', '*.pid', '*.sock', '*.lua', '*.nginx']
    },
    packages=find_packages(exclude=["tests.*", "tests"]),
    entry_points={
        'console_scripts': ['meta=utilmeta.bin.meta:main'],
    },
)
