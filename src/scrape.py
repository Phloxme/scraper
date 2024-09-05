import sys
import os

# Add the src directory to the Python path
sys.path.append(os.path.abspath('src'))

# Now you can import the WebScraper class
from webscraper import WebScraper

# Initialize the WebScraper with the desired parameters
start_url = "https://www.mindtickle.com"  # Change this to your desired start URL
max_threads = 3  # Adjust the number of threads as needed

scraper = WebScraper(
    start_url=start_url,
    max_threads=max_threads,
    skip_embedding=True,  # Set to True if you want to use ChromaDB
    max_links=5,
    max_depth=5
)

if not scraper:
    print("Failed to initialize the WebScraper.")
    exit()
else:
    scraper.logger.info("Testing logger before calling comprehensive_crawler")

# Run the comprehensive crawler and iterate over the results
try:
    print("Starting comprehensive crawler...")

    scraper.comprehensive_crawler()
    # for title, content in scraper.comprehensive_crawler():
    #     print(f"Processed: {title}")

    print("Crawling completed.")
except Exception as e:
    print(f"An error occurred during crawling: {e}")
