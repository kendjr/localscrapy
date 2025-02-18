import scrapy
import json
import brotli
import gzip

from datetime import datetime
from pathlib import Path
import os
from ..parsers import (
    WordPressEventsCalendarParser,
    LibraryEventsParser,
    DrupalEventsParser,
)


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

        spider_dir = Path(os.path.dirname(os.path.abspath(__file__)))
        project_dir = spider_dir.parent
        sources_path = project_dir / "sources" / "sources.json"

        self.logger.info(f"Looking for sources.json at: {sources_path}")
        if not sources_path.exists():
            raise FileNotFoundError(f"sources.json not found at {sources_path}")

        with open(sources_path) as f:
            self.config = json.load(f)
            self.logger.info(f"Loaded {len(self.config)} hubs from config")
            for hub_name, sources in self.config.items():
                self.logger.info(
                    f"Hub: {hub_name} has {len(sources)} sources"
                )

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

                yield scrapy.Request(
                    url=test_url,
                    callback=self.parse,
                    headers=headers,
                    dont_filter=True,
                    errback=self.handle_error,
                    meta={
                        "hub": hub_name,
                        "source": source,
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
        """Main parsing logic."""
        if response.status != 200:
            self.logger.error(f"Got status {response.status} for {response.url}")
            return

        source = response.meta['source']
        self.logger.info(f"Parsing response from {response.url} using {source['platform']}")

        # Log response headers
        self.logger.info(f"Response headers for {response.url}: {response.headers}")

        # Check if the content type is HTML
        content_type = response.headers.get('Content-Type', b'').decode('utf-8', errors='ignore')
        self.logger.info(f"Content-Type: {content_type}")

        if 'text/html' not in content_type:
            self.logger.warning(f"Non-HTML content type {content_type} for {response.url}")
            return

        # Detect and manually decompress if needed
        encoding = response.headers.get('Content-Encoding', b'').decode('utf-8', errors='ignore')
        self.logger.info(f"Detected Encoding: {encoding}")

        raw_body = response.body  # Raw response body

        if 'br' in encoding:  # Brotli compressed response
            self.logger.info("Decompressing Brotli response")
            try:
                raw_body = brotli.decompress(raw_body)
            except brotli.error as e:
                self.logger.error(f"Brotli decompression failed: {str(e)}")

        elif 'gzip' in encoding or 'deflate' in encoding:  # Gzip/Deflate compressed response
            self.logger.info("Decompressing Gzip response")
            try:
                raw_body = gzip.decompress(raw_body)
            except OSError as e:
                self.logger.error(f"Gzip decompression failed: {str(e)}")

        # Ensure response is treated as text properly
        try:
            html_content = raw_body.decode('utf-8', errors='replace')  # Decode properly
        except UnicodeDecodeError:
            self.logger.warning("Scrapy failed to decode response properly, trying ignore mode.")
            html_content = raw_body.decode('utf-8', errors='ignore')

        # Save response for debugging
        debug_file = f"debug_{source['name'].lower().replace(' ', '_')}.html"
        try:
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            self.logger.info(f"Saved debug HTML to {debug_file}")
        except Exception as e:
            self.logger.error(f"Failed to write debug file: {str(e)}")

        # Extract JSON-LD Event Data
        json_ld_scripts = response.xpath('//script[@type="application/ld+json"]/text()').getall()
        
        extracted_events = []
        for json_ld in json_ld_scripts:
            try:
                data = json.loads(json_ld)  # Parse JSON
                if isinstance(data, list):  # If multiple events in an array
                    for event in data:
                        if event.get("@type") == "Event":
                            extracted_events.append(event)
                elif data.get("@type") == "Event":  # Single event case
                    extracted_events.append(data)
            except json.JSONDecodeError:
                self.logger.warning("Skipping invalid JSON-LD")

        self.logger.info(f"Extracted {len(extracted_events)} events from JSON-LD.")

        # Get the appropriate parser
        parser = self.parser_mapping.get(source['platform'])
        if not parser:
            self.logger.error(f"No parser found for platform: {source['platform']}")
            return

        try:
            # Get events from HTML parser
            html_events = parser.parse_events(response)
            self.logger.info(f"Found {len(html_events)} events for {source['name']} via HTML parsing.")

            # Merge both extracted JSON-LD and HTML events
            all_events = html_events + extracted_events

            # Group events by hub and URL name
            grouped_events = {}
            for event in all_events:
                hub_name = response.meta['hub']
                source_name = source['name']
                event.update({
                    'source_url': response.url,
                    'hub': hub_name,
                    'source_name': source_name
                })
                
                if hub_name not in grouped_events:
                    grouped_events[hub_name] = {}
                if source_name not in grouped_events[hub_name]:
                    grouped_events[hub_name][source_name] = []
                grouped_events[hub_name][source_name].append(event)

            # Yield structured JSON
            structured_output = {}
            for hub, sources in grouped_events.items():
                structured_output[hub] = [
                    {source_name: events} for source_name, events in sources.items()
                ]
            
            yield structured_output

        except Exception as e:
            self.logger.error(f"Error parsing events for {source['name']}: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())

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