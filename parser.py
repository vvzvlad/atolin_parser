import requests
from urllib.parse import urlencode, urljoin
import logging
from bs4 import BeautifulSoup
import time
import random
import json
import os
import re
from typing import Dict, Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AtolinParser:
    # Location IDs
    LOCATIONS: Dict[str, int] = {
        # Capitals
        "MOSCOW": 140,
        "SAINT_PETERSBURG": 141,
        
        # CIS
        "BELARUS": 145,
        "KAZAKHSTAN": 143,
        "UKRAINE": 142,
        
        # Russian cities
        "ABAKAN": 1,
        "ADLER": 2,
        "ANAPA": 4,
        "ANGARSK": 5,
        "ARKHANGELSK": 7,
        "ASTRAKHAN": 8,
        "BARNAUL": 9,
        "BELGOROD": 10,
        "BELORECHENSK": 12,
        "BIYSK": 14,
        "BLAGOVESHCHENSK": 15,
        "BRATSK": 16,
        "BRYANSK": 17,
        "VELIKY_NOVGOROD": 18,
        "VLADIVOSTOK": 19,
        "VLADIKAVKAZ": 20,
        "VLADIMIR": 21,
        "VOLGOGRAD": 22,
        "VOLZHSKY": 24,
        "VOLOGDA": 26,
        "VORKUTA": 27,
        "VORONEZH": 28,
        "GELENDZHIK": 31,
        "EVPATORIA": 167,
        "YEKATERINBURG": 37,
        "ZAPOROZHYE": 156,
        "IVANOVO": 42,
        "IZHEVSK": 43,
        "IRKUTSK": 44,
        "YOSHKAR_OLA": 45,
        "KAZAN": 46,
        "KALININGRAD": 47,
        "KALUGA": 48,
        "KEMEROVO": 50,
        "KERCH": 166,
        "KIROV": 51,
        "KOLOMNA": 53,
        "KOMSOMOLSK_ON_AMUR": 54,
        "KOSTROMA": 55,
        "KRASNODAR": 56,
        "KRASNOYARSK": 57,
        "KURGAN": 58,
        "KURSK": 59,
        "LIPETSK": 60,
        "MAGADAN": 61,
        "MAGNITOGORSK": 62,
        "MAYKOP": 63,
        "MAKHACHKALA": 64,
        "MURMANSK": 66,
        "MUROM": 67,
        "NABEREZHNYE_CHELNY": 68,
        "NALCHIK": 69,
        "NAKHODKA": 70,
        "NIZHNEVARTOVSK": 71,
        "NIZHNY_NOVGOROD": 72,
        "NIZHNY_TAGIL": 73,
        "NOVOKUZNETSK": 74,
        "NOVOROSSIYSK": 76,
        "NOVOSIBIRSK": 77,
        "NOVY_URENGOY": 80,
        "NORILSK": 81,
        "OMSK": 85,
        "OREL": 86,
        "ORENBURG": 87,
        "ORSK": 88,
        "PENZA": 89,
        "PERM": 90,
        "PETROZAVODSK": 91,
        "PETROPAVLOVSK_KAMCHATSKY": 92,
        "PSKOV": 94,
        "PYATIGORSK": 96,
        "ROSTOV_ON_DON": 98,
        "RYAZAN": 99,
        "SAMARA": 100,
        "SARANSK": 101,
        "SARATOV": 102,
        "SEVASTOPOL": 164,
        "SIMFEROPOL": 163,
        "SMOLENSK": 106,
        "SOCHI": 108,
        "STAVROPOL": 109,
        "STARY_OSKOL": 110,
        "SURGUT": 112,
        "SYKTYVKAR": 113,
        "TAGANROG": 114,
        "TAMBOV": 115,
        "TVER": 116,
        "TOLYATTI": 117,
        "TOMSK": 118,
        "TULA": 120,
        "TYUMEN": 121,
        "ULAN_UDE": 122,
        "ULYANOVSK": 123,
        "USSURIYSK": 124,
        "UFA": 126,
        "UKHTA": 127,
        "FEODOSIYA": 168,
        "KHABAROVSK": 128,
        "KHANTY_MANSIYSK": 129,
        "KHERSON": 160,
        "CHEBOKSARY": 130,
        "CHELYABINSK": 131,
        "CHEREPOVETS": 132,
        "CHITA": 134,
        "YUZHNO_SAKHALINSK": 136,
        "YAKUTSK": 137,
        "YALTA": 165,
        "YAROSLAVL": 138
    }

    GOAL_MAPPING = {
        "ищу спонсора": "спонсора",
        "постоянные отношения": "отношения",
        "провести вечер": "вечер",
        "совместное путешествие": "путешествия"
    }

    DATA_KEY_MAPPING = {
        "Рост": "height",
        "Вес": "weight"
    }

    def __init__(self):
        self.base_url = "https://atolin.ru/anketa/search"
        self.domain = "https://atolin.ru"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        self.profiles = {}
        self.new_profiles = {}
        
        # Create data directory if it doesn't exist
        os.makedirs('data', exist_ok=True)
        self.load_existing_profiles()

    def clean_name_location(self, text):
        text = text.replace("Девушка", "").replace("Москва,", "").strip()
        text = re.sub(r'\s+', ' ', text)
        return text

    def load_existing_profiles(self):
        try:
            if os.path.exists('data/profiles.json'):
                with open('data/profiles.json', 'r', encoding='utf-8') as f:
                    self.profiles = json.load(f)
                logger.info(f"Loaded {len(self.profiles)} existing profiles")
        except Exception as e:
            logger.error(f"Failed to load existing profiles: {str(e)}")
            self.profiles = {}

    def get_search_page(self, age_from, age_to, location_id, page, gender=0):
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

    def get_profile_details(self, profile_url: str) -> Optional[dict]:
        try:
            delay = random.uniform(1.0, 2.0)
            logger.info(f"Waiting {delay:.2f} seconds before requesting profile details")
            time.sleep(delay)
            
            response = requests.get(profile_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            details = {}
            
            # Find details section
            details_div = soup.find('div', class_='details')
            if details_div:
                # Parse data sections
                for section in details_div.find_all('div'):
                    h3 = section.find('h3')
                    if not h3:
                        continue
                        
                    title = h3.text.strip()
                    
                    if title == "Данные":
                        params = {}
                        for param_div in section.find_all('div', class_='param'):
                            key_span = param_div.find('span')
                            value_span = param_div.find('span', class_='param_blue')
                            if key_span and value_span:
                                key = key_span.text.strip()
                                value = value_span.text.strip()
                                # Map key to English if exists
                                key = self.DATA_KEY_MAPPING.get(key, key)
                                params[key] = value
                        details['data'] = params
                        
                    elif title == "Цели знакомства":
                        goals = []
                        ul = section.find('ul')
                        if ul:
                            for li in ul.find_all('li'):
                                goal = li.text.strip()
                                # Map goal to short version if exists
                                goals.append(self.GOAL_MAPPING.get(goal, goal))
                        details['goals'] = goals
                        
                    elif title == "О себе":
                        about = section.text.replace("О себе", "").strip()
                        if about != "Информация отсутствует":
                            if "Показ контактной информации из женских анкет для «гостей» недоступен" in about:
                                details['about'] = "Необходима премиум-подписка для просмотра анкеты"
                            else:
                                details['about'] = about
            
            return details if details else None
            
        except Exception as e:
            logger.error(f"Failed to get profile details from {profile_url}: {str(e)}")
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
                        
                        # Skip if profile already exists
                        if profile_id in self.profiles:
                            continue
                            
                        link = item.find("a", class_="viewed")
                        if link:
                            img = link.find("img")
                            # Skip profiles without photos
                            if not img or "no-photo" in img.get("class", []):
                                continue
                                
                            profile_url = urljoin(self.domain, link['href'])
                            profile_data = {
                                "id": profile_id,
                                "photo_url": urljoin(self.domain, img['src']),
                                "additional_photos": None,
                                "name_location": None,
                                "status": None,
                                "profile_url": profile_url
                            }
                            
                            name_elem = link.find("span", class_="user-name")
                            if name_elem:
                                profile_data["name_location"] = self.clean_name_location(name_elem.text.strip())
                            
                            was_elem = link.find("span", class_="user-was")
                            if was_elem:
                                status = was_elem.find("span", class_=["online", "offline", "oldline"])
                                if status:
                                    profile_data["status"] = status.text.strip()
                            
                            photo_count = link.find("span", class_="viewed-count")
                            if photo_count:
                                profile_data["additional_photos"] = photo_count.text.strip()
                            
                            # Get profile details only for new profiles
                            if details := self.get_profile_details(profile_url):
                                profile_data.update(details)
                            
                            # Add to new profiles and all profiles
                            self.new_profiles[profile_id] = profile_data
                            self.profiles[profile_id] = profile_data
                            logger.info(f"Found new profile: {profile_id}")
            else:
                logger.error("Results container not found")
                return None
        except Exception as e:
            logger.error(f"Failed to parse HTML: {str(e)}")
            return None

    def collect_profiles(self, end_page, gender=0, age_from=None, age_to=None, location_id=None):
        logger.info(f"Starting collection from page 1 to {end_page}")
        
        for page in range(1, end_page + 1):
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
                
        # Save all profiles to profiles.json
        if self.profiles:
            with open('data/profiles.json', 'w', encoding='utf-8') as f:
                json.dump(self.profiles, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved {len(self.profiles)} total profiles to profiles.json")
        else:
            logger.warning("No profiles collected")

if __name__ == "__main__":
    parser = AtolinParser()
    parser.collect_profiles(
        end_page=20,
        age_from=18,
        age_to=35,
        location_id=AtolinParser.LOCATIONS["MOSCOW"]
    )
