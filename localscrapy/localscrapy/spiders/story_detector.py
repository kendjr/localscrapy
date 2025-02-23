import scrapy
import json
import csv
import os
from urllib.parse import urlparse
import logging
from datetime import datetime

class StructureDetectorSpider(scrapy.Spider):
    name = 'structure_detector'
    
    def __init__(self, *args, **kwargs):
        super(StructureDetectorSpider, self).__init__(*args, **kwargs)
        self.logger.setLevel(logging.INFO)
        self.sites = self.load_urls()

    def load_urls(self):
        sites = []
        file_path = os.path.join(os.path.dirname(__file__), '..', 'story_urls.csv')
        try:
            with open(file_path, mode='r', newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    if all(key in row for key in ['url', 'hub', 'name']):
                        sites.append({
                            'url': row['url'],
                            'hub': row['hub'],
                            'name': row['name']
                        })
            return sites
        except Exception as e:
            self.logger.error(f"Error loading URLs: {str(e)}")
            return []


    def start_requests(self):
        for site in self.sites:
            yield scrapy.Request(
                url=site['url'],
                callback=self.detect_structure,
                meta={'site_info': site}
            )


    def detect_structure(self, response):
        domain = urlparse(response.url).netloc
        
        # Common article selectors to check
        potential_selectors = {
            'article_container': [
                'div.news-list',
                'div.articles',
                'div.post-list',
                'div.news-items',
                'div.story-list'
            ],
            'article_item': [
                'div.news-item',
                'article',
                'div.post',
                'div.story'
            ],
            'title': [
                'h2 a',
                'h3 a',
                'h4 a',
                '.title a',
                '.headline a'
            ],
            'date': [
                '.date',
                '.published',
                '.timestamp',
                'time',
                '.post-date'
            ],
            'content_preview': [
                '.summary',
                '.excerpt',
                '.description',
                '.preview',
                'p'
            ]
        }

        # Store found selectors
        working_selectors = {}
        
        # Test each selector type
        for selector_type, selectors in potential_selectors.items():
            for selector in selectors:
                elements = response.css(selector)
                if elements:
                    working_selectors[selector_type] = selector
                    self.logger.info(f"Found working selector for {selector_type}: {selector}")
                    break

        # Analyze sample data using found selectors
        sample_data = self.extract_sample_data(response, working_selectors)

        # Get site info from meta
        site_info = response.meta.get('site_info', {})
        
        # Create structure definition
        structure = {
            'url': response.url,
            'domain': domain,
            'hub': site_info.get('hub', ''),
            'name': site_info.get('name', ''),
            'platform': self.detect_platform(response),
            'selectors': working_selectors,
            'sample_data': sample_data,
            'detected_at': datetime.now().isoformat()
        }

        # Save to JSON file
        self.save_structure(structure)
        
        return structure

    def detect_platform(self, response):
        # Try to detect CMS or platform
        platform_indicators = {
            'wordpress': ['wp-content', 'wp-includes'],
            'drupal': ['drupal.js', 'drupal.min.js'],
            'blackboard': ['blackboard.com', 'bbox'],
            'schoolMessenger': ['schoolmessenger.com'],
            'squarespace': ['squarespace.com'],
            'wix': ['wix.com'],
        }

        html_str = str(response.body)
        for platform, indicators in platform_indicators.items():
            for indicator in indicators:
                if indicator in html_str.lower():
                    return platform
                
        return 'unknown'

    def extract_sample_data(self, response, selectors):
        sample_data = []
        
        # Extract directly from the page for simplicity
        title_selector = selectors.get('title', '')
        content_selector = selectors.get('content_preview', '')
        date_selector = selectors.get('date', '')
        
        # Get all titles first
        titles = response.css(title_selector)
        
        # Process up to 3 items
        for title_element in titles[:3]:
            data = {}
            
            # Extract title with href
            title_text = title_element.css('::text').get()
            if title_text:
                data['title'] = title_text.strip()
                href = title_element.attrib.get('href', '')
                if href:
                    data['url'] = response.urljoin(href)
            
            try:
                # Try to find parent container
                parents = title_element.xpath('./ancestor::div[contains(@class, "news") or contains(@class, "post") or contains(@class, "article")]')
                parent = parents[0] if parents else title_element.root.getparent()
                
                # Extract content preview from parent
                if content_selector:
                    content = parent.css(f'{content_selector}::text').get()
                    if content:
                        data['content_preview'] = content.strip()
                
                # Extract date from parent
                if date_selector:
                    date = parent.css(f'{date_selector}::text').get()
                    if date:
                        data['date'] = date.strip()
            except Exception:
                continue
            
            if data:
                sample_data.append(data)
                
        return sample_data

    def save_structure(self, structure):
        filename = f'website_structures.json'
        try:
            # Read existing structures
            try:
                with open(filename, 'r') as f:
                    structures = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                structures = []

            # Update or append new structure
            domain_structures = [s for s in structures if s['domain'] != structure['domain']]
            domain_structures.append(structure)
            
            # Save updated structures
            with open(filename, 'w') as f:
                json.dump(domain_structures, f, indent=2)
                
            self.logger.info(f"Saved structure definition to {filename}")
            
        except Exception as e:
            self.logger.error(f"Error saving structure: {str(e)}")