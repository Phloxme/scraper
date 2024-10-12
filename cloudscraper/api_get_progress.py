import json
import boto3
import os

dynamodb = boto3.resource('dynamodb')
DYNAMODB_TABLE = os.environ['DYNAMODB_TABLE']
CONFIG_TABLE = os.environ['CONFIG_TABLE']
url_table = dynamodb.Table(DYNAMODB_TABLE)
config_table = dynamodb.Table(CONFIG_TABLE)

def lambda_handler(event, context):
    statuses = ['pending', 'processing', 'completed', 'failed']
    counts = {}
    for status in statuses:
        response = url_table.query(
            IndexName='status-index',
            KeyConditionExpression=boto3.dynamodb.conditions.Key('status').eq(status),
            Select='COUNT'
        )
        counts[status] = response['Count']

    response = config_table.get_item(Key={'config_name': 'MAX_DEPTH'})
    max_depth = int(response['Item']['value']) if 'Item' in response else 3

    return {
        'statusCode': 200,
        'body': json.dumps({
            'counts': counts,
            'max_depth': max_depth
        }),
        'headers': {
            'Content-Type': 'application/json'
        }
    }
