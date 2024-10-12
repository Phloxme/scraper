import boto3
from botocore.exceptions import ClientError

# Configuration
REGION = 'us-east-1'  # Change this to your desired AWS region
SQS_QUEUE_NAME = 'WebScraperQueue'
DYNAMODB_TABLE_NAME = 'URLMetadata'

# Initialize boto3 clients
sqs = boto3.client('sqs', region_name=REGION)
dynamodb = boto3.resource('dynamodb', region_name=REGION)

def create_sqs_queue(queue_name):
    """Create an SQS queue."""
    try:
        response = sqs.create_queue(
            QueueName=queue_name,
            Attributes={
                'VisibilityTimeout': '60',  # Time in seconds that a message is invisible after a reader picks it up
                'MessageRetentionPeriod': '86400'  # Retain messages for 1 day
            }
        )
        print(f"SQS Queue '{queue_name}' created successfully.")
        print(f"Queue URL: {response['QueueUrl']}")
        return response['QueueUrl']
    except ClientError as e:
        print(f"Error creating SQS queue: {e.response['Error']['Message']}")
        return None

def create_dynamodb_table(table_name):
    """Create a DynamoDB table."""
    try:
        response = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {
                    'AttributeName': 'url',
                    'KeyType': 'HASH'  # Partition key
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'url',
                    'AttributeType': 'S'
                }
            ],
            ProvisionedThroughput={
                'ReadCapacityUnits': 5,
                'WriteCapacityUnits': 5
            }
        )
        print(f"DynamoDB Table '{table_name}' is being created. This may take a few minutes.")
        # Wait until the table exists.
        dynamodb.meta.client.get_waiter('table_exists').wait(TableName=table_name)
        print(f"DynamoDB Table '{table_name}' created successfully.")
        return response
    except ClientError as e:
        print(f"Error creating DynamoDB table: {e.response['Error']['Message']}")
        return None

def main():
    # Create SQS queue
    queue_url = create_sqs_queue(SQS_QUEUE_NAME)
    if not queue_url:
        print("Failed to create SQS queue. Exiting.")
        return

    # Create DynamoDB table
    table = create_dynamodb_table(DYNAMODB_TABLE_NAME)
    if not table:
        print("Failed to create DynamoDB table. Exiting.")
        return

    print("Setup completed successfully.")

if __name__ == '__main__':
    main()