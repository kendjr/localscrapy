from abc import ABC, abstractmethod
import logging
from datetime import datetime
from dateutil.parser import parse as parse_datetime
from dateutil import tz
import string
import re

class BaseEventParser(ABC):
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def parse_events(self, response):
        pass
    
    def extract_links(self, response, selector):
        """
        Extract all hyperlinks from the given CSS selector in the response.
        Converts relative URLs to absolute URLs.
        
        Args:
            response: The response object containing the HTML content.
            selector (str): CSS selector targeting the container with links.
        
        Returns:
            list: List of absolute URLs extracted from the selector.
        """
        container = response.css(selector)
        links = container.css('a::attr(href)').getall()
        absolute_links = [response.urljoin(link) for link in links]
        self.logger.debug(f"Extracted {len(absolute_links)} links from {selector}")
        return absolute_links
    
    def parse_datetime(self, date_str, time_str=None):
        if not date_str:
            return None
        try:
            # Regex pattern for ISO 8601 with timezone offset or 'Z'
            ISO8601_PATTERN = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}([+-]\d{2}:\d{2}|Z)$'
            
            # Check if date_str matches ISO 8601 format
            if re.match(ISO8601_PATTERN, date_str):
                # Parse directly without cleaning
                dt = parse_datetime(date_str)
            else:
                # Clean the string and parse with fuzzy=True
                cleaned_str = self.clean_string(date_str)
                if time_str:
                    cleaned_time = self.clean_string(time_str)
                    full_str = f"{cleaned_str} {cleaned_time}"
                else:
                    full_str = cleaned_str
                dt = parse_datetime(full_str, fuzzy=True)
            
            # Handle timezone: if naive, assume UTC; if aware, convert to UTC
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=tz.UTC)
            else:
                dt = dt.astimezone(tz.UTC)
            
            # Return ISO 8601 string in UTC without microseconds
            return dt.replace(microsecond=0).isoformat().replace('+00:00', 'Z')
        except Exception as e:
            # Log the error (assuming a logger exists in the class)
            if hasattr(self, 'logger'):
                self.logger.error(f"Failed to parse datetime '{date_str}': {e}")
            else:
                print(f"Failed to parse datetime '{date_str}': {e}")
            return None

    @staticmethod
    def clean_string(s):
        if s is None:
            return None
        import string
        s = s.translate(str.maketrans('', '', string.punctuation))
        return ' '.join(s.split())