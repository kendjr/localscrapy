# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class LocalScrapyItem(scrapy.Item):
    # define the fields for your item here like:
    # name = scrapy.Field()
    pass

class WebsiteStructureItem(scrapy.Item):
    url = scrapy.Field()
    domain = scrapy.Field()
    hub = scrapy.Field()
    name = scrapy.Field()
    platform = scrapy.Field()
    selectors = scrapy.Field()
    sample_data = scrapy.Field()
    detected_at = scrapy.Field()

class StoryItem(scrapy.Item):
    url = scrapy.Field()
    title = scrapy.Field()
    content = scrapy.Field()
    date = scrapy.Field()
    source = scrapy.Field()
    detected_at = scrapy.Field()
    hub = scrapy.Field()
    site_name = scrapy.Field()