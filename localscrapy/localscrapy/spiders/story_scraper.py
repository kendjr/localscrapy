import scrapy
import json
import logging
from datetime import datetime
from urllib.parse import urljoin
from localscrapy.items import StoryItem
from collections import defaultdict
import re

class StoryScraperSpider(scrapy.Spider):
    name = 'story_scraper'
    
    def __init__(self, *args, **kwargs):
        super(StoryScraperSpider, self).__init__(*args, **kwargs)
        self.logger.setLevel(logging.INFO)
        self.structures = self.load_site_structures()
        self.max_stories_per_site = 5  # Limit per site
        self.stories_scraped = defaultdict(int)  # Count per site

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
                selectors = site_data.get('selectors', {})
                
                self.logger.info(f"Starting scrape of {site_name} ({url})")
                yield scrapy.Request(
                    url=url,
                    callback=self.parse_stories,
                    meta={
                        'hub': hub,
                        'site_name': site_name,
                        'selectors': selectors,
                        'platform': site_data.get('platform', 'unknown')
                    }
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

    def parse_stories(self, response):
        hub = response.meta['hub']
        site_name = response.meta['site_name']
        selectors = response.meta['selectors']
        platform = response.meta['platform']
        
        # Check site-specific limit
        if self.stories_scraped[site_name] >= self.max_stories_per_site:
            self.logger.info(f"Reached maximum stories limit for {site_name} ({self.max_stories_per_site})")
            return
        
        # Get selectors
        title_selector = selectors.get('title', '')
        
        # Find all story titles using a cascading approach
        stories = []
        
        # 1. First try the site-specific selector if available
        if title_selector:
            stories = self.safe_css(response, title_selector)
        
        # 2. If no stories found, try platform-specific selectors
        if not stories:
            platform_selectors = self.get_platform_selectors(platform)
            for selector in platform_selectors.get('title', []):
                stories = self.safe_css(response, selector)
                if stories:
                    self.logger.info(f"Using platform selector: {selector}")
                    break
        
        # 3. If still no stories, try generic backup selectors
        if not stories:
            for backup_selector in [
                'a.title', '.news-title a', '.article-title a', '.story-link', 
                'div.title a', '.headline a', 'a[href*="article"]', 'a[href*="story"]', 
                'a[href*="news"]', '.data-title a', 'h4 a', 'h3 a', 'h2 a', 'h1 a'
            ]:
                stories = self.safe_css(response, backup_selector)
                if stories:
                    self.logger.info(f"Using backup selector: {backup_selector}")
                    break
        
        # Log the number of stories found
        self.logger.info(f"Found {len(stories)} potential stories for {site_name}")
        
        for story in stories:
            # Check site-specific limit again inside the loop
            if self.stories_scraped[site_name] >= self.max_stories_per_site:
                return

            try:
                # Extract story data
                title = story.css('::text').get() or ''
                if not title.strip():
                    title = story.attrib.get('title', '').strip()
                
                # Get link
                href = story.attrib.get('href', '')
                url = urljoin(response.url, href) if href else None
                
                # Debug output
                self.logger.info(f"Found story: {title} at {url}")
                
                # Only proceed if we have a valid URL
                if url:
                    yield scrapy.Request(
                        url=url,
                        callback=self.parse_full_story,
                        meta={
                            'hub': hub,
                            'site_name': site_name,
                            'selectors': selectors,
                            'platform': platform,
                            'initial_data': {
                                'title': title.strip() if title else None,
                                'content_preview': None,  # We'll get this in parse_full_story
                                'date_published': None,   # We'll get this in parse_full_story
                            }
                        }
                    )
                    
            except Exception as e:
                self.logger.error(f"Error parsing story from {site_name}: {str(e)}")

    def get_platform_selectors(self, platform):
        """Get common selectors for different platforms"""
        selectors = {
            'wordpress': {
                'title': ['h2 a', 'h3 a', '.entry-title a', '.post-title a'],
                'content': ['.entry-content p', '.post-content p', 'article p', '.content p', '.single-content p'],
                'image': ['.entry-content img', '.post-content img', 'article img', '.featured-image img', '.wp-post-image']
            },
            'drupal': {
                'title': ['.node-title a', '.field-title a', '.views-field-title a'],
                'content': ['.field-body p', '.node-content p', '.field-content p'],
                'image': ['.field-image img', '.node-content img', '.content img']
            },
            'squarespace': {
                'title': ['.entry-title a', '.blog-item-title a', '.summary-title a'],
                'content': ['.entry-content p', '.blog-item-content p', '.body-content p'],
                'image': ['.entry-content img', '.blog-item-content img', '.content-wrapper img']
            },
            'joomla': {
                'title': ['.item-title a', '.contentheading a', '.page-header a'],
                'content': ['.item-content p', '.item-page p', '.article-content p'],
                'image': ['.item-image img', '.item-content img', '.article-content img']
            },
            'wix': {
                'title': ['.post-title a', '.blog-post-title a'],
                'content': ['.post-content p', '.blog-post-content p'],
                'image': ['.post-content img', '.blog-post-image img']
            },
            'unknown': {
                'title': ['h2 a', 'h3 a', 'h4 a', '.title a', '.headline a'],
                'content': ['.article-body p', '.story-content p', '.post-body p', '.content p', 'article p'],
                'image': ['.article-image img', '.story-image img', '.featured-image img', 'article img']
            }
        }
        
        return selectors.get(platform, selectors['unknown'])

    def parse_full_story(self, response):
        site_name = response.meta['site_name']
        platform = response.meta['platform']
        
        if self.stories_scraped[site_name] >= self.max_stories_per_site:
            return
            
        try:
            selectors = response.meta['selectors']
            initial_data = response.meta['initial_data']
            hub = response.meta['hub']
            
            # For debugging - analyze page structure
            self.analyze_page_structure(response, site_name)
            
            # Extract content using a cascading approach for robustness
            
            # 1. Extract date
            date = self.extract_date(response, selectors)
            
            # 2. Extract content preview
            content_preview = self.extract_content_preview(response, selectors)
            
            # 3. Extract full content
            full_content = self.extract_full_content(response, selectors, platform)
            
            # Debug output for content extraction
            if full_content:
                self.logger.info(f"Successfully extracted full content: {len(full_content)} paragraphs")
            else:
                self.logger.warning(f"Failed to extract content with standard methods for {site_name} at {response.url}")
                # Try more aggressive content extraction methods
                full_content = self.extract_deep_content(response, site_name)
                if full_content:
                    self.logger.info(f"Extracted content using deep extraction: {len(full_content)} paragraphs")
            
            # 4. Extract images
            images = self.extract_images(response, selectors, platform)
            
            # Debug output for image extraction
            if images:
                self.logger.info(f"Successfully extracted images: {len(images)} images")
            else:
                self.logger.warning(f"Failed to extract images for {site_name} at {response.url}")
                # Try more aggressive image extraction methods
                images = self.extract_deep_images(response, site_name)
                if images:
                    self.logger.info(f"Extracted images using deep extraction: {len(images)} images")
            
            # Create StoryItem
            story_item = StoryItem(
                title=initial_data['title'],
                url=response.url,
                content={
                    'preview': content_preview,
                    'full_text': '\n\n'.join(full_content) if full_content else None,
                    'images': images
                },
                date=date,
                source=site_name,
                hub=hub,
                site_name=site_name,
                detected_at=datetime.now().isoformat()
            )
            
            # Only yield if we have the essential data
            if story_item['title'] and story_item['url']:
                self.stories_scraped[site_name] += 1
                self.logger.info(f"Scraped story: {story_item['title']} ({self.stories_scraped[site_name]}/{self.max_stories_per_site} for {site_name})")
                yield story_item
                
        except Exception as e:
            self.logger.error(f"Error parsing full story from {response.url}: {str(e)}")
    
    def analyze_page_structure(self, response, site_name):
        """Analyze page structure to aid debugging"""
        # For problematic sites like YMCA, perform detailed analysis
        if site_name == "New Canaan YMCA" or True:  # Always analyze for debugging
            # Count the paragraphs
            paragraphs = response.css('p')
            self.logger.info(f"Found {len(paragraphs)} paragraphs on page")
            
            # Look for common containers
            for container in ['article', '.post', '.entry', '.content', '.main', '.page', '.story']:
                elements = response.css(container)
                if elements:
                    self.logger.info(f"Found {len(elements)} '{container}' elements on page")
            
            # Check body classes for clues
            body_classes = response.css('body::attr(class)').get()
            if body_classes:
                self.logger.info(f"Body classes: {body_classes}")
                
            # Check for iframes that might contain content
            iframes = response.css('iframe')
            if iframes:
                self.logger.info(f"Found {len(iframes)} iframes on page")
                
            # Look for script blocks that might be loading content dynamically
            scripts = response.css('script:contains("var")')
            if scripts:
                self.logger.info(f"Found {len(scripts)} scripts with variables on page")
    
    def extract_date(self, response, selectors):
        """Extract date using multiple approaches"""
        date = None
        
        # 1. Try site-specific selector
        if 'date' in selectors:
            date_elements = self.safe_css(response, selectors['date'])
            if date_elements:
                date = date_elements[0].css('::text').get()
                if date:
                    return date.strip()
        
        # 2. Try common date selectors
        for date_sel in [
            'time::text', '.date::text', '.published::text', '.post-date::text',
            'meta[property="article:published_time"]::attr(content)',
            '.entry-date::text', '.meta-date::text', '.post-meta::text'
        ]:
            date_elements = self.safe_css(response, date_sel)
            if date_elements:
                date = date_elements[0].get()
                if date:
                    return date.strip()
        
        return date
    
    def extract_content_preview(self, response, selectors):
        """Extract content preview using multiple approaches"""
        preview = None
        
        # 1. Try site-specific selector
        if 'content_preview' in selectors:
            preview_elements = self.safe_css(response, selectors['content_preview'])
            if preview_elements:
                preview = preview_elements[0].css('::text').get()
                if preview:
                    return preview.strip()
        
        # 2. Try to get first paragraph as preview
        for preview_sel in ['p:first-child::text', '.entry-summary::text', '.excerpt::text', 'meta[name="description"]::attr(content)']:
            preview_elements = self.safe_css(response, preview_sel)
            if preview_elements:
                preview = preview_elements[0].get()
                if preview:
                    return preview.strip()
        
        return preview
    
    def extract_full_content(self, response, selectors, platform):
        """Extract full content using multiple approaches"""
        full_content = []
        
        # 1. Try site-specific selector
        if 'story_content' in selectors:
            content_elements = self.safe_css(response, f'{selectors["story_content"]}::text').getall()
            if content_elements:
                full_content = [content.strip() for content in content_elements if content and content.strip()]
                if full_content:
                    return full_content
        
        # 2. Try platform-specific selectors
        platform_selectors = self.get_platform_selectors(platform)
        for content_sel in platform_selectors.get('content', []):
            content_elements = self.safe_css(response, f'{content_sel}::text').getall()
            if content_elements:
                full_content = [content.strip() for content in content_elements if content and content.strip()]
                if full_content:
                    self.logger.info(f"Found content with platform selector: {content_sel}")
                    return full_content
        
        # 3. Try common content selectors
        for content_sel in [
            '.article p::text', '.post p::text', '.content p::text', 
            '.story p::text', '.entry p::text', '.body p::text',
            'article p::text', '.main-content p::text', 'p::text'
        ]:
            content_elements = self.safe_css(response, content_sel).getall()
            if content_elements:
                full_content = [content.strip() for content in content_elements if content and content.strip()]
                if full_content:
                    self.logger.info(f"Found content with common selector: {content_sel}")
                    return full_content
        
        return full_content
    
    def extract_deep_content(self, response, site_name):
        """Aggressive content extraction for difficult sites"""
        # Try to find any paragraphs with meaningful content
        all_paragraphs = self.safe_css(response, "p::text").getall()
        
        # Debug output
        sample_paragraphs = all_paragraphs[:3] if all_paragraphs else []
        self.logger.info(f"Deep extraction found {len(all_paragraphs)} paragraph texts. Sample: {sample_paragraphs}")
        
        # Filter out empty or very short paragraphs and copyright notices
        content = [p.strip() for p in all_paragraphs if 
                  p.strip() and 
                  len(p.strip()) > 20 and 
                  not p.strip().lower().startswith('copyright') and
                  not p.strip().lower().startswith('©')]
        
        # If we found real content, return it
        if content:
            return content
        
        # Try direct HTML parsing for YMCA site or other problematic sites
        if site_name == "New Canaan YMCA" or not content:
            # Try to extract directly from HTML
            html_content = response.body.decode('utf-8')
            
            # Look for content between paragraph tags
            p_tags = re.findall(r'<p[^>]*>(.*?)<\/p>', html_content, re.DOTALL)
            if p_tags:
                # Clean the content
                cleaned_content = []
                for p in p_tags:
                    # Remove HTML tags
                    clean_p = re.sub(r'<[^>]+>', '', p).strip()
                    if clean_p and len(clean_p) > 20:
                        cleaned_content.append(clean_p)
                
                if cleaned_content:
                    self.logger.info(f"Extracted {len(cleaned_content)} paragraphs from HTML parsing")
                    return cleaned_content
        
        # As a last resort, try to get any text blocks
        content_blocks = []
        for sel in [
            'div::text', 'section::text', 'article::text', 
            '.content::text', '.body::text', '.main::text'
        ]:
            blocks = self.safe_css(response, sel).getall()
            blocks = [b.strip() for b in blocks if b.strip() and len(b.strip()) > 40]
            if blocks:
                content_blocks.extend(blocks)
        
        return content_blocks
    
    def extract_images(self, response, selectors, platform):
        """Extract images using multiple approaches"""
        images = []
        
        # 1. Try site-specific selector
        if 'image' in selectors:
            image_elements = self.safe_css(response, selectors['image'])
            for img in image_elements:
                src = img.attrib.get('src', '')
                if src:
                    image_url = urljoin(response.url, src)
                    alt_text = img.attrib.get('alt', '')
                    images.append({
                        'url': image_url,
                        'alt_text': alt_text
                    })
            if images:
                return images
        
        # 2. Try platform-specific selectors
        platform_selectors = self.get_platform_selectors(platform)
        for img_sel in platform_selectors.get('image', []):
            image_elements = self.safe_css(response, img_sel)
            for img in image_elements:
                src = img.attrib.get('src', '')
                if src:
                    image_url = urljoin(response.url, src)
                    alt_text = img.attrib.get('alt', '')
                    images.append({
                        'url': image_url,
                        'alt_text': alt_text
                    })
            if images:
                self.logger.info(f"Found images with platform selector: {img_sel}")
                return images
        
        # 3. Try common image selectors
        for img_sel in [
            'figure img', '.image img', '.media img', '.wp-post-image',
            '.featured-image img', '.article-image img', '.content img',
            'img.size-full', 'img.size-large', 'img.attachment-large', 'img'
        ]:
            image_elements = self.safe_css(response, img_sel)
            for img in image_elements:
                src = img.attrib.get('src', '')
                if src:
                    image_url = urljoin(response.url, src)
                    alt_text = img.attrib.get('alt', '')
                    images.append({
                        'url': image_url,
                        'alt_text': alt_text
                    })
            if images:
                self.logger.info(f"Found images with common selector: {img_sel}")
                return images
        
        return images
    
    def extract_deep_images(self, response, site_name):
        """Aggressive image extraction for difficult sites"""
        images = []
        
        # Get all images on the page
        all_images = self.safe_css(response, "img")
        
        # Debug
        self.logger.info(f"Deep image extraction found {len(all_images)} img tags")
        
        # Try direct HTML parsing for problematic sites
        if site_name == "New Canaan YMCA" or not all_images:
            # Try to extract directly from HTML
            html_content = response.body.decode('utf-8')
            
            # Look for img tags with src attributes
            img_tags = re.findall(r'<img[^>]*src=[\'"](.*?)[\'"][^>]*>', html_content)
            if img_tags:
                for src in img_tags:
                    # Skip tiny images, icons, logos, etc.
                    if (not src.endswith('.ico') and
                        'logo' not in src.lower() and
                        'icon' not in src.lower() and
                        'avatar' not in src.lower()):
                        
                        image_url = urljoin(response.url, src)
                        images.append({
                            'url': image_url,
                            'alt_text': ''
                        })
                
                if images:
                    self.logger.info(f"Extracted {len(images)} images from HTML parsing")
                    return images
        
        # Filter to likely content images (skip tiny images, logos, icons)
        for img in all_images:
            src = img.attrib.get('src', '')
            # Skip common icon, social media, and tracking images
            if (src and 
                not src.endswith('.ico') and
                'logo' not in src.lower() and
                'icon' not in src.lower() and
                'avatar' not in src.lower() and
                'tracking' not in src.lower() and
                'pixel' not in src.lower() and
                'social' not in src.lower()):
                
                # Check for image dimensions if available
                width = img.attrib.get('width', '0')
                height = img.attrib.get('height', '0')
                try:
                    # Try to convert to integers
                    width = int(width) if width else 0
                    height = int(height) if height else 0
                    
                    # Skip very small images (likely icons)
                    if width > 100 and height > 100:
                        image_url = urljoin(response.url, src)
                        alt_text = img.attrib.get('alt', '')
                        images.append({
                            'url': image_url,
                            'alt_text': alt_text
                        })
                except (ValueError, TypeError):
                    # If dimensions aren't valid numbers, include the image anyway
                    image_url = urljoin(response.url, src)
                    alt_text = img.attrib.get('alt', '')
                    images.append({
                        'url': image_url,
                        'alt_text': alt_text
                    })
        
        return images