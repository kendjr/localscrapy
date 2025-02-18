import sys
if 'twisted.internet.reactor' in sys.modules:
    del sys.modules['twisted.internet.reactor']
from twisted.internet import asyncioreactor
asyncioreactor.install()

import scrapy
from scrapy.crawler import CrawlerProcess
from datetime import datetime
import json

class NewsSpider(scrapy.Spider):
    name = 'news_spider'
    
    def start_requests(self):
        urls = {
            'newcanaan_info': 'https://www.newcanaan.info/newslist.php',
            'live_newcanaan': 'https://livenewcanaan.org/news/',
            'newcanaan_cf': 'https://www.newcanaancf.org/whats-happening',
            'newcanaan_cares': 'https://newcanaancares.org/news/',
            'grace_farms': 'https://gracefarms.org/news'
        }
        
        for site_id, url in urls.items():
            yield scrapy.Request(url=url, callback=self.parse, meta={'site_id': site_id})

    def parse(self, response):
        site_id = response.meta['site_id']
        articles = []
        
        if site_id == 'newcanaan_info':
            articles = response.css('.newsarticle')
            for article in articles:
                yield {
                    'source': response.url,
                    'title': article.css('h3::text').get().strip(),
                    'date': article.css('.newsdate::text').get().strip(),
                    'content': article.css('.newscontent::text').get().strip(),
                    'site_id': site_id
                }
                
        elif site_id == 'live_newcanaan':
            articles = response.css('article.post')
            for article in articles:
                yield {
                    'source': response.url,
                    'title': article.css('h2.entry-title a::text').get().strip(),
                    'date': article.css('time.entry-date::text').get().strip(),
                    'content': article.css('.entry-content p::text').get().strip(),
                    'site_id': site_id
                }
                
        elif site_id == 'newcanaan_cf':
            articles = response.css('.news-item')
            for article in articles:
                yield {
                    'source': response.url,
                    'title': article.css('h3::text').get().strip(),
                    'date': article.css('.date::text').get().strip(),
                    'content': article.css('.excerpt::text').get().strip(),
                    'site_id': site_id
                }
                
        elif site_id == 'newcanaan_cares':
            articles = response.css('.news-post')
            for article in articles:
                yield {
                    'source': response.url,
                    'title': article.css('.post-title::text').get().strip(),
                    'date': article.css('.post-date::text').get().strip(),
                    'content': article.css('.post-excerpt::text').get().strip(),
                    'site_id': site_id
                }
                
        elif site_id == 'grace_farms':
            articles = response.css('.news-article')
            for article in articles:
                yield {
                    'source': response.url,
                    'title': article.css('h2::text').get().strip(),
                    'date': article.css('.date::text').get().strip(),
                    'content': article.css('.excerpt::text').get().strip(),
                    'site_id': site_id
                }

class GroupBySiteJsonPipeline:
    def open_spider(self, spider):
        self.items = {}

    def process_item(self, item, spider):
        site_id = item['site_id']
        if site_id not in self.items:
            self.items[site_id] = []
        self.items[site_id].append(item)
        return item

    def close_spider(self, spider):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'news_articles_{timestamp}.json'
        with open(filename, 'w') as f:
            json.dump(self.items, f, indent=2)

# Set up and run the crawler
process = CrawlerProcess(settings={
    'ITEM_PIPELINES': {'__main__.GroupBySiteJsonPipeline': 300},
    'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
})

process.crawl(NewsSpider)
process.start()