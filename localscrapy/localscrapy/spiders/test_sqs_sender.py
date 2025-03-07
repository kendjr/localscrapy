import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env')
import os
from utils.sqs_sender import send_to_sqs, get_secret

def main():
    # Load environment variables from the .env file
    load_dotenv()
    
    # Get the SQS queue URL from the environment variable
    sqs_queue_url = os.getenv('SQS_QUEUE_URL')
    if not sqs_queue_url:
        raise ValueError("SQS_QUEUE_URL is not set in the .env file.")
    
    try:
        # Retrieve the bot email using get_secret
        bot_email = get_secret()
        print(f"Retrieved bot email: {bot_email}")
        
        # Create a sample test event
        test_event = {
            'hub': 'test_hub',
            'source': 'test_source',
            'event': {
                'title': 'Test Event',
                'description': 'This is a test event',
                'date': '2023-10-01'
            }
        }
        
        # Construct the message body to send to SQS
        message_body = {
            'hub': test_event['hub'],
            'source': test_event['source'],
            'event': test_event['event'],
            'bot_email': bot_email
        }
        
        # Send the message to the SQS queue
        send_to_sqs(sqs_queue_url, message_body)
        print("Test message sent successfully to SQS.")
        
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()