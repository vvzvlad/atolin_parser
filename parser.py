import requests
from urllib.parse import urlencode
import logging
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class Profile:
    id: int
    name: str
    age: int
    city: str
    photo_count: int
    has_main_photo: bool
    last_online: str
    profile_url: str

class AtolinParser:
    def __init__(self):
        self.base_url = "https://atolin.ru/anketa/search"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    def get_search_page(self, gender=0, age_from=18, age_to=22, location_id=140, page=1) -> Optional[str]:
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

    def parse_profiles(self, html_content: str) -> List[Profile]:
        if not html_content:
            logger.error("Empty HTML content received")
            return []

        soup = BeautifulSoup(html_content, 'html.parser')
        profiles_data = []
        
        for profile_div in soup.select('#results .items div[data-key]'):
            try:
                profile_id = int(profile_div.get('data-key', 0))
                link = profile_div.select_one('a.viewed')
                if not link:
                    continue

                profile_url = f"https://atolin.ru{link.get('href')}"
                img = profile_div.select_one('.viewed-img img')
                has_main_photo = img and not 'no-photo' in img.get('class', [])
                
                photo_count_elem = profile_div.select_one('.viewed-count')
                photo_count = 1
                if photo_count_elem:
                    count_text = photo_count_elem.text.strip()
                    if count_text.startswith('+'):
                        photo_count += int(count_text[1].split()[0])
                
                name_elem = profile_div.select_one('.user-name')
                if not name_elem:
                    continue
                    
                name_parts = name_elem.text.strip().split(',')
                if len(name_parts) < 2:
                    continue
                    
                name = name_parts[0].strip().split()[0]
                location_age = name_parts[1].strip().split()
                if len(location_age) < 2:
                    continue
                    
                city = location_age[0]
                age = int(location_age[1])
                
                last_online = profile_div.select_one('.user-was span:last-child').text.strip()
                
                profile = Profile(
                    id=profile_id,
                    name=name,
                    age=age,
                    city=city,
                    photo_count=photo_count,
                    has_main_photo=has_main_photo,
                    last_online=last_online,
                    profile_url=profile_url
                )
                profiles_data.append(profile)
                
            except Exception as e:
                logger.error(f"Failed to parse profile {profile_div.get('data-key', 'unknown')}: {str(e)}")
                continue
        
        logger.info(f"Successfully parsed {len(profiles_data)} profiles")
        return profiles_data

if __name__ == "__main__":
    parser = AtolinParser()
    content = parser.get_search_page(gender=0, age_from=18, age_to=22, location_id=140, page=1)
    if content:
        profiles = parser.parse_profiles(content)
        for profile in profiles:
            print(f"{profile.name}, {profile.age}, {profile.city}, Photos: {profile.photo_count}, Last online: {profile.last_online}")
