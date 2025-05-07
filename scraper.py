from playwright.sync_api import sync_playwright, TimeoutError
import json
import time
from pathlib import Path
from tqdm import tqdm
import logging
import re
import os
from datetime import datetime
from cache_manager import CacheManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class GAFContractorScraper:
    def __init__(self, test_mode=False):
        self.base_url = "https://www.gaf.com/en-us/roofing-contractors/residential"
        self.zip_code = "10013"
        self.data_dir = Path("data")
        self.data_dir.mkdir(exist_ok=True)
        self.test_mode = test_mode
        self.contractors = []
        self.cache_manager = CacheManager()
        
    def _get_last_modified(self, page):
        """Get the last modified timestamp from the page"""
        try:
            # Try to get Last-Modified header
            last_modified = page.evaluate("""
                () => {
                    const meta = document.querySelector('meta[property="article:modified_time"]');
                    if (meta) return meta.getAttribute('content');
                    return document.lastModified;
                }
            """)
            return last_modified
        except Exception as e:
            logger.error(f"Error getting last modified date: {e}")
            return None

    def _get_detailed_info(self, page, profile_url):
        """Get detailed information from a contractor's profile page"""
        try:
            # Navigate to the profile page and wait for content to load
            logger.info(f"Navigating to profile page: {profile_url}")
            page.goto(profile_url, wait_until="networkidle")
            page.wait_for_timeout(2000)  # Wait for any dynamic content to load
            
            # Get last modified timestamp
            last_modified = self._get_last_modified(page)
            
            # Extract contractor ID from URL
            contractor_id = profile_url.split('-')[-1]
            
            # Check if we need to update this contractor's data
            if not self.cache_manager.needs_update(contractor_id, last_modified):
                logger.info(f"Contractor {contractor_id} data is up to date, skipping...")
                return None
            
            # Initialize detailed info dictionary with only essential fields
            detailed_info = {
                'about': None,
                'reviews': [],
                'founding_year': None,
                'contractor_id': contractor_id,
                'state_license': None,
                'number_of_employees': None,
                'last_modified': last_modified,
                'last_updated': datetime.now().isoformat()  # Add our own timestamp
            }
            
            # Extract about section
            try:
                about_element = page.query_selector('.about-section__content, [class*="about"]')
                if about_element:
                    detailed_info['about'] = about_element.inner_text().strip()
            except Exception as e:
                logger.error(f"Error extracting about section: {str(e)}")

            # Extract reviews
            reviews = []
            seen_reviews = set()
            
            # Get reviews from the specific span elements
            review_elements = page.query_selector_all('span.contractor-reviews__quote-text')
            for element in review_elements:
                review_text = element.inner_text().strip()
                if review_text and len(review_text) > 10:
                    # Clean up the review text
                    review_text = re.sub(r'\s+', ' ', review_text).strip()
                    if review_text not in seen_reviews:
                        reviews.append(review_text)
                        seen_reviews.add(review_text)
            
            # Get the dates from the review elements
            date_elements = page.query_selector_all('div.contractor-reviews__date')
            dates = [elem.inner_text().strip() for elem in date_elements]
            
            # Combine reviews with dates if available
            if len(dates) == len(reviews):
                reviews = [f"{review} ({date})" for review, date in zip(reviews, dates)]
            
            detailed_info['reviews'] = reviews

            # Extract contractor details from the Contractor Details section
            try:
                # First try to extract data from HTML attributes
                data_elements = page.query_selector_all('[data-layer]')
                for element in data_elements:
                    data_layer = element.get_attribute('data-layer')
                    if data_layer:
                        try:
                            # Parse the JSON data from the data-layer attribute
                            data = json.loads(data_layer)
                            if isinstance(data, list):
                                data = data[0]  # Usually the first item contains the data
                            
                            # Look for event_attributes
                            if 'event_attributes' in data:
                                attrs = data['event_attributes']
                                
                                # Try to get employee count if present
                                if detailed_info['number_of_employees'] is None and 'number_of_employees' in attrs:
                                    detailed_info['number_of_employees'] = attrs['number_of_employees']
                        except json.JSONDecodeError:
                            continue

                # Look for elements containing the detail labels
                details_elements = page.query_selector_all('div[class*="details"], div[class*="info"], div[class*="contractor"], div[class*="profile"], div[class*="company"]')
                
                for element in details_elements:
                    if element:
                        text = element.inner_text().strip().lower()
                        
                        # Years in Business
                        if any(x in text for x in ['business since', 'in business since', 'established', 'founded']):
                            match = re.search(r'(?:business since|in business since|established|founded)[:\s]*(\d{4})', text)
                            if match:
                                detailed_info['founding_year'] = match.group(1)
                        
                        # State License
                        if any(x in text for x in ['license', 'lic.', 'license number', 'state license']):
                            match = re.search(r'(?:license|lic\.|license number|state license)[:\s]*([a-z0-9-]+(?:\s*[a-z0-9-]+)*)', text, re.IGNORECASE)
                            if match and not match.group(1).strip().lower() in ['number', 'license']:
                                license_number = match.group(1).strip()
                                license_number = re.sub(r'\s*number\s*', '', license_number, flags=re.IGNORECASE)
                                license_number = re.sub(r'\s+', ' ', license_number).strip()
                                if license_number:
                                    detailed_info['state_license'] = license_number
                        
                        # Number of Employees
                        if any(x in text for x in ['employees', 'team size', 'staff size', 'company size', 'team members']):
                            match = re.search(r'(?:employees|team size|staff size|company size|team members)[:\s]*(.+?)(?:\n|$)', text)
                            if match:
                                employee_text = match.group(1).strip()
                                if employee_text and not employee_text.lower() in ['number', 'size']:
                                    detailed_info['number_of_employees'] = employee_text

            except Exception as e:
                logger.error(f"Error extracting contractor details: {str(e)}")

            # Update cache with new timestamp
            if last_modified:
                self.cache_manager.update_contractor_cache(contractor_id, last_modified)

            return detailed_info
        except Exception as e:
            logger.error(f"Error in _get_detailed_info: {str(e)}")
            return None

    def start_scraping(self):
        """Main method to start the scraping process"""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()
            
            # Create two pages - one for search results and one for profiles
            search_page = context.new_page()
            profile_page = context.new_page()
            
            try:
                # Navigate to the search page
                logger.info(f"Navigating to GAF contractor search page for zip code {self.zip_code}")
                search_page.goto(self.base_url, wait_until="domcontentloaded")
                
                # Handle cookie consent if it appears
                try:
                    cookie_button = search_page.get_by_role("button", name="Accept All Cookies")
                    if cookie_button:
                        logger.info("Accepting cookies...")
                        cookie_button.click()
                except Exception as e:
                    logger.info("No cookie consent dialog found or already accepted")
                
                # First, check if we already have contractor cards visible
                logger.info("Checking for existing contractor cards...")
                search_page.evaluate("window.scrollTo(0, document.body.scrollHeight)")  # Scroll to bottom
                
                # Initialize list to store all contractors
                all_contractors_data = []
                current_page = 1
                
                while True:
                    logger.info(f"Processing page {current_page}...")
                    
                    # Look for certification cards which contain contractor info
                    cards = search_page.query_selector_all('.certification-card')
                    if not cards:
                        cards = search_page.query_selector_all('[class*="contractor"]')
                    
                    # Filter out non-company cards
                    cards = [card for card in cards if not card.inner_text().startswith('Showing')]
                    
                    if not cards:
                        logger.info("No cards found on this page, might be the end")
                        break
                    
                    logger.info(f"Found {len(cards)} cards on page {current_page}")
                    
                    # Process the cards on this page
                    for card in cards:
                        try:
                            # Get all text from the card
                            text = card.inner_text()
                            
                            # Skip if this is a pagination text
                            if text.startswith('Showing'):
                                continue
                            
                            # Extract the profile URL
                            profile_link = card.query_selector('a[href*="/roofing-contractors/"]')
                            profile_url = profile_link.get_attribute('href') if profile_link else None
                            
                            if not profile_url:
                                continue
                                
                            # Store the basic data
                            contractor_data = {
                                'profile_url': profile_url
                            }
                            
                            # Parse basic info from the card
                            lines = text.split('\n')
                            contractor_data.update({
                                'name': lines[0].strip() if len(lines) > 0 else None,
                                'rating': lines[1].strip() if len(lines) > 1 else None,
                            })
                            
                            # Extract location
                            location_element = card.query_selector('.certification-card__city')
                            location = location_element.inner_text() if location_element else None
                            if location:
                                # Remove the distance information (e.g., " - 19.9 mi")
                                location = location.split(' - ')[0].strip()
                            contractor_data['location'] = location
                            
                            # Extract phone number using regex
                            phone_match = re.search(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', text)
                            if phone_match:
                                contractor_data['phone'] = phone_match.group()
                            
                            # Get detailed info from profile page
                            detailed_info = self._get_detailed_info(profile_page, profile_url)
                            if detailed_info:
                                contractor_data.update(detailed_info)
                                all_contractors_data.append(contractor_data)
                            
                            # If in test mode, save and exit after first contractor
                            if self.test_mode:
                                logger.info("Test mode: Processing only the first contractor")
                                self._save_data(all_contractors_data)
                                return
                            
                        except Exception as e:
                            logger.error(f"Error processing card: {str(e)}")
                    
                    # Try to go to next page
                    try:
                        # Look for the next page button
                        next_button = search_page.query_selector('.pagination__next:not([disabled])')
                        if next_button:
                            logger.info("Clicking next page button...")
                            # Wait a bit before clicking to ensure the page is ready
                            search_page.wait_for_timeout(1000)
                            next_button.click()
                            # Wait for the new page to load
                            search_page.wait_for_timeout(2000)
                            # Verify we're on a new page by checking if the cards are different
                            new_cards = search_page.query_selector_all('.certification-card')
                            if not new_cards:
                                new_cards = search_page.query_selector_all('[class*="contractor"]')
                            if len(new_cards) > 0:
                                current_page += 1
                                logger.info(f"Successfully navigated to page {current_page}")
                            else:
                                logger.error("Failed to load new page, retrying...")
                                search_page.reload()
                                search_page.wait_for_timeout(2000)
                        else:
                            logger.info("No next page button found, we're done!")
                            break
                    except Exception as e:
                        logger.error(f"Error navigating to next page: {str(e)}")
                        # Try to recover by reloading the page
                        try:
                            logger.info("Attempting to recover by reloading the page...")
                            search_page.reload()
                            search_page.wait_for_timeout(2000)
                        except Exception as reload_error:
                            logger.error(f"Failed to recover: {str(reload_error)}")
                            break
                
                # Save all the data
                if all_contractors_data:
                    self._save_data(all_contractors_data)
                    logger.info(f"Saved data for {len(all_contractors_data)} total contractors across {current_page} pages")
                else:
                    logger.error("No contractor data found")
                
            except Exception as e:
                logger.error(f"An error occurred during scraping: {str(e)}")
            finally:
                context.close()
                browser.close()
    
    def _save_data(self, data):
        """Save the scraped data to a JSON file"""
        output_file = self.data_dir / "contractors.json"
        # Load existing data if it exists
        existing_data = []
        if output_file.exists():
            try:
                with open(output_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            except Exception as e:
                logger.error(f"Error loading existing data: {e}")
        
        # Create a map of existing contractors by ID
        existing_contractors = {c.get('contractor_id'): c for c in existing_data}
        
        # Update or add new contractors
        for contractor in data:
            contractor_id = contractor.get('contractor_id')
            if contractor_id:
                existing_contractors[contractor_id] = contractor
        
        # Convert back to list
        updated_data = list(existing_contractors.values())
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(updated_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Data saved to {output_file} with {len(updated_data)} contractors")

if __name__ == '__main__':
    scraper = GAFContractorScraper(test_mode=True)
    scraper.start_scraping() 