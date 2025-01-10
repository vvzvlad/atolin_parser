import requests
from urllib.parse import urlencode
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AtolinParser:
    def __init__(self):
        self.base_url = "https://atolin.ru/anketa/search"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

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

if __name__ == "__main__":
    parser = AtolinParser()
    # Example usage
    content = parser.get_search_page(gender=0, age_from=18, age_to=22, location_id=140, page=1)
    if content:
        print(content[:500])  # Print first 500 characters as preview
