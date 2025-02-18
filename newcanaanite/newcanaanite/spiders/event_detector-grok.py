import scrapy
import re
import os
import csv
from collections import defaultdict

class EventDetectorSpider(scrapy.Spider):
    name = 'event_detector'
    
    start_urls = []
    grouped_results = defaultdict(list)

    custom_settings = {
        'FEEDS': {
            os.path.join(os.path.dirname(__file__), '..', 'sources', 'sources.json'): {
                'format': 'json',
                'overwrite': True,
            },
        },
    }

    def __init__(self, *args, **kwargs):
        super(EventDetectorSpider, self).__init__(*args, **kwargs)
        self.urls_info = self.load_urls_from_csv('urls.csv')  # Load URLs from CSV

    def load_urls_from_csv(self, file_name):
        urls_info = []
        file_path = os.path.join(os.path.dirname(__file__), '..', file_name)
        with open(file_path, mode='r', newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if all(key in row for key in ['url', 'hub', 'name']):
                    urls_info.append({
                        'url': row['url'],
                        'hub': row['hub'],
                        'name': row['name']
                    })
        return urls_info

    def start_requests(self):
        for info in self.urls_info:
            yield scrapy.Request(info['url'], meta={'info': info})

    def parse(self, response):
        info = response.meta['info']
        url = response.url
        
        # CMS Detection with more checks for WordPress
        platform = self.detect_platform(response)
        
        # Event CSS Selector Detection with broader search
        event_selector = self.detect_event_selector(response, platform)

        result = {
            'url': url,
            'platform': platform,
            'event_selector': event_selector,
            'name': info['name']
        }
        self.grouped_results[info['hub']].append(result)

    def closed(self, reason):
        # Write grouped data to JSON file
        with open(os.path.join(os.path.dirname(__file__), '..', 'sources', 'sources.json'), 'w') as json_file:
            import json
            json.dump(self.grouped_results, json_file, indent=2)

    def detect_platform(self, response):
        # Check for WordPress in more places
        if (response.css('meta[name="generator"][content*="WordPress"]') or
            response.css('link[href*="wp-content"]') or
            response.css('script[src*="wp-content"]') or
            response.xpath('//comment()[contains(., "wp-content")]')):
            return 'wordpress'
        elif response.css('meta[name="Generator"][content*="Drupal"]'):
            return 'drupal'
        else:
            return 'Unknown'

    def detect_event_selector(self, response, platform):
        if platform == 'wordpress':
            # Look for more common WordPress event classes
            possible_selectors = [
                'div.type-tribe_events',
                'div.tribe-events-calendar',
                'div.tribe-events-list',
                'div.events-grid',
                '.tribe-events-event',
                '.tribe-common',
                'div.event-list-item',
                'article.type-tribe_events'
            ]
        else:
            # Generic event selectors for non-WordPress or unknown platform 
            possible_selectors = [
                'article.event-card',
                'div.event',
                'article.event',
                'li.event',
                'div.events-list',
                'ul.events',
                'div.event-item',
                'div.event-block'
            ]
        
        for selector in possible_selectors:
            if response.css(selector):
                return selector
        
        return None