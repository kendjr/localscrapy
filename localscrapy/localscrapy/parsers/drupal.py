from .base import BaseEventParser

class DrupalEventsParser(BaseEventParser):
    def parse_events(self, response):
        events = []
        self.logger.info("Attempting to parse Drupal events")
        
        # Log the first 500 characters of the response body for debugging
        self.logger.debug(f"Response body: {response.text[:500]}")
        
        # Use a common selector for both libraries
        selectors = [
            'article.event-card',  # Common selector for both libraries
            # Uncomment the following lines to try additional selectors for other Drupal sites
            # 'div.views-row',
            # 'div.event-card',
            # '.event-list-item',
            # '.calendar-event'
        ]
        
        event_containers = None
        for selector in selectors:
            event_containers = response.css(selector)
            if event_containers:
                self.logger.info(f"Found {len(event_containers)} events using selector: {selector}")
                break
        
        if not event_containers:
            self.logger.info("No events found with the given selectors")
            return events
        
        for event in event_containers:
            try:
                # Extract title
                title = event.css('h3.lc-event__title a::text').get()
                
                # Extract date components
                month = event.css('span.lc-date-icon__item--month::text').get()
                day = event.css('span.lc-date-icon__item--day::text').get()
                year = event.css('span.lc-date-icon__item--year::text').get()
                date = f"{month} {day}, {year}" if month and day and year else None
                
                # Extract time
                time = event.css('div.lc-event-info-item--time::text').get()
                
                # Extract categories
                categories = event.css('div.lc-event-info__item--categories::text').get()
                
                # Extract registration status
                registration_status = event.css('div.lc-registration-label::text').get()
                
                # Extract URL
                url = event.css('a.lc-event__link::attr(href)').get()
                if url and not url.startswith('http'):
                    url = response.urljoin(url)
                
                event_data = {
                    'title': title.strip() if title else None,
                    'date': date,
                    'time': time.strip() if time else None,
                    'categories': categories.strip() if categories else None,
                    'registration_status': registration_status.strip() if registration_status else None,
                    'url': url
                }
                
                # Remove None values
                event_data = {k: v for k, v in event_data.items() if v is not None}
                
                if event_data:
                    events.append(event_data)
                    self.logger.info(f"Extracted event: {event_data['title']}")
                
            except Exception as e:
                self.logger.error(f"Error parsing event: {str(e)}")
                continue
        
        self.logger.info(f"Successfully parsed {len(events)} events")
        return events
    

    def parse_event_details(self, response):
        """Extract additional details from an individual event page."""
        details = {}

        # Define multiple selectors for each field to handle variations
        description_selectors = [
            'section.lc-event__content div.field-container p::text',  # Darien Library
            'div.field-container p::text',  # General Drupal field container
            'div.event-description p::text',  # Alternative event description
            'div.node__content p::text',  # Common Drupal content area
        ]
        location_selectors = [
            'div.lc-event-location-address p::text',  # Darien Library location name
            'div.lc-event-location-address div.lc-address-line::text',  # Address lines
            'div.lc-event-location p::text',  # Broader location container
            'address::text',  # Standard HTML address tag
        ]
        contact_selectors = [
            'div.lc-event-address-container div.lc-event-contact-name::text',  # Contact name
            'div.lc-event-location__phone a::text',  # Phone number
            'div.contact-info::text',  # Alternative contact section
            'footer.contact::text',  # Contact in footer (common in some Drupal themes)
        ]

        # Helper function to extract text using multiple selectors
        def extract_with_selectors(selectors):
            for selector in selectors:
                extracted = response.css(selector).getall()
                if extracted:
                    # Clean and join extracted text
                    return ' '.join([text.strip() for text in extracted if text.strip()])
            return None

        # Extract details
        details['description'] = extract_with_selectors(description_selectors)
        details['location'] = extract_with_selectors(location_selectors)
        details['contact'] = extract_with_selectors(contact_selectors)

        # Filter out None values and return
        return {k: v for k, v in details.items() if v is not None}