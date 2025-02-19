# newcanaanite/newcanaanite/parsers/library.py
from .base import BaseEventParser

class LibraryEventsParser(BaseEventParser):
    def parse_events(self, response):
        events = []
        # Save the HTML for inspection
        with open('library_debug.html', 'w', encoding='utf-8') as f:
            f.write(response.text)
            
        self.logger.info("Attempting to parse library events")
        
        # List possible selectors
        selectors = [
            'div.event-listing',
            'div.event-item',
            'div.eventlist-event',
            '.event-container'
        ]
        
        event_containers = None
        used_selector = None
        
        for selector in selectors:
            event_containers = response.css(selector)
            if event_containers:
                self.logger.info(f"Found {len(event_containers)} events using selector: {selector}")
                used_selector = selector
                break
        
        if not event_containers:
            self.logger.error("No events found with any known selector")
            self.logger.info("Available classes on page: %s", 
                           set(response.css('*::attr(class)').getall()))
            return events
            
        for event in event_containers:
            try:
                # Extract title
                title = (event.css('h3::text').get() or
                        event.css('.event-title::text').get() or
                        event.css('.title::text').get())
                
                # Extract date
                date = (event.css('.event-date::text').get() or
                       event.css('.date::text').get() or
                       event.css('.time::text').get())
                
                # Extract description
                description = (event.css('.event-description::text').get() or
                             event.css('.description::text').get())
                
                # Extract URL
                url = event.css('a::attr(href)').get()
                
                if title:  # Only add event if we at least found a title
                    events.append({
                        'title': title,
                        'schedule': date,
                        'description': description,
                        'url': url
                    })
                    
            except Exception as e:
                self.logger.error(f"Error parsing event: {str(e)}")
                continue
        
        self.logger.info(f"Successfully parsed {len(events)} events")
        return events