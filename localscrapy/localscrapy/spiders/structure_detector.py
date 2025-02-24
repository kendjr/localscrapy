import scrapy
import json
import csv
import os
from urllib.parse import urlparse, urljoin
import logging
from datetime import datetime
from localscrapy.items import WebsiteStructureItem

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

    def safe_css(self, response, selector):
        """Safely apply a CSS selector with error handling"""
        if not selector or selector.strip() == '':
            return []
        try:
            return response.css(selector)
        except Exception as e:
            self.logger.error(f"Error with selector '{selector}': {str(e)}")
            return []

    def detect_structure(self, response):
        site_info = response.meta.get('site_info', {})
        main_selectors = self.detect_main_page_selectors(response)
        
        # Find a sample article link
        sample_link = None
        sample_title = None
        
        # Use the detected title selector or try common ones
        if 'title' in main_selectors:
            title_elements = self.safe_css(response, main_selectors['title'])
            if title_elements:
                href = title_elements[0].attrib.get('href', '')
                sample_title = title_elements[0].css('::text').get() or title_elements[0].attrib.get('title', '')
                if href:
                    sample_link = urljoin(response.url, href)
        
        # If no link found with the detected selector, try common patterns
        if not sample_link:
            platform = self.detect_platform(response)
            if platform == 'wordpress':
                # Try WordPress-specific selectors
                for selector in ['h2 a', 'h3 a', '.entry-title a', '.post-title a', 'article h2 a']:
                    elements = self.safe_css(response, selector)
                    if elements:
                        href = elements[0].attrib.get('href', '')
                        sample_title = elements[0].css('::text').get() or elements[0].attrib.get('title', '')
                        if href:
                            sample_link = urljoin(response.url, href)
                            main_selectors['title'] = selector
                            self.logger.info(f"Found WordPress title selector: {selector}")
                            break
            else:
                # Try general backup selectors for non-WordPress sites
                for selector in ['.news-title a', '.article-title a', '.story-link', 'div.title a', 
                                '.headline a', 'a[href*="article"]', 'a[href*="story"]', 'a[href*="news"]']:
                    elements = self.safe_css(response, selector)
                    if elements:
                        href = elements[0].attrib.get('href', '')
                        sample_title = elements[0].css('::text').get() or elements[0].attrib.get('title', '')
                        if href:
                            sample_link = urljoin(response.url, href)
                            main_selectors['title'] = selector
                            self.logger.info(f"Found backup title selector: {selector}")
                            break

        if sample_link:
            self.logger.info(f"Found sample article: {sample_title} at {sample_link}")
            yield scrapy.Request(
                url=sample_link,
                callback=self.detect_article_selectors,
                meta={
                    'site_info': site_info,
                    'main_selectors': main_selectors,
                    'sample_data': self.extract_sample_data(response, main_selectors)
                }
            )
        else:
            # If no sample link found, yield item with main page selectors only
            self.logger.warning(f"No sample article found for {site_info.get('name')}. Will create limited detection.")
            yield WebsiteStructureItem(
                url=response.url,
                domain=urlparse(response.url).netloc,
                hub=site_info.get('hub', 'unknown'),
                name=site_info.get('name', urlparse(response.url).netloc),
                platform=self.detect_platform(response),
                selectors=main_selectors,
                sample_data=self.extract_sample_data(response, main_selectors),
                detected_at=datetime.now().isoformat()
            )

    def detect_main_page_selectors(self, response):
        potential_selectors = {
            'article_item': [
                'article',
                'div.news-item',
                'div.post',
                'div.story',
                '.news-container .item',
                '.post-container .item'
            ],
            'title': [
                'h2 a', 
                'h3 a', 
                'h4 a',
                '.title a',
                '.headline a',
                '.entry-title a',
                '.post-title a',
                'a.title',
                '.news-title a',
                '.article-title a',
                '.story-link',
                'div.title a',
                'a[href*="article"]',
                'a[href*="story"]',
                'a[href*="news"]'
            ],
            'date': [
                '.post-date',
                '.date',
                'time',
                '.published',
                '.timestamp',
                '.meta-date',
                '.entry-date',
                '.article-date'
            ],
            'content_preview': [
                'p',
                '.excerpt',
                '.summary',
                '.description',
                '.preview',
                '.entry-summary',
                '.article-excerpt',
                '.post-summary'
            ]
        }

        working_selectors = {}
        for selector_type, selectors in potential_selectors.items():
            for selector in selectors:
                elements = self.safe_css(response, selector)
                if elements:
                    working_selectors[selector_type] = selector
                    self.logger.info(f"Found working selector for {selector_type}: {selector}")
                    break
        
        return working_selectors

    def detect_article_selectors(self, response):
        article_selectors = {
            'story_content': [
                'article p',
                '.post-content p',
                '.entry-content p',
                '.article-content p',
                '.story-content p',
                '.content p',
                'article .content',
                '.article-body p',
                '.main-content p',
                '.story-body p',
                '.post-body p'
            ],
            'image': [
                'article img',
                '.post-content img',
                '.entry-content img',
                '.article-content img',
                '.featured-image img',
                '.wp-post-image',
                '.post-thumbnail img',
                '.article-image img',
                '.story-image img',
                'figure img'
            ]
        }

        main_selectors = response.meta.get('main_selectors', {})
        site_info = response.meta.get('site_info', {})
        sample_data = response.meta.get('sample_data', [])

        # Test article-specific selectors
        for selector_type, selectors in article_selectors.items():
            for selector in selectors:
                elements = self.safe_css(response, selector)
                if elements:
                    main_selectors[selector_type] = selector
                    self.logger.info(f"Found working selector for {selector_type}: {selector}")
                    break

        # Update sample data with full content if available
        if sample_data and isinstance(sample_data, list) and len(sample_data) > 0:
            first_sample = sample_data[0]
            if 'story_content' in main_selectors:
                content = ' '.join(response.css(f"{main_selectors['story_content']}::text").getall())
                if content:
                    first_sample['full_content'] = content[:500]  # First 500 chars
            
            if 'image' in main_selectors:
                images = response.css(main_selectors['image'])
                image_urls = []
                for img in images[:3]:  # First 3 images
                    src = img.attrib.get('src', '')
                    if src:
                        image_urls.append(urljoin(response.url, src))
                if image_urls:
                    first_sample['image_urls'] = image_urls

        # Yield the completed item
        yield WebsiteStructureItem(
            url=site_info['url'],
            domain=urlparse(response.url).netloc,
            hub=site_info.get('hub', 'unknown'),
            name=site_info.get('name', urlparse(response.url).netloc),
            platform=self.detect_platform(response),
            selectors=main_selectors,
            sample_data=sample_data,
            detected_at=datetime.now().isoformat()
        )

    def extract_sample_data(self, response, selectors):
        sample_data = []
        title_selector = selectors.get('title', '')
        
        if not title_selector:
            return []

        titles = self.safe_css(response, title_selector)
        for title in titles[:3]:  # Get up to 3 samples
            data = {}
            
            # Get title and URL
            title_text = title.css('::text').get()
            if title_text:
                data['title'] = title_text.strip()
                href = title.attrib.get('href', '')
                if href:
                    data['url'] = urljoin(response.url, href)

            # Get preview content if available
            if 'content_preview' in selectors:
                # Try different approaches to find content
                try:
                    # Try with parent article
                    parent_article = title.xpath('ancestor::article')
                    if parent_article:
                        preview = parent_article.css(f"{selectors['content_preview']}::text").get()
                        if preview:
                            data['content_preview'] = preview.strip()
                except Exception:
                    pass
                
                # If still no content, try direct relation in DOM
                if 'content_preview' not in data:
                    try:
                        # Look for siblings or nearby elements
                        preview = title.xpath(f'..//{selectors["content_preview"]}/text()').get()
                        if preview:
                            data['content_preview'] = preview.strip()
                    except Exception:
                        pass

            if data.get('title') and data.get('url'):
                sample_data.append(data)

        return sample_data

    def detect_platform(self, response):
        html_str = str(response.body)
        
        # WordPress detection
        if 'wp-content' in html_str or 'wp-includes' in html_str:
            return 'wordpress'
        
        # Other CMS detection
        platforms = {
            'drupal': ['drupal.js', 'drupal.min.js'],
            'joomla': ['joomla', '/media/jui/'],
            'squarespace': ['squarespace.com', 'static1.squarespace'],
            'wix': ['wix.com', 'wixstatic'],
            'shopify': ['shopify.com', '.myshopify.'],
            'blackboard': ['blackboard.com', 'bbox'],
            'schoolMessenger': ['schoolmessenger.com']
        }
        
        for platform, indicators in platforms.items():
            for indicator in indicators:
                if indicator.lower() in html_str.lower():
                    return platform
                
        return 'unknown'