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

def send_to_sqs(queue_url: str, message_dict: dict, raise_on_error: bool = False) -> None:
    """
    Send a message to the specified Amazon SQS queue.

    :param queue_url: The URL of the SQS queue to send the message to.
    :param message_dict: A dictionary containing the message data to be sent.
    :param raise_on_error: If True, raises exceptions on errors; if False, logs errors and continues.
    :return: None
    """
    # Check if message_dict is actually a dictionary
    if not isinstance(message_dict, dict):
        logger.error("message_dict must be a dictionary")
        if raise_on_error:
            raise ValueError("message_dict must be a dictionary")
        return

    # Serialize the dictionary to a JSON string
    try:
        message_body = json.dumps(message_dict)
    except TypeError as e:
        logger.error(f"Failed to serialize message_dict to JSON: {e}")
        if raise_on_error:
            raise
        return

    # Initialize the SQS client
    sqs = boto3.client('sqs')

    # Send the message to SQS
    try:
        response = sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=message_body
        )
        logger.info(f"Message sent to SQS: {response['MessageId']}")
    except ClientError as e:
        logger.error(f"Error sending message to SQS: {e}")
        if raise_on_error:
            raise
    except Exception as e:
        logger.error(f"Unexpected error sending message to SQS: {e}")
        if raise_on_error:
            raise