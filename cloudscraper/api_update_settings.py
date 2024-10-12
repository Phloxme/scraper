import json
import boto3
import os

dynamodb = boto3.resource('dynamodb')
CONFIG_TABLE = os.environ['CONFIG_TABLE']
config_table = dynamodb.Table(CONFIG_TABLE)

def lambda_handler(event, context):
    body = json.loads(event['body'])
    max_depth = body.get('max_depth')
    crawl_status = body.get('crawl_status')

    if max_depth is not None:
        config_table.put_item(
            Item={'config_name': 'MAX_DEPTH', 'value': str(max_depth)}
        )

    if crawl_status in ['running', 'paused', 'stopped']:
        config_table.put_item(
            Item={'config_name': 'CRAWL_STATUS', 'value': crawl_status}
        )

    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'Settings updated'}),
        'headers': {
            'Content-Type': 'application/json'
        }
    }
