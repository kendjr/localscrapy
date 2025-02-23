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

        # Possible selectors for events
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

        for event in event_containers:
            try:
                # Extract title
                title = (event.css('h3.tribe-events-list-event-title a::text').get() or
                         event.css('h2.tribe-events-title::text').get() or
                         event.css('.tribe-events-title::text').get())

                if not title:
                    self.logger.warning("Skipping event: No title found")
                    continue  # Skip this event if no title is found
                
                # Extract date/time
                schedule = None
                schedule_selectors = [
                    'div.tribe-event-schedule-details *::text',
                    'div.tribe-events-start-date::text',
                    'span.tribe-event-date-start::text'
                ]

                for selector in schedule_selectors:
                    schedule_parts = event.css(selector).getall()
                    if schedule_parts:
                        schedule = ' '.join([s.strip() for s in schedule_parts if s.strip()])
                        break
                
                # Extract venue info
                venue_name = event.css('div.tribe-events-venue-details a::text').get()
                venue_address = ' '.join(event.css('span.tribe-address *::text').getall()).strip()

                # Extract cost
                cost = event.css('div.tribe-events-event-cost span.ticket-cost::text').get()

                # Extract description
                description = ' '.join(event.css('div.tribe-events-list-event-description p::text').getall()).strip()

                # Get URL
                url = (event.css('h3.tribe-events-list-event-title a::attr(href)').get() or
                       event.css('h2.tribe-events-title a::attr(href)').get())

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
