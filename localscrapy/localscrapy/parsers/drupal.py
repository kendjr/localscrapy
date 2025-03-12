from .base import BaseEventParser

class DrupalEventsParser(BaseEventParser):
    def parse_events(self, response):
        """
        Parse event listings from a Drupal events page, extracting key event information
        and standardizing datetime using the base parser's parse_datetime method.
        """
        events = []
        self.logger.info("Attempting to parse Drupal events")
        
        # Log a snippet of the response for debugging
        self.logger.debug(f"Response body: {response.text[:500]}")
        
        # List of possible CSS selectors for event containers
        selectors = [
            'article.event-card',
            # 'div.views-row',
            # 'div.event-card',
            # '.event-list-item',
            # '.calendar-event'
        ]
        
        # Try each selector until events are found
        event_containers = None
        for selector in selectors:
            event_containers = response.css(selector)
            if event_containers:
                self.logger.info(f"Found {len(event_containers)} events using selector: {selector}")
                break
        
        if not event_containers:
            self.logger.info("No events found with the given selectors")
            return events
        
        # Process each event container
        for event in event_containers:
            try:
                # Extract raw fields
                title = event.css('h3.lc-event__title a::text').get()
                month = event.css('span.lc-date-icon__item--month::text').get()
                day = event.css('span.lc-date-icon__item--day::text').get()
                year = event.css('span.lc-date-icon__item--year::text').get()
                time = event.css('div.lc-event-info-item--time::text').get()
                categories = event.css('div.lc-event-info__item--categories::text').get()
                registration_status = event.css('div.lc-registration-label::text').get()
                url = event.css('a.lc-event__link::attr(href)').get()
                
                # Make URL absolute if relative
                if url and not url.startswith('http'):
                    url = response.urljoin(url)
                
                # Create date string if all components are present
                date_str = f"{month} {day}, {year}" if month and day and year else None
                time_str = time.strip() if time else None
                
                # Standardize datetime using base parser's parse_datetime method
                event_datetime = self.parse_datetime(date_str, time_str)
                if not event_datetime:
                    self.logger.warning(
                        f"Skipping event '{title}': Failed to parse datetime from "
                        f"'{date_str}' and '{time_str}'"
                    )
                    continue
                
                # Build event data dictionary with standardized event_datetime
                event_data = {
                    'title': title.strip() if title else None,
                    'event_datetime': event_datetime,
                    'categories': categories.strip() if categories else None,
                    'registration_status': registration_status.strip() if registration_status else None,
                    'url': url
                }
                
                # Filter out None values
                event_data = {k: v for k, v in event_data.items() if v is not None}
                
                # Add event to list if data exists
                if event_data:
                    events.append(event_data)
                    self.logger.info(f"Extracted event: {event_data['title']}")
                
            except Exception as e:
                self.logger.error(f"Error parsing event: {str(e)}")
                continue
        
        self.logger.info(f"Successfully parsed {len(events)} events")
        return events

    def parse_event_details(self, response):
        """
        Extract additional details from an individual event page, including links from
        the description. No date-related parsing is performed here.
        """
        details = {}

        # Define selectors for description containers
        description_element_selectors = [
            'section.lc-event__content div.field-container p',
            'div.field-container p',
            'div.event-description p',
            'div.node__content p',
        ]

        # Define selectors for location
        location_selectors = [
            'div.lc-event-location-address p',
            'div.lc-event-location-address div.lc-address-line',
            'div.lc-event-location p',
            'address',
        ]

        # Define selectors for contact
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
                    # Extract all text within elements, including child elements
                    texts = []
                    for elem in elements:
                        texts.extend(elem.xpath('.//text()').getall())
                    text = ' '.join([t.strip() for t in texts if t.strip()])
                    if text:
                        if extract_links:
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

        # Log parsed details
        self.logger.debug(f"Parsed event details: {details}")

        return details