# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html

from collections import defaultdict
import json

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
            self.structures[hub][name] = item
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