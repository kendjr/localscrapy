import scrapy
import re
import os
import csv
import json
from collections import defaultdict

class EventDetectorSpider(scrapy.Spider):
    name = 'event_detector'
    
    start_urls = []
    grouped_results = defaultdict(list)

    def __init__(self, *args, **kwargs):
        super(EventDetectorSpider, self).__init__(*args, **kwargs)
        self.urls_info = self.load_urls_from_csv('urls.csv')
        # Remove custom_settings and handle file writing only in closed method

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
        
        platform = self.detect_platform(response)
        event_selector = self.detect_event_selector(response, platform)

        result = {
            'url': url,
            'platform': platform,
            'event_selector': event_selector,
            'name': info['name']
        }
        self.grouped_results[info['hub']].append(result)

    def closed(self, reason):
        # Convert defaultdict to regular dict for proper JSON serialization
        output = dict(self.grouped_results)
        
        # Ensure the sources directory exists
        output_dir = os.path.join(os.path.dirname(__file__), '..', 'sources')
        os.makedirs(output_dir, exist_ok=True)
        
        # Write to JSON file
        output_path = os.path.join(output_dir, 'sources.json')
        with open(output_path, 'w') as json_file:
            json.dump(output, json_file, indent=2)

    def detect_platform(self, response):
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