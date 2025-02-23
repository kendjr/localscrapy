import scrapy
import json
import logging
from datetime import datetime
from urllib.parse import urljoin

class StoryScraperSpider(scrapy.Spider):
    name = 'story_scraper'
    
    def __init__(self, *args, **kwargs):
        super(StoryScraperSpider, self).__init__(*args, **kwargs)
        self.logger.setLevel(logging.INFO)
        self.structures = self.load_site_structures()

    def load_site_structures(self):
        try:
            with open('website_structures.json', 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading site structures: {str(e)}")
            return {}

    def start_requests(self):
        # Iterate through all sites in the structures
        for hub in self.structures:
            for site_name, site_data in self.structures[hub].items():
                url = site_data['url']
                selectors = site_data['selectors']
                
                self.logger.info(f"Starting scrape of {site_name} ({url})")
                yield scrapy.Request(
                    url=url,
                    callback=self.parse_stories,
                    meta={
                        'hub': hub,
                        'site_name': site_name,
                        'selectors': selectors
                    }
                )

    def parse_stories(self, response):
        hub = response.meta['hub']
        site_name = response.meta['site_name']
        selectors = response.meta['selectors']
        
        # Get title selector
        title_selector = selectors.get('title', '')
        content_selector = selectors.get('content_preview', '')
        date_selector = selectors.get('date', '')
        
        # Find all story titles
        stories = response.css(title_selector)
        
        for story in stories:
            try:
                # Extract story data
                title = story.css('::text').get()
                if not title:
                    title = story.attrib.get('title', '').strip()
                
                # Get link
                href = story.attrib.get('href', '')
                url = urljoin(response.url, href) if href else None
                
                # Try to find parent container for additional content
                try:
                    parent = story.xpath('./ancestor::div[contains(@class, "news") or contains(@class, "post") or contains(@class, "article")]')
                    parent_element = response.css(parent[0].getroottree().getpath(parent[0])) if parent else None
                except Exception:
                    parent_element = None
                    
                # Extract content preview
                content = None
                if content_selector and parent_element:
                    content = parent_element.css(f'{content_selector}::text').get()
                    if not content:
                        # Try getting content from the story element itself
                        content = story.css(f'{content_selector}::text').get()
                    if content:
                        content = content.strip()
                
                # Extract date
                date = None
                if date_selector and parent_element:
                    date = parent_element.css(f'{date_selector}::text').get()
                    if not date:
                        # Try getting date from the story element itself
                        date = story.css(f'{date_selector}::text').get()
                    if date:
                        date = date.strip()
                
                # Create story item
                story_item = {
                    'title': title.strip() if title else None,
                    'url': url,
                    'content_preview': content,
                    'date_published': date,
                    'hub': hub,
                    'site_name': site_name,
                    'scraped_at': datetime.now().isoformat()
                }
                
                # Only yield if we have at least a title and URL
                if story_item['title'] and story_item['url']:
                    yield story_item
                    
            except Exception as e:
                self.logger.error(f"Error parsing story from {site_name}: {str(e)}")