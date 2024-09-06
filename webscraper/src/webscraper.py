import logging
import os
# trunk-ignore(bandit/B403)
import pickle
import sqlite3
import traceback
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed

import chromadb
from bs4 import BeautifulSoup
from chromadb.utils import embedding_functions
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


class WebScraper:
    def __init__(
        self,
        start_url,
        max_links=30,
        max_depth=10,
        max_threads=3,
        skip_embedding=False,
        collection_name="mindtickle_summaries",
    ):
        self.start_url = start_url
        self.max_links = max_links
        self.max_depth = max_depth
        self.max_threads = max_threads
        self.skip_embedding = skip_embedding
        self.queue_file = f"./{collection_name}_crawler_queue.pkl"
        self.visited = set()
        self.link_count = 0
        self.collection = None
        self.queue = deque()  # Ensure self.queue is always initialized as a deque
        self.visited_urls = set()

        # Setup custom logger
        self.logger = self.setup_logger(collection_name)

        # Setup chromadb
        self.setup_chromadb(collection_name)
        # Setup metadata store
        self.setup_metadata_store(collection_name)

        # Test logging to verify it works
        self.logger.debug("Logger is set up.")
        self.logger.info("WebScraper initialized.")

    """ **** METADATA STORAGE START **** """

    def setup_metadata_store(self, collection_name):
        """Set up an SQLite database to store metadata about visited URLs."""
        self.metadata_db_file = f"./{collection_name}_metadata.db"
        self.conn = sqlite3.connect(self.metadata_db_file)
        cursor = self.conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS url_metadata (
                url TEXT PRIMARY KEY,
                content_hash TEXT,
                depth INTEGER,
                title TEXT,
                processed INTEGER DEFAULT 0
            )
        """
        )
        self.conn.commit()
        return self.conn

    def save_url_metadata(self, url, content_hash, depth, title=None):
        """Save metadata about a visited URL."""
        print("In save_url_metadata")
        cursor = self.conn.cursor()
        print("Cursor acquired")
        query = """
            INSERT OR IGNORE INTO url_metadata (url, content_hash, depth, title)
            VALUES (?, ?, ?, ?)
        """
        cursor.execute(query.strip(), (url, content_hash, depth, title))
        print("Execute called")
        self.conn.commit()
        print("Commit called")

    def mark_url_processed(self, url):
        """Mark the given URL as processed in the metadata database."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "UPDATE url_metadata SET processed = 1 WHERE url = ?", (url,)
            )
            self.conn.commit()
            self.logger.info(f"Marked URL as processed: {url}")
        except Exception as e:
            self.logger.error(f"Error marking URL as processed: {e}")

    def is_url_visited(self, url):
        """Check if a URL has already been visited."""
        print("In is_url_visited")
        cursor = self.conn.cursor()
        print("Cursor acquired")
        cursor.execute("SELECT 1 FROM url_metadata WHERE url = ?", (url,))
        print("Execute called")
        return cursor.fetchone() is not None

    def check_bulk_links(self, urls):
        """
        Takes a list of URLs and checks which ones are already in the metadata database.

        Args:
            urls (list): List of URLs to check.

        Returns:
            tuple: A tuple containing two lists:
                - already_in_db (list): URLs that are already in the database.
                - not_in_db (list): URLs that are not in the database.
        """
        self.logger.info("Checking bulk links in the database.")
        already_in_db = []
        not_in_db = []

        try:
            cursor = self.conn.cursor()
            # Create a tuple of URLs for the SQL query
            url_tuples = tuple(urls)
            placeholders = ", ".join("?" for _ in urls)

            # trunk-ignore(bandit/B608)
            query = f"SELECT url FROM url_metadata WHERE url IN ({placeholders})"
            cursor.execute(query, url_tuples)
            result_set = set(row[0] for row in cursor.fetchall())

            for url in urls:
                if url in result_set:
                    already_in_db.append(url)
                else:
                    not_in_db.append(url)

            self.logger.info(
                f"Checked {len(urls)} URLs. {len(already_in_db)} are already in the database."
            )

        except Exception as e:
            self.logger.error(f"An error occurred while checking bulk links: {e}")

        return already_in_db, not_in_db

    """ **** METADATA STORAGE END **** """

    def setup_logger(self, collection_name):
        """Set up the logger for this scraper."""
        logger = logging.getLogger(collection_name)
        logger.setLevel(logging.DEBUG)  # Capture everything from DEBUG level and above

        # Clear any existing handlers
        if logger.hasHandlers():
            logger.handlers.clear()

        # Create file handler
        file_handler = logging.FileHandler(f"{collection_name}_crawler.log")
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(formatter)

        # Create console handler for easier debugging (optional)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(formatter)

        # Add handlers to the logger
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        return logger

    def setup_chromadb(self, collection_name):
        try:
            # Initialize the ChromaDB client
            self.client = chromadb.PersistentClient(
                path="./chroma_data"
            )  # For persistent storage
            self.logger.info("ChromaDB Client Initialized.")

            # Define the embedding function (using OpenAI's API in this case)
            self.embedding_fn = embedding_functions.OpenAIEmbeddingFunction(
                api_key=os.getenv("OPENAI_API_KEY"), model_name="text-embedding-ada-002"
            )

            # Check for or create the collection
            self.collection = self.client.get_or_create_collection(
                name=collection_name, embedding_function=self.embedding_fn
            )
            self.logger.info(f"Collection '{collection_name}' is ready.")

        except Exception as e:
            self.logger.error(
                f"An error occurred while initializing the ChromaDB client or collection: {e}"
            )
            traceback.print_tb(e.__traceback__)

    def save_queue(self, queue):
        """Save the queue to a file."""
        self.logger.debug("Saving queue to file.")
        try:
            with open(self.queue_file, "wb") as f:
                pickle.dump(queue, f)
            self.logger.debug(f"Queue saved to '{self.queue_file}'.")
        except Exception as e:
            self.logger.error(f"Error saving queue: {e}")

    def load_queue(self):
        """Load the queue from a file, or create a new one if the file doesn't exist."""
        self.logger.debug("Loading queue from file.")
        if os.path.exists(self.queue_file):
            try:
                with open(self.queue_file, "rb") as f:
                    # trunk-ignore(bandit/B301)
                    queue = pickle.load(f)
                self.logger.debug(f"Queue loaded from '{self.queue_file}'.")
                return queue
            except Exception as e:
                self.logger.error(f"Error loading queue: {e}")
                return deque()
        else:
            self.logger.debug("No queue file found. Starting with a new queue.")
            return deque()

    def fetch_with_headless_browser(self, url):
        """Fetch a page using a headless browser to avoid bot detection."""
        self.logger.info(f"Fetching content from {url}")
        try:
            options = Options()
            options.add_argument("--headless=new")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            driver = webdriver.Chrome(options=options)
            driver.get(url)
            html_content = driver.page_source
            driver.quit()
            self.logger.debug(f"Fetched content from {url}")
            return html_content
        except Exception as e:
            self.logger.error(f"Error fetching content from {url}: {e}")
            return None

    def extract_links(self, html_content):
        """Extract all valid HTTP/HTTPS links from a webpage that start with the start_url."""
        self.logger.debug("Extracting links from HTML content.")
        try:
            soup = BeautifulSoup(html_content, "html.parser")
            all_links = soup.find_all("a", href=True)
            print(
                f"Extracted {len(all_links)} links from content.here are all the links: {all_links}"
            )
            links = [
                a["href"] for a in all_links if a["href"].startswith(self.start_url)
            ]
            # Extract all links that dont already exist in the database
            if links:
                not_valid_links, all_links = self.check_bulk_links(links)
                self.logger.debug(
                    f"Extracted links_that_already_exist: {not_valid_links}, here are all the links that dont: {all_links}"
                )
            else:
                self.logger.debug(
                    f"Extracted 0 links from content.here are all the links: {all_links}"
                )

            # Extract all valid links which belong to the domain

            self.logger.debug(
                f"Extracted {len(links)} links from content.here are all the links: {all_links}"
            )
            return links
        except Exception as e:
            self.logger.error(f"Error extracting links: {e}")
            traceback.print_tb(e.__traceback__)
            return []

    def extract_info(self, soup):
        """Extract the title and first 5 paragraphs as a summary from the BeautifulSoup object."""
        self.logger.debug("Extracting title and content from the page.")
        try:
            title = soup.title.string.strip() if soup.title else "No title"
            paragraphs = soup.find_all("p")
            content = " ".join([para.get_text(strip=True) for para in paragraphs[:5]])
            self.logger.debug(f"Extracted title: {title}")
            return title, content
        except Exception as e:
            self.logger.error(f"Error extracting info: {e}")
            return "No title", ""

    def process_url(self, url, depth):
        """Process a URL by scraping and extracting information."""
        if depth != 0 and self.is_url_visited(url):
            self.logger.info(f"Skipping already visited URL: {url}")
            return None, None, None

        self.logger.info(f"Processing URL: {url}")
        html_content = self.fetch_with_headless_browser(url)

        if not html_content:
            self.logger.info(f"Skipping {url} due to error fetching content.")

        if html_content:
            soup = BeautifulSoup(html_content, "html.parser")
            title, content = self.extract_info(soup)
            content_hash = hash(content)
            self.save_url_metadata(url, content_hash, depth)
            self.store_in_chroma(title, content, url, depth, content_hash)
            return title, content, html_content

        return None, None, html_content

    def store_in_chroma(self, title, content, url, depth, content_hash):
        """Store the title, content, and URL in ChromaDB (optional)."""
        self.logger.info(f"Storing content in ChromaDB for URL: {url}")

        if depth != 0 and self.is_already_indexed(url):
            self.logger.info(f"URL already indexed: {url}")
            return

        try:
            embedding = None
            if not self.skip_embedding:
                embedding = self.generate_embedding(content)

            self.save_url_metadata(url, content_hash, depth, title)
            if self.skip_embedding or embedding:
                self.collection.add(
                    embeddings=[embedding] if embedding else None,
                    metadatas=[
                        {
                            "title": title,
                            "content": content,
                            "url": url,
                            "content_hash": content_hash,
                            "depth": depth,
                        }
                    ],
                    ids=[url],
                )
                self.logger.debug(f"Stored content for URL: {url} in ChromaDB.")
                self.mark_url_processed(url)  # Mark the URL as processed in SQLite

        except Exception as e:
            self.logger.error(f"Error storing content in ChromaDB for URL: {url}: {e}")

    def is_already_indexed(self, url, content_hash=None):
        """Check if the URL or content has already been indexed in ChromaDB."""
        self.logger.debug(f"Checking if URL is already indexed: {url}")
        if self.collection is None:
            return False
        try:
            if self.is_url_visited(url):
                return True
        except Exception as e:
            self.logger.error(f"An error occurred during URL check: {e}")

        try:
            results = self.collection.get(ids=[url])
            if len(results["ids"]) > 0:
                return True
        except Exception as e:
            self.logger.error(f"An error occurred during indexing check: {e}")

        return False

    def generate_embedding(self, text):
        """Generate text embeddings using the OpenAI API."""
        self.logger.debug("Generating embedding for content.")
        try:
            response = self.embedding_fn(text)  # Corrected usage of embedding function
            self.logger.debug("Generated embedding for content.")
            return response
        except Exception as e:
            self.logger.error(f"Error generating embedding: {e}")
            return None

    def comprehensive_crawler_threaded(self):
        self.logger.info("Starting comprehensive crawl.")
        self.queue = self.load_queue()  # Load the queue from persistent storage
        if not self.queue:
            self.logger.info("Queue is empty, starting with the initial URL.")
            self.queue.append((self.start_url, 0))
        else:
            self.logger.info(
                f"Resuming with a queue of size: {len(self.queue)}, here is the current queue: {self.queue}"
            )

        with ThreadPoolExecutor(self.max_threads) as executor:
            futures = {
                executor.submit(self.process_url, url, depth): (url, depth)
                for url, depth in self.queue
            }
            while futures:
                for future in as_completed(futures):
                    url, depth = futures.pop(future)
                    try:
                        result = future.result()
                        if result:
                            title, content = result
                            self.link_count += 1
                            yield title, content

                            if (
                                self.link_count < self.max_links
                                and depth + 1 <= self.max_depth
                            ):
                                links = self.extract_links(result[1])
                                for link in links:
                                    if (
                                        link not in self.visited
                                        and self.link_count < self.max_links
                                    ):
                                        self.queue.append((link, depth + 1))

                    except Exception as e:
                        self.logger.error(f"Error processing {url}: {e}")

                self.save_queue(self.queue)

            if not self.queue and os.path.exists(self.queue_file):
                os.remove(self.queue_file)
                self.logger.info(
                    f"Crawl completed. Queue file '{self.queue_file}' has been deleted."
                )

        self.logger.info("Crawling completed.")

    def mark_chromadb_used(self, id):
        """Mark id has been used, not to be used in future"""
        pass

    def comprehensive_crawler(self):
        results = []
        try:
            self.logger.info("Starting comprehensive crawl.")
            self.queue = self.load_queue()  # Load the queue from persistent storage
            if not self.queue:  # If the queue is empty, start with the initial URL
                self.queue.append((self.start_url, 0))
                self.logger.info(f"Added initial URL to queue: {self.start_url}")
            else:
                self.logger.info(f"Resuming with a queue of size: {len(self.queue)}")

            while self.queue and self.link_count < self.max_links:
                url, depth = self.queue.popleft()
                self.logger.info(f"Processing URL: {url} at depth: {depth}")

                if depth > self.max_depth:
                    self.logger.info(f"Skipping {url} due to max depth reached.")
                    continue
                if url in self.visited:
                    self.logger.info(f"Skipping {url} as it has already been visited.")
                    continue

                self.visited.add(url)
                result = self.process_url(url, 0)  # Directly call the method

                if result:
                    title, content, html_content = result
                    self.link_count += 1
                    self.logger.info(f"Processed: {title}")
                    results.append((title, content, html_content))

                if self.link_count < self.max_links and depth + 1 <= self.max_depth:
                    links = self.extract_links(result[2] if result else "")
                    for link in links:
                        if (
                            link not in self.visited
                            and not self.is_url_visited(link)
                            and self.link_count < self.max_links
                        ):
                            self.queue.append((link, depth + 1))
                        else:
                            self.logger.info(f"Ignoring the link={link}")

                self.save_queue(self.queue)

            if not self.queue and os.path.exists(self.queue_file):
                os.remove(self.queue_file)
                self.logger.info(
                    f"Crawl completed. Queue file '{self.queue_file}' has been deleted."
                )

            self.logger.info("Crawling completed.")
            return results

        except Exception as e:
            self.logger.error(f"An error occurred while crawling: {e}")
            traceback.print_tb(e.__traceback__)
            return results  # Optionally return what has been processed before the exception

    def cleanup(self):
        """Clean up resources."""
        self.logger.info("Cleaning up resources.")
        self.save_queue(self.queue)
        self.conn.close()
        self.logger.info("Resources cleaned up.")
