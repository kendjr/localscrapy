from .base import BaseEventParser

class LibraryEventsParser(BaseEventParser):
    def parse_events(self, response):
        """
        Parse event listings from a library events page, extracting key event information
        and standardizing datetime using the base parser's parse_datetime method.
        """
        events = []
        # Save the HTML for inspection
        with open('library_debug.html', 'w', encoding='utf-8') as f:
            f.write(response.text)
            
        self.logger.info("Attempting to parse library events")
        
        # List possible selectors for event containers
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
        
        # Define selectors for title, date, and time
        title_selectors = [
            'h3::text',
            '.event-title::text',
            '.title::text'
        ]
        date_selectors = [
            '.event-date::text',
            '.date::text',
            '.event-datetime::text'  # For cases where date and time are combined
        ]
        time_selectors = [
            '.event-time::text',
            '.time::text'
        ]
        
        for event in event_containers:
            try:
                # Extract title
                title = None
                for selector in title_selectors:
                    title = event.css(selector).get()
                    if title:
                        break
                if not title:
                    self.logger.warning("Skipping event: No title found")
                    continue
                
                # Extract date string
                date_str = None
                for selector in date_selectors:
                    date_str = event.css(selector).get()
                    if date_str:
                        break
                if not date_str:
                    self.logger.warning(f"Skipping event '{title}': No date found")
                    continue
                
                # Extract time string (optional)
                time_str = None
                for selector in time_selectors:
                    time_str = event.css(selector).get()
                    if time_str:
                        break
                
                # Standardize datetime using parse_datetime
                event_datetime = self.parse_datetime(date_str, time_str)
                if not event_datetime:
                    self.logger.warning(
                        f"Skipping event '{title}': Failed to parse datetime from "
                        f"'{date_str}' and '{time_str}'"
                    )
                    continue
                
                # Extract description container
                description_container = event.css('.event-description') or event.css('.description')
                if description_container:
                    # Extract full text from the container
                    description_text = ' '.join(description_container[0].xpath('.//text()').getall()).strip()
                    # Extract links from the container
                    links = [response.urljoin(link) for link in description_container[0].css('a::attr(href)').getall()]
                else:
                    description_text = None
                    links = []
                
                # Extract URL
                url = event.css('a::attr(href)').get()
                
                # Build event data dictionary with standardized event_datetime
                event_data = {
                    'title': title,
                    'event_datetime': event_datetime,
                    'description': description_text,
                    'url': url,
                    'links': links
                }
                
                # Add event to list
                events.append(event_data)
                self.logger.info(f"Extracted event: {title}")
                
            except Exception as e:
                self.logger.error(f"Error parsing event: {str(e)}")
                continue
        
        self.logger.info(f"Successfully parsed {len(events)} events")
        return events