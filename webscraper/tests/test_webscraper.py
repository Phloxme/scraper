import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from collections import deque
from webscraper import WebScraper
import pickle  # Import added

class TestWebScraper(unittest.TestCase):
    @patch('chromadb.PersistentClient')
    def setUp(self, mock_persistent_client):
        # Create a temporary directory for the queue file and log file
        self.test_dir = tempfile.TemporaryDirectory()
        self.queue_file = os.path.join(self.test_dir.name, 'test_queue.pkl')
        self.log_file = os.path.join(self.test_dir.name, 'test_log.log')
        
        # Mock the SQLite database connection
        self.mock_conn = MagicMock(sqlite3.Connection)
        self.mock_cursor = self.mock_conn.cursor.return_value  # Mock the cursor
        self.patcher_sqlite = patch('sqlite3.connect', return_value=self.mock_conn)
        self.patcher_sqlite.start()
        # Create a mock ChromaDB client instance
        mock_client_instance = MagicMock()
        mock_persistent_client.return_value = mock_client_instance

        # Initialize the WebScraper with mock paths
        self.scraper = WebScraper(
            start_url="https://example.com",
            max_links=3,
            max_depth=2,
            collection_name="test_collection"
        )

        # Mock the embedding function if it's used during initialization
        self.scraper.embedding_fn = MagicMock(return_value="mock_embedding")

        # Ensure the WebScraper uses the mocked connection
        self.scraper.conn = self.mock_conn  # Explicitly assign the mock connection
        self.scraper.queue_file = self.queue_file

    def tearDown(self):
        # Stop all active patches
        patch.stopall()
        
        # Clean up the temporary directory
        self.test_dir.cleanup()

    @patch('webscraper.chromadb.PersistentClient')
    def test_chromadb_connection(self, mock_chromadb_client):
        # Mock the client and connection
        mock_client = mock_chromadb_client.return_value
        mock_collection = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection

        # Initialize the scraper which will use the mock client
        self.scraper = WebScraper(
            start_url="https://example.com",
            max_links=3,
            max_depth=2,
            collection_name="test_collection",
        )

        # Check that the ChromaDB client was called
        mock_chromadb_client.assert_called_once()
        mock_client.get_or_create_collection.assert_called_once_with(
            name="test_collection", embedding_function=self.scraper.embedding_fn
        )

    @patch('webscraper.webdriver.Chrome')
    def test_fetch_with_headless_browser(self, MockChrome):
        # Mock the Chrome WebDriver and its methods
        mock_driver = MockChrome.return_value
        mock_driver.page_source = "<html></html>"
        
        # Test fetching a page
        html_content = self.scraper.fetch_with_headless_browser(self.scraper.start_url)
        
        mock_driver.get.assert_called_once_with(self.scraper.start_url)
        mock_driver.quit.assert_called_once()
        self.assertEqual(html_content, "<html></html>")
    
    def test_extract_links(self):
        # Test extracting valid links from HTML content
        html_content = '''
        <html>
            <body>
                <a href="https://example.com/page1">Page 1</a>
                <a href="https://example.com/page2">Page 2</a>
                <a href="https://anotherdomain.com/page3">Page 3</a>
            </body>
        </html>
        '''
        links = self.scraper.extract_links(html_content)
        
        # Only links starting with the start_url should be extracted
        self.assertEqual(links, ["https://example.com/page1", "https://example.com/page2"]) 
    
    def test_extract_info(self):
        # Test extracting title and content summary from HTML content
        soup = MagicMock()
        soup.title.string.strip.return_value = "Test Title"
        paragraphs = [MagicMock(get_text=MagicMock(return_value="Paragraph 1")),
                      MagicMock(get_text=MagicMock(return_value="Paragraph 2")),
                      MagicMock(get_text=MagicMock(return_value="Paragraph 3")),
                      MagicMock(get_text=MagicMock(return_value="Paragraph 4")),
                      MagicMock(get_text=MagicMock(return_value="Paragraph 5"))]
        soup.find_all.return_value = paragraphs
        
        title, content = self.scraper.extract_info(soup)
        
        self.assertEqual(title, "Test Title")
        self.assertEqual(content, "Paragraph 1 Paragraph 2 Paragraph 3 Paragraph 4 Paragraph 5")
    
    @patch('webscraper.WebScraper.save_queue')
    @patch('webscraper.WebScraper.load_queue')
    @patch('webscraper.WebScraper.fetch_with_headless_browser')
    @patch('webscraper.WebScraper.extract_info')
    def test_comprehensive_crawler(self, mock_extract_info, mock_fetch_with_headless_browser, mock_load_queue, mock_save_queue):
        # Set up mock responses
        mock_load_queue.return_value = deque([(self.scraper.start_url, 0)])
        mock_fetch_with_headless_browser.return_value = "<html></html>"
        mock_extract_info.return_value = ("Test Title", "Test Content")

        # Run the crawler
        results = list(self.scraper.comprehensive_crawler())

        # Ensure the queue was loaded and saved, and the correct results were yielded
        mock_load_queue.assert_called_once()  # Ensure load_queue is called once
        mock_save_queue.assert_called()  # Ensure save_queue is called at least once
        mock_fetch_with_headless_browser.assert_called_once_with(self.scraper.start_url)  # Ensure the start URL is fetched
        self.assertEqual(results, [("Test Title", "Test Content", "<html></html>")])  # Ensure the results match the mock return value
    
    def test_load_queue_creates_new_queue_if_not_exists(self):
        with patch('os.path.exists', return_value=False):
            queue = self.scraper.load_queue()
            self.assertIsInstance(queue, deque)
            self.assertEqual(len(queue), 0)

    def test_load_queue_loads_existing_queue(self):
        existing_queue = deque([("https://example.com", 0)])
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', unittest.mock.mock_open(read_data=pickle.dumps(existing_queue))):
            queue = self.scraper.load_queue()
            self.assertEqual(queue, existing_queue)

    @patch('builtins.open', new_callable=unittest.mock.mock_open)
    def test_save_queue(self, mock_open):
        queue = deque([("https://example.com", 0)])
        self.scraper.save_queue(queue)
        mock_open.assert_called_once_with(self.scraper.queue_file, 'wb')
        mock_open().write.assert_called_once()

    def test_no_links_added_if_not_starting_with_start_url(self):
        html_content = '''
        <html>
            <body>
                <a href="https://anotherdomain.com/page1">Page 1</a>
                <a href="https://example.com/page2">Page 2</a>
            </body>
        </html>
        '''
        links = self.scraper.extract_links(html_content)
        self.assertEqual(links, ["https://example.com/page2"])

    @patch('webscraper.WebScraper.extract_info', return_value=("No title", ""))
    @patch.object(WebScraper, 'fetch_with_headless_browser', return_value="<html><title>Test</title><p>Test Content</p></html>")
    def test_process_url_without_chromadb(self, mock_fetch_with_headless_browser, mock_extract_info):
        title, content, _ = self.scraper.process_url(self.scraper.start_url, depth=0)
        mock_fetch_with_headless_browser.assert_called_once_with(self.scraper.start_url)
        mock_extract_info.assert_called_once()
        self.assertEqual(title, "No title")
        self.assertEqual(content, "")


    @patch('sqlite3.connect')  # Patch the sqlite3.connect method
    def test_save_url_metadata(self, mock_connect):
        # Mock the connection and cursor explicitly
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # Ensure the mock connection returns a mock cursor
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        # Assign the mock connection to the scraper's `conn`
        self.scraper.conn = mock_conn

        # Call the method under test
        self.scraper.save_url_metadata("https://example.com", "content_hash", 1, "Test Title")

        # Define the expected SQL query and parameters
        expected_sql = '''
            INSERT OR IGNORE INTO url_metadata (url, content_hash, depth, title)
            VALUES (?, ?, ?, ?)
        '''
        expected_params = ("https://example.com", "content_hash", 1, "Test Title")

        # Normalize the actual SQL query by stripping unnecessary whitespace
        actual_sql = mock_cursor.execute.call_args[0][0].strip()
        
        # Assert the SQL query was called with the normalized string and the expected parameters
        self.assertEqual(actual_sql.strip(), expected_sql.strip())
        mock_cursor.execute.assert_called_once_with(actual_sql, expected_params)

        # Ensure commit was called
        mock_conn.commit.assert_called_once()

    @patch('sqlite3.connect')  # Patch the sqlite3.connect method
    def test_is_url_visited(self, mock_connect):
        # Mock the connection and cursor explicitly
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # Ensure the mock connection returns a mock cursor
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        # Simulate cursor.fetchone returning a value, meaning the URL has been visited
        mock_cursor.fetchone.return_value = (1,)

        # Assign the mock connection to the scraper's `conn`
        self.scraper.conn = mock_conn

        # Call the method under test
        visited = self.scraper.is_url_visited("https://example.com/page1")

        # Ensure execute was called with the correct SQL query and parameters
        mock_cursor.execute.assert_called_once_with('SELECT 1 FROM url_metadata WHERE url = ?', ("https://example.com/page1",))

        # Ensure that the function returns True when the URL is marked as visited
        self.assertTrue(visited)


if __name__ == '__main__':
    unittest.main()
