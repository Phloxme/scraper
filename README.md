
# WebScraper

`WebScraper` is a highly configurable web scraper that uses Selenium for web crawling, BeautifulSoup for parsing, and ChromaDB for embedding and storing content. This package is ideal for scraping web content, extracting metadata, and optionally storing the content in a persistent database.

## Features

- **Headless Browser Scraping**: Uses Selenium for automated web scraping in a headless Chrome environment.
- **Content Parsing**: Extracts text, metadata, and links from web pages using BeautifulSoup.
- **ChromaDB Integration**: Optionally stores extracted content and embeddings using ChromaDB.
- **Multithreaded Crawling**: Enables multithreaded crawling to scrape multiple links concurrently.
- **Persistence**: Stores scraping progress and metadata in SQLite to avoid duplicate processing.
- **Configurable Limits**: Configure the depth of crawling, number of threads, and maximum links to follow.

## Installation

To install the package directly from GitHub, use:

```bash
pip install git+https://github.com/yourusername/webscraper.git
```

### Dependencies

This project requires the following Python libraries:

```
beautifulsoup4==4.12.2
chromadb==0.4.7
pydantic==1.10.16
requests==2.32.0
selenium==4.14.0
openai==1.42
kfp==2.8.0
```

You can install these dependencies via `requirements.txt`:

```bash
pip install -r requirements.txt
```

## Basic Usage

### 1. Initializing the Scraper

```python
from webscraper import WebScraper

scraper = WebScraper(
    start_url="https://example.com",
    max_links=30,
    max_depth=10,
    max_threads=3,
    skip_embedding=False,
    collection_name="example_summaries"
)
```

### 2. Starting the Crawl

There are two methods you can use to start the crawl:

- **Single-threaded crawl** (useful for simple or smaller crawls):

    ```python
    results = scraper.comprehensive_crawler()
    for title, content, html in results:
        print(f"Title: {title}")
    ```

- **Multithreaded crawl** (recommended for larger websites):

    ```python
    for title, content in scraper.comprehensive_crawler_threaded():
        print(f"Title: {title}")
    ```

### 3. Storing Results in ChromaDB

The `WebScraper` integrates with ChromaDB to store scraped content along with OpenAI-generated embeddings:

```python
scraper.store_in_chroma(
    title="Example Title", 
    content="This is some example content.", 
    url="https://example.com", 
    depth=1, 
    content_hash="hashvalue"
)
```

## Example Code

Here's a quick script to demonstrate a basic web scraping session:

```python
from webscraper import WebScraper

# Initialize the scraper
scraper = WebScraper(
    start_url="https://example.com",
    max_links=10,
    max_depth=5,
    max_threads=2
)

# Start the crawl
for title, content in scraper.comprehensive_crawler_threaded():
    print(f"Scraped Title: {title}")
```

## Logging and Debugging

Logs are saved to a file and printed in the console for easier debugging. You can access the logs in the `crawler.log` file, which logs details like:

- When a URL is processed.
- If a URL was already visited.
- Errors or exceptions during scraping.

### Example log output:

```
2024-09-06 12:00:00 - INFO - WebScraper initialized.
2024-09-06 12:00:01 - INFO - Processing URL: https://example.com
2024-09-06 12:00:02 - INFO - Stored content for URL: https://example.com in ChromaDB.
```

## Configuration Options

- **`start_url`**: The URL where the crawl begins.
- **`max_links`**: Maximum number of links to crawl.
- **`max_depth`**: Maximum depth for recursive crawling.
- **`max_threads`**: Number of threads for multithreading.
- **`skip_embedding`**: If `True`, skips embedding generation with OpenAI.
- **`collection_name`**: Name of the collection in ChromaDB to store results.

## Contributing

Feel free to contribute to this project by forking the repository, making changes, and submitting a pull request. Issues and feature requests are welcome!

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
