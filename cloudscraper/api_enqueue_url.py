import json
import boto3
import os

sqs = boto3.client('sqs')
SQS_QUEUE_URL = os.environ['SQS_QUEUE_URL']

def lambda_handler(event, context):
    try:
        # Get URL and optional depth from the request body
        body = json.loads(event['body'])
        url = body.get('url')
        depth = body.get('depth', 0)

        if not url:
            return {
                'statusCode': 400,
                'body': json.dumps({'message': 'URL is required'}),
                'headers': {'Content-Type': 'application/json'}
            }

        # Enqueue the URL
        message = {'url': url, 'depth': depth}
        sqs.send_message(
            QueueUrl=SQS_QUEUE_URL,
            MessageBody=json.dumps(message)
        )

        response = {
            'statusCode': 200,
            'body': json.dumps({'message': 'URL enqueued successfully'}),
            'headers': {'Content-Type': 'application/json'}
        }
        return response

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'message': f'Error: {str(e)}'}),
            'headers': {'Content-Type': 'application/json'}
        }
