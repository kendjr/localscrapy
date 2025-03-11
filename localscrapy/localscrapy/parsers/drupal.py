from .base import BaseEventParser

class DrupalEventsParser(BaseEventParser):
    def parse_events(self, response):
        # This method remains unchanged as per the query
        events = []
        self.logger.info("Attempting to parse Drupal events")
        
        self.logger.debug(f"Response body: {response.text[:500]}")
        
        selectors = [
            'article.event-card',
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
                title = event.css('h3.lc-event__title a::text').get()
                month = event.css('span.lc-date-icon__item--month::text').get()
                day = event.css('span.lc-date-icon__item--day::text').get()
                year = event.css('span.lc-date-icon__item--year::text').get()
                date = f"{month} {day}, {year}" if month and day and year else None
                time = event.css('div.lc-event-info-item--time::text').get()
                categories = event.css('div.lc-event-info__item--categories::text').get()
                registration_status = event.css('div.lc-registration-label::text').get()
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
        """Extract additional details from an individual event page, including links from the description."""
        details = {}

        # Define selectors for description containers (selecting <p> elements, not just text)
        description_element_selectors = [
            'section.lc-event__content div.field-container p',  # Darien Library
            'div.field-container p',  # General Drupal field container
            'div.event-description p',  # Alternative event description
            'div.node__content p',  # Common Drupal content area
        ]

        # Define selectors for location (elements, not just text, for consistency)
        location_selectors = [
            'div.lc-event-location-address p',
            'div.lc-event-location-address div.lc-address-line',
            'div.lc-event-location p',
            'address',
        ]

        # Define selectors for contact (elements, not just text, for consistency)
        contact_selectors = [
            'div.lc-event-address-container div.lc-event-contact-name',
            'div.lc-event-location__phone a',
            'div.contact-info',
            'footer.contact',
        ]

        # Helper function to extract text and optionally links
        def extract_with_selectors(selectors, extract_links=False):
            for selector in selectors:
                elements = response.css(selector)
                if elements:
                    # Extract all text within the elements, including text in child elements like <a>
                    texts = []
                    for elem in elements:
                        # Use xpath to get all text nodes within each element
                        texts.extend(elem.xpath('.//text()').getall())
                    text = ' '.join([t.strip() for t in texts if t.strip()])
                    if text:  # Only proceed if we have text content
                        if extract_links:
                            # Use the base class's extract_links method
                            links = self.extract_links(response, selector)
                            return text, links
                        return text
            return None if not extract_links else (None, [])

        # Extract description and links
        description, links = extract_with_selectors(description_element_selectors, extract_links=True)
        if description:
            details['description'] = description
            details['links'] = links if links else []

        # Extract location
        location = extract_with_selectors(location_selectors)
        if location:
            details['location'] = location

        # Extract contact
        contact = extract_with_selectors(contact_selectors)
        if contact:
            details['contact'] = contact

        # Log the parsed details for debugging
        self.logger.debug(f"Parsed event details: {details}")

        # Return details, no need to filter None here since we only add non-None values
        return details