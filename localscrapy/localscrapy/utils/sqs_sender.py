import boto3
from botocore.exceptions import ClientError
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_secret() -> str:
    """Retrieve a secret from AWS Secrets Manager."""
    secret_name = "hamlethub-story-bot"
    region_name = "us-east-1"

    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager', region_name=region_name)
    try:
        response = client.get_secret_value(SecretId=secret_name)
        return response['SecretString']
    except ClientError as e:
        logger.error(f"Error retrieving secret {secret_name}: {e}")
        raise

def send_to_sqs(queue_url: str, message_body: dict) -> None:
    """
    Send a message to the specified SQS queue.
    
    :param queue_url: The URL of the SQS queue
    :param message_body: The message body to send (must be a dict)
    """
    sqs = boto3.client('sqs')
    try:
        response = sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(message_body)
        )
        logger.info(f"Message sent to SQS: {response['MessageId']}")
    except ClientError as e:
        logger.error(f"Error sending message to SQS: {e}")
        raise