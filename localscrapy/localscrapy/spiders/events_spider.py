import scrapy
import json
from pathlib import Path
import os
import gzip
import brotli
from scrapy.exceptions import CloseSpider
from ..utils.sqs_sender import send_to_sqs, get_secret
from datetime import datetime
from pathlib import Path
import os
from ..parsers import (
    WordPressEventsCalendarParser,
    LibraryEventsParser,
    DrupalEventsParser,
)

SPIDER_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
PROJECT_DIR = SPIDER_DIR.parent
OUTPUT_FILE = PROJECT_DIR / "output" / "events.json"


class EventSpider(scrapy.Spider):
    name = "event_spider"
    custom_settings = {
        "USER_AGENT": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "HTTPERROR_ALLOW_ALL": True,  # Allow handling of all HTTP status codes
    }

    def __init__(self, *args, **kwargs):
        super(EventSpider, self).__init__(*args, **kwargs)
        self.parser_mapping = {
            "wordpress": WordPressEventsCalendarParser(),
            "library": LibraryEventsParser(),
            "drupal": DrupalEventsParser(),
        }


        # Get SQS queue URL from environment variable
        self.sqs_queue_url = os.getenv('SQS_QUEUE_URL')
        if not self.sqs_queue_url:
            raise CloseSpider("SQS_QUEUE_URL environment variable not set")

        # Retrieve the email from AWS Secrets Manager
        try:
            self.bot_email = get_secret('story-bot-email')  # Replace with your secret name/ARN
            self.logger.info(f"Retrieved bot email: {self.bot_email}")
        except Exception as e:
            raise CloseSpider(f"Failed to retrieve bot email from Secrets Manager: {e}")
        
    def start_requests(self):
        self.logger.info("Starting requests for all sources")
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

        for hub_name, sources in self.config.items():
            for source in sources:
                self.logger.info(
                    f"Creating request for {source['name']} ({source['platform']})"
                )

                test_url = source["url"]
                self.logger.info(f"Testing URL: {test_url}")

                # Get the geocode from the source entry
                geocode = source.get("geocode") 

                yield scrapy.Request(
                    url=test_url,
                    callback=self.parse,
                    headers=headers,
                    dont_filter=True,
                    errback=self.handle_error,
                    meta={
                        "hub": hub_name,
                        "source": source,
                        "geocode": geocode,
                        "handle_httpstatus_list": [404, 500, 502, 503, 504],
                    },
                )

    def handle_error(self, failure):
        """Handle request failures."""
        request = failure.request
        source = request.meta["source"]
        self.logger.error(f"Failed to fetch {request.url}")
        self.logger.error(f"Error: {failure.value}")

        if failure.check(scrapy.exceptions.HttpError):
            response = failure.value.response
            self.logger.error(f"HTTP Error {response.status} for {source['name']}")
            if "alternate_url" in source:
                self.logger.info(f"Trying alternate URL: {source['alternate_url']}")
                yield scrapy.Request(
                    url=source["alternate_url"],
                    callback=self.parse,
                    meta=request.meta,
                    dont_filter=True,
                )


    def parse(self, response):
        source = response.meta['source']
        hub_name = response.meta['hub']
        source_name = source['name']
        geocode = response.meta['geocode']  # Retrieve geocode from meta

        parser = self.parser_mapping.get(source['platform'])
        if not parser:
            self.logger.error(f"No parser found for platform: {source['platform']}")
            return

        try:
            html_events = parser.parse_events(response)
            self.logger.info(f"Found {len(html_events)} events for {source_name} via HTML parsing.")

            for event in html_events:
                event['geocode'] = geocode  # Attach geocode to each event
                event_url = event.get('url')
                if event_url:
                    yield scrapy.Request(
                        url=event_url,
                        callback=self.parse_event_page,
                        errback=self.handle_event_page_error,
                        meta={
                            'hub': hub_name,
                            'source': source_name,
                            'event': event,
                            'parser': parser
                        }
                    )
                else:
                    self.logger.warning(f"No URL found for event: {event.get('title', 'unknown')}")
                    message_body = {
                        'hub': hub_name,
                        'source': source_name,
                        'event': event,
                        'bot_email': self.bot_email
                    }
                    send_to_sqs(self.sqs_queue_url, message_body)
        except Exception as e:
            self.logger.error(f"Error parsing events for {source_name}: {str(e)}")


    def parse_event_page(self, response):
        """Parse the individual event page to extract additional details."""
        event = response.meta['event']
        parser = response.meta['parser']
        hub = response.meta['hub']
        source = response.meta['source']

        try:
            # Extract additional details from the event page
            additional_details = parser.parse_event_details(response)
            self.logger.info(f"Extracted details: {additional_details}")
            # Update the event dictionary with new details
            event.update(additional_details)
            event['details_fetched'] = True
        except Exception as e:
            self.logger.error(f"Error parsing event details for {event.get('url')}: {str(e)}")
            event['details_fetched'] = False


        # Send the updated event to SQS
        message_body = {
            'hub': hub,
            'source': source,
            'event': event,
            'bot_email': self.bot_email
        }
        send_to_sqs(self.sqs_queue_url, message_body)


    def handle_event_page_error(self, failure):
        """Handle failures for individual event page requests."""
        request = failure.request
        event = request.meta['event']
        hub = request.meta['hub']
        source = request.meta['source']

        # Log the error with specific details
        if failure.check(scrapy.exceptions.HttpError):
            response = failure.value.response
            self.logger.error(f"HTTP Error {response.status} for event page {request.url}")
        else:
            self.logger.error(f"Failed to fetch event page {request.url}: {failure.value}")

        # Send the basic event data to SQS
        message_body = {
            'hub': hub,
            'source': source,
            'event': event,
            'bot_email': self.bot_email
        }
        send_to_sqs(self.sqs_queue_url, message_body)
        

    def get_next_page(self, response, pagination_config):
        """Handles pagination logic."""
        if pagination_config["type"] == "link":
            next_link = response.css(pagination_config["selector"]).get()
            if next_link:
                self.logger.info(f"Found next page link: {next_link}")
            else:
                self.logger.info("No next page link found")
            return next_link
        return None