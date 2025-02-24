# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html

from collections import defaultdict
import json
from datetime import datetime
from urllib.parse import urlparse

class LocalScrapyPipeline:
    def process_item(self, item, spider):
        return item

class GroupBySiteJsonPipeline:
    def __init__(self):
        # Create nested defaultdict structure
        self.structures = defaultdict(lambda: defaultdict(dict))
        
    def process_item(self, item, spider):
        # Only process items from the structure_detector spider
        if spider.name == 'structure_detector':
            hub = item.get('hub', 'unknown')
            name = item.get('name', 'unknown')
            # Convert to dict to avoid JSON serialization issues
            self.structures[hub][name] = dict(item)
        return item
    
    def close_spider(self, spider):
        if spider.name == 'structure_detector':
            try:
                # Convert defaultdict to regular dict for JSON serialization
                structured_data = {}
                for hub, sites in self.structures.items():
                    structured_data[hub] = {
                        name: site_data
                        for name, site_data in sites.items()
                    }
                
                with open('website_structures.json', 'w') as f:
                    json.dump(structured_data, f, indent=2)
            except Exception as e:
                spider.logger.error(f"Error saving structures: {str(e)}")

class StoryPipeline:
    def __init__(self):
        self.stories = defaultdict(lambda: defaultdict(list))
        
    def process_item(self, item, spider):
        if spider.name == 'story_scraper':
            hub = item.get('hub', 'unknown')
            site_name = item.get('site_name', 'unknown')
            self.stories[hub][site_name].append(dict(item))  # Convert item to dict
        return item
    
    def close_spider(self, spider):
        if spider.name == 'story_scraper':
            try:
                output = {}
                # Convert defaultdict to regular dict
                for hub, sites in self.stories.items():
                    output[hub] = {}
                    for site_name, stories in sites.items():
                        output[hub][site_name] = stories

                # Save all stories
                with open('stories.json', 'w') as f:
                    json.dump(output, f, indent=2)
                    
            except Exception as e:
                spider.logger.error(f"Error saving stories: {str(e)}")

class StructureDetectorPipeline:
    """Pipeline for saving website structure data"""
    def __init__(self):
        self.file = None
        self.structures = {}

    def open_spider(self, spider):
        if spider.name != 'structure_detector':
            return
        # Try to load existing structures
        try:
            with open('website_structures.json', 'r') as f:
                self.structures = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.structures = {}

    def close_spider(self, spider):
        if spider.name != 'structure_detector':
            return
        # Save all structures at once when spider closes
        with open('website_structures.json', 'w') as f:
            json.dump(self.structures, f, indent=2)

    def process_item(self, item, spider):
        if spider.name != 'structure_detector':
            return item

        hub = item.get('hub', 'unknown')
        site_name = item.get('name', '')
        
        # Initialize hub if it doesn't exist
        if hub not in self.structures:
            self.structures[hub] = {}
        
        # Update or create site entry
        self.structures[hub][site_name] = {
            'url': item.get('url'),
            'domain': item.get('domain', urlparse(item.get('url', '')).netloc),
            'hub': hub,
            'name': site_name,
            'platform': item.get('platform', 'unknown'),
            'selectors': item.get('selectors', {}),
            'sample_data': item.get('sample_data', []),
            'detected_at': datetime.now().isoformat()
        }
        
        return item