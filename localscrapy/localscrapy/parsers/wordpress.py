from .base import BaseEventParser
import json
import re

class WordPressEventsCalendarParser(BaseEventParser):
    def parse_events(self, response):
        events = []
        
        # Save the HTML for debugging
        with open('wordpress_debug.html', 'w', encoding='utf-8') as f:
            f.write(response.text)

        self.logger.info("Attempting to parse WordPress events")

        ## ========== STEP 1: TRY JSON-LD PARSING FIRST ==========
        json_ld_scripts = response.xpath('//script[@type="application/ld+json"]/text()').getall()
        
        for script in json_ld_scripts:
            try:
                data = json.loads(script)
                if isinstance(data, list):
                    for event in data:
                        if event.get("@type") == "Event":
                            events.append({
                                'title': event.get("name"),
                                'schedule': f"{event.get('startDate')} - {event.get('endDate')}",
                                'venue': {
                                    'name': event.get("location", {}).get("name"),
                                    'address': event.get("location", {}).get("address", {}).get("streetAddress"),
                                },
                                'cost': event.get("offers", {}).get("price"),
                                'description': event.get("description"),
                                'url': event.get("url")
                            })
                if events:
                    self.logger.info(f"Successfully parsed {len(events)} events using JSON-LD")
                    return events  # If JSON-LD data was found, return immediately
            except json.JSONDecodeError as e:
                self.logger.error(f"Error parsing JSON-LD: {str(e)}")

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
                    continue  # Skip this event if no title is found
                
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
                self.logger.info(f"Extracted Event: Title: {title}, Schedule: {schedule}, Venue: {venue_name}, URL: {url}")

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
                self.logger.error(f"Error parsing event: {str(e)}")
                continue
        
        self.logger.info(f"Successfully parsed {len(events)} events using CSS selectors")
        return events
    

    def parse_event_details(self, response):
        """Extract additional details from the individual event page."""
        details = {}
        
        # Full description
        description = response.css('div.tribe-events-single-event-description ::text').getall()
        details['full_description'] = ' '.join([d.strip() for d in description if d.strip()])

        # Organizer
        organizer = response.css('div.tribe-events-meta-group-organizer dd a::text').get()
        if organizer:
            details['organizer'] = organizer

        # Add more fields as needed (examples)
        # Ticket info
        ticket_info = response.css('div.tribe-events-event-cost ::text').get()
        if ticket_info:
            details['ticket_info'] = ticket_info.strip()

        # Event categories
        categories = response.css('span.tribe-event-categories a::text').getall()
        if categories:
            details['categories'] = categories

        return details

