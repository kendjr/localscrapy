from .base import BaseEventParser
import json
import re

class WordPressEventsCalendarParser(BaseEventParser):
    def parse_events(self, response):
        """
        Parse events from a WordPress events calendar page using JSON-LD or CSS selectors.
        """
        events = []
        
        # Save the HTML for debugging
        with open('wordpress_debug.html', 'w', encoding='utf-8') as f:
            f.write(response.text)

        self.logger.info("Attempting to parse WordPress events")

        ## ========== STEP 1: TRY JSON-LD PARSING FIRST ==========
        json_ld_scripts = response.xpath('//script[@type="application/ld+json"]/text()').getall()
        self.logger.info(f"Found {len(json_ld_scripts)} JSON-LD scripts")

        for idx, script in enumerate(json_ld_scripts):
            self.logger.debug(f"Processing JSON-LD script {idx}: {script[:100]}...")
            try:
                # Parse JSON and log its structure
                data = json.loads(script)
                self.logger.debug(f"Parsed data from script {idx}: type={type(data)}")
                
                # Handle both single dictionaries and lists
                items = data if isinstance(data, list) else [data] if isinstance(data, dict) else []
                if not items:
                    self.logger.debug(f"Script {idx} contains no processable data: {data}")
                    continue

                self.logger.debug(f"Script {idx} contains {len(items)} items")
                self.logger.debug(f"Types of first few items: {[type(item) for item in items[:3]]}")
                
                # Process each item in the list or single dict
                for i, event in enumerate(items):
                    self.logger.debug(f"Script {idx}, item {i}: type={type(event)}")
                    if not isinstance(event, dict):
                        self.logger.warning(f"Skipping non-dict item in script {idx}, position {i}: {event} (type: {type(event)})")
                        continue
                    if event.get("@type") != "Event":
                        self.logger.debug(f"Item {i} in script {idx} is not an Event: {event.get('@type')}")
                        continue
                    
                    # Safely extract event data with defaults and type checks
                    location = event.get("location", {})
                    if not isinstance(location, dict):
                        self.logger.warning(f"Location is not a dict in script {idx}, item {i}: {location}")
                        location = {}
                    address = location.get("address", {})
                    if not isinstance(address, dict):
                        self.logger.warning(f"Address is not a dict in script {idx}, item {i}: {address}")
                        address = {}
                    offers = event.get("offers", {})
                    if not isinstance(offers, dict):
                        self.logger.warning(f"Offers is not a dict in script {idx}, item {i}: {offers}")
                        offers = {}

                    events.append({
                        'title': event.get("name"),
                        'schedule': f"{event.get('startDate')} - {event.get('endDate')}",
                        'venue': {
                            'name': location.get("name"),
                            'address': address.get("streetAddress"),
                        },
                        'cost': offers.get("price"),
                        'description': event.get("description"),
                        'url': event.get("url")
                    })
                
                if events:
                    self.logger.info(f"Successfully parsed {len(events)} events using JSON-LD")
                    return events  # Return immediately if events are found

            except json.JSONDecodeError as e:
                self.logger.error(f"Error parsing JSON-LD in script {idx}: {str(e)}")

        ## ========== STEP 2: FALLBACK TO CSS SELECTOR PARSING ==========
        self.logger.info("No JSON-LD events found, falling back to CSS selectors.")

        # Possible selectors for event containers
        selectors = [
            'div.type-tribe_events',
            'div.tribe-events-event',
            'article.type-tribe_events',
            'div.tribe_events'
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

        # Define selector lists for each field
        title_selectors = [
            'h3.tribe-events-list-event-title a::text',
            'h3.tribe-events-calendar-list__event-title a::text',
            'h2.tribe-events-title::text',
            '.tribe-events-title::text'
        ]
        
        url_selectors = [
            'h3.tribe-events-list-event-title a::attr(href)',
            'h3.tribe-events-calendar-list__event-title a::attr(href)',
            'h2.tribe-events-title a::attr(href)'
        ]
        
        schedule_selectors = [
            'div.tribe-event-schedule-details *::text',
            'div.tribe-events-start-date::text',
            'span.tribe-event-date-start::text',
            'time.tribe-events-calendar-list__event-datetime *::text'
        ]
        
        venue_name_selectors = [
            'div.tribe-events-venue-details a::text',
            'span.tribe-events-calendar-list__event-venue-title::text'
        ]
        
        venue_address_selectors = [
            'span.tribe-address *::text',
            'span.tribe-events-calendar-list__event-venue-address::text'
        ]
        
        cost_selectors = [
            'div.tribe-events-event-cost span.ticket-cost::text',
            'span.tribe-events-c-small-cta__price::text'
        ]
        
        description_selectors = [
            'div.tribe-events-list-event-description p::text',
            'div.tribe-events-calendar-list__event-description p::text'
        ]

        for event in event_containers:
            try:
                # Extract title (single value)
                title = None
                for selector in title_selectors:
                    title = event.css(selector).get()
                    if title:
                        break
                if not title:
                    self.logger.warning("Skipping event: No title found")
                    continue
                
                # Extract schedule (multiple parts)
                schedule = None
                for selector in schedule_selectors:
                    schedule_parts = event.css(selector).getall()
                    if schedule_parts:
                        schedule = ' '.join([s.strip() for s in schedule_parts if s.strip()])
                        break
                
                # Extract venue name (single value)
                venue_name = None
                for selector in venue_name_selectors:
                    venue_name = event.css(selector).get()
                    if venue_name:
                        break
                
                # Extract venue address (multiple parts)
                venue_address = None
                for selector in venue_address_selectors:
                    venue_address_parts = event.css(selector).getall()
                    if venue_address_parts:
                        venue_address = ' '.join([s.strip() for s in venue_address_parts if s.strip()])
                        break

                # Extract cost (single value)
                cost = None
                for selector in cost_selectors:
                    cost = event.css(selector).get()
                    if cost:
                        break

                # Extract description (multiple parts)
                description = None
                for selector in description_selectors:
                    description_parts = event.css(selector).getall()
                    if description_parts:
                        description = ' '.join([s.strip() for s in description_parts if s.strip()])
                        break

                # Extract URL (single value)
                url = None
                for selector in url_selectors:
                    url = event.css(selector).get()
                    if url:
                        break

                # Debug log extracted data
                self.logger.debug(f"Extracted Event: Title: {title}, Schedule: {schedule}, Venue: {venue_name}, URL: {url}")

                events.append({
                    'title': title,
                    'schedule': schedule,
                    'venue': {
                        'name': venue_name,
                        'address': venue_address
                    },
                    'cost': cost,
                    'description': description,
                    'url': url
                })

            except Exception as e:
                self.logger.error(f"Error parsing event with CSS: {str(e)}")
                continue
        
        self.logger.info(f"Successfully parsed {len(events)} events using CSS selectors")
        return events

    def parse_event_details(self, response):
        """
        Extract additional details from an individual event page.
        """
        details = {}
        
        # Full description
        description = response.css('div.tribe-events-single-event-description ::text').getall()
        details['full_description'] = ' '.join([d.strip() for d in description if d.strip()])

        # Organizer
        organizer = response.css('div.tribe-events-meta-group-organizer dd a::text').get()
        if organizer:
            details['organizer'] = organizer

        # Ticket info
        ticket_info = response.css('div.tribe-events-event-cost ::text').get()
        if ticket_info:
            details['ticket_info'] = ticket_info.strip()

        # Event categories
        categories = response.css('span.tribe-event-categories a::text').getall()
        if categories:
            details['categories'] = categories

        self.logger.debug(f"Parsed event details: {details}")
        return details