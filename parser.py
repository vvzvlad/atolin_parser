import requests
from urllib.parse import urlencode
import logging
from bs4 import BeautifulSoup
import time
import random
import json
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AtolinParser:
    def __init__(self):
        self.base_url = "https://atolin.ru/anketa/search"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        self.profiles = {}
        self.new_profiles = {}
        self.load_existing_profiles()

    def load_existing_profiles(self):
        try:
            if os.path.exists('profiles.json'):
                with open('profiles.json', 'r', encoding='utf-8') as f:
                    self.profiles = json.load(f)
                logger.info(f"Loaded {len(self.profiles)} existing profiles")
        except Exception as e:
            logger.error(f"Failed to load existing profiles: {str(e)}")
            self.profiles = {}

    def get_search_page(self, gender=0, age_from=18, age_to=22, location_id=140, page=1):
        params = {
            "AnketaSearch[gender][]": gender,
            "AnketaSearch[agefrom]": age_from,
            "AnketaSearch[ageto]": age_to,
            "AnketaSearch[location_id]": location_id,
            "page": page
        }
        
        url = f"{self.base_url}?{urlencode(params)}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            logger.info(f"Successfully loaded page {page} with parameters: age {age_from}-{age_to}, gender {gender}, location {location_id}")
            return response.text
        except requests.RequestException as e:
            logger.error(f"Failed to load page: {str(e)}")
            return None

    def get_results_container(self, html_content):
        if not html_content:
            logger.error("Empty HTML content")
            return None
            
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            results = soup.select_one("#results")
            if results:
                for item in results.find_all("div", recursive=False):
                    if "data-key" in item.attrs:
                        profile_id = item['data-key']
                        link = item.find("a", class_="viewed")
                        if link:
                            img = link.find("img")
                            # Skip profiles without photos
                            if not img or "no-photo" in img.get("class", []):
                                continue
                                
                            profile_data = {
                                "id": profile_id,
                                "photo_url": img['src'],
                                "additional_photos": None,
                                "name_location": None,
                                "status": None
                            }
                            
                            name_elem = link.find("span", class_="user-name")
                            if name_elem:
                                profile_data["name_location"] = name_elem.text.strip()
                            
                            was_elem = link.find("span", class_="user-was")
                            if was_elem:
                                status = was_elem.find("span", class_=["online", "offline", "oldline"])
                                if status:
                                    profile_data["status"] = status.text.strip()
                            
                            photo_count = link.find("span", class_="viewed-count")
                            if photo_count:
                                profile_data["additional_photos"] = photo_count.text.strip()
                            
                            # Check if this is a new profile
                            if profile_id not in self.profiles:
                                self.new_profiles[profile_id] = profile_data
                                logger.info(f"Found new profile: {profile_id}")
                            
                            # Update or add to all profiles
                            self.profiles[profile_id] = profile_data
            else:
                logger.error("Results container not found")
                return None
        except Exception as e:
            logger.error(f"Failed to parse HTML: {str(e)}")
            return None

    def collect_profiles(self, start_page=1, end_page=20, gender=0, age_from=18, age_to=22, location_id=140):
        logger.info(f"Starting collection from page {start_page} to {end_page}")
        
        for page in range(start_page, end_page + 1):
            logger.info(f"Processing page {page}")
            content = self.get_search_page(gender=gender, age_from=age_from, age_to=age_to, location_id=location_id, page=page)
            
            if content:
                self.get_results_container(content)
                
                # Random delay between requests to avoid blocking
                delay = random.uniform(2.0, 5.0)
                logger.info(f"Waiting {delay:.2f} seconds before next request")
                time.sleep(delay)
            else:
                logger.error(f"Failed to get content for page {page}")
        
        # Save new profiles to new.json
        if self.new_profiles:
            with open('new.json', 'w', encoding='utf-8') as f:
                json.dump(self.new_profiles, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved {len(self.new_profiles)} new profiles to new.json")
        else:
            logger.info("No new profiles found")
                
        # Save all profiles to profiles.json
        if self.profiles:
            with open('profiles.json', 'w', encoding='utf-8') as f:
                json.dump(self.profiles, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved {len(self.profiles)} total profiles to profiles.json")
        else:
            logger.warning("No profiles collected")

if __name__ == "__main__":
    parser = AtolinParser()
    parser.collect_profiles(start_page=1, end_page=3)
