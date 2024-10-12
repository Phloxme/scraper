import json
import logging
import os
import hashlib
import boto3
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
dynamodb = boto3.resource('dynamodb')
sqs = boto3.client('sqs')

# Environment variables
DYNAMODB_TABLE = os.environ['DYNAMODB_TABLE']
CONFIG_TABLE = os.environ['CONFIG_TABLE']
SQS_QUEUE_URL = os.environ['SQS_QUEUE_URL']
START_URL = os.environ['START_URL']
DOMAIN = urlparse(START_URL).netloc

# DynamoDB tables
url_table = dynamodb.Table(DYNAMODB_TABLE)
config_table = dynamodb.Table(CONFIG_TABLE)

def get_max_depth():
    try:
        response = config_table.get_item(Key={'config_name': 'MAX_DEPTH'})
        if 'Item' in response:
            return int(response['Item']['value'])
        else:
            return 3
    except Exception as e:
        logger.error(f"Error fetching MAX_DEPTH from DynamoDB: {e}")
        return 3

def lambda_handler(event, context):
    try:
        # Parse the request body
        body = json.loads(event['body'])
        url = body.get('url')
        depth = body.get('depth', 0)

        if not url:
            return {
                'statusCode': 400,
                'body': json.dumps({'message': 'URL is required'}),
                'headers': {'Content-Type': 'application/json'}
            }

        max_depth = get_max_depth()
        if depth > max_depth:
            return {
                'statusCode': 400,
                'body': json.dumps({'message': f'Depth {depth} exceeds MAX_DEPTH {max_depth}'}),
                'headers': {'Content-Type': 'application/json'}
            }

        # Process the URL directly
        result = process_url(url, depth)

        if result:
            title, content = result
            response = {
                'statusCode': 200,
                'body': json.dumps({'message': 'URL processed successfully', 'title': title}),
                'headers': {'Content-Type': 'application/json'}
            }
        else:
            response = {
                'statusCode': 500,
                'body': json.dumps({'message': 'Failed to process URL'}),
                'headers': {'Content-Type': 'application/json'}
            }

        return response

    except Exception as e:
        logger.error(f"Error: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': f'Error: {str(e)}'}),
            'headers': {'Content-Type': 'application/json'}
        }

def process_url(url, depth):
    if is_url_processed(url):
        logger.info(f"URL already processed: {url}")
        return None

    update_url_status(url, 'processing')

    content = fetch_with_headless_browser(url)
    if content is None:
        logger.info(f"Failed to fetch content for URL: {url}")
        update_url_status(url, 'failed')
        return None

    title, page_content = extract_info(content)
    # trunk-ignore(bandit/B324)
    content_hash = hashlib.md5(page_content.encode('utf-8')).hexdigest()

    # Save metadata and mark as completed
    save_url_metadata(url, content_hash, depth, title, status='completed')

    # Enqueue new links if depth allows
    if depth < get_max_depth():
        links = extract_links(content, url)
        for link in links:
            enqueue_url(link, depth + 1)

    return title, page_content

def get_crawl_status():
    try:
        response = config_table.get_item(Key={'config_name': 'CRAWL_STATUS'})
        if 'Item' in response:
            return response['Item']['value']
        else:
            return 'running'
    except Exception as e:
        logger.error(f"Error fetching CRAWL_STATUS from DynamoDB: {e}")
        return 'running'

def is_url_processed(url):
    try:
        response = url_table.get_item(Key={'url': url})
        if 'Item' in response and response['Item'].get('status') == 'completed':
            return True
        else:
            return False
    except Exception as e:
        logger.error(f"Error checking URL in DynamoDB: {e}")
        return False

def save_url_metadata(url, content_hash, depth, title, status='completed'):
    try:
        url_table.put_item(
            Item={
                'url': url,
                'content_hash': content_hash,
                'depth': depth,
                'title': title,
                'status': status
            }
        )
        logger.info(f"Saved metadata for URL: {url} with status: {status}")
    except Exception as e:
        logger.error(f"Error saving metadata to DynamoDB: {e}")

def update_url_status(url, status):
    try:
        url_table.update_item(
            Key={'url': url},
            UpdateExpression='SET #s = :status',
            ExpressionAttributeNames={'#s': 'status'},
            ExpressionAttributeValues={':status': status}
        )
        logger.info(f"Updated status for URL: {url} to {status}")
    except Exception as e:
        logger.error(f"Error updating status for URL: {url}, Error: {e}")

def fetch_with_headless_browser(url):
    try:
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-dev-shm-usage")
        options.binary_location = "/opt/headless-chromium"
        driver = webdriver.Chrome('/opt/chromedriver', options=options)
        driver.get(url)
        html_content = driver.page_source
        driver.quit()
        return html_content
    except Exception as e:
        logger.error(f"Error fetching content from {url}: {e}")
        return None

def extract_info(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    title = soup.title.string.strip() if soup.title else 'No title'
    paragraphs = soup.find_all('p')
    content = ' '.join([para.get_text(strip=True) for para in paragraphs[:5]])
    return title, content

def extract_links(html_content, base_url):
    soup = BeautifulSoup(html_content, 'html.parser')
    links = set()
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        href = urljoin(base_url, href)
        parsed_href = urlparse(href)
        if parsed_href.scheme in ['http', 'https'] and parsed_href.netloc == DOMAIN:
            links.add(href)
    logger.info(f"Extracted {len(links)} links from {base_url}")
    return links

def enqueue_url(url, depth):
    current_max_depth = get_max_depth()
    if depth > current_max_depth:
        logger.info(f"Depth {depth} exceeds current MAX_DEPTH {current_max_depth}. Not enqueuing {url}.")
        return
    try:
        message = {'url': url, 'depth': depth}
        sqs.send_message(
            QueueUrl=SQS_QUEUE_URL,
            MessageBody=json.dumps(message)
        )
        save_url_metadata(url, content_hash='', depth=depth, title='', status='pending')
        logger.info(f"Enqueued URL: {url} at depth {depth}")
    except Exception as e:
        logger.error(f"Error enqueuing URL: {url}, Error: {e}")
