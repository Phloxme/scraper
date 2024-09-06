from setuptools import setup, find_packages

setup(
    name='webscraper',
    version='0.1.0',
    packages=find_packages(where='webscraper'),  # Automatically finds the packages
    package_dir={'': 'webscraper'},
    install_requires=[
        'beautifulsoup4==4.12.2',
        'chromadb==0.4.7',
        'pydantic==1.10.16',
        'requests==2.32.0',
        'selenium==4.14.0',
        'openai==1.42',
        'kfp==2.8.0',
    ],
    author='Kritivasas Shukla',
    author_email='kritivasas@gmail.com',
    description='A web scraper using ChromaDB, OpenAI, and BeautifulSoup.',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/yourusername/webscraper',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.10',
)
