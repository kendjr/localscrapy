from abc import ABC, abstractmethod
import logging

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