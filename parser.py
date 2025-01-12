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
from datetime import datetime
import urllib3
from fake_headers import Headers

# Disable SSL warning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AtolinParser:
    # Score settings
    SCORE_PER_50_CHARS = 1.1
    SCORE_PER_PHOTO = 0.8
    SCORE_PER_GOAL = 0.5
    SCORE_PER_DAY = 0.8

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
        self.profiles = {}
        self.new_profiles = {}
        
        # Load min score threshold from env
        self.min_score_threshold = float(os.getenv('MIN_SCORE_THRESHOLD', '2.0'))
        logger.info(f"Using minimum score threshold: {self.min_score_threshold}")
        
        # Setup proxy if configured
        self.proxies = None
        proxy = os.getenv('PROXY')
        if proxy:
            if proxy.startswith('socks5://'):
                # For SOCKS5 proxy we use the full URL
                self.proxies = {
                    'http': proxy,
                    'https': proxy
                }
            elif proxy.startswith('http://'):
                # For HTTP proxy we use the full URL
                self.proxies = {
                    'http': proxy,
                    'https': proxy
                }
            logger.info(f"Using proxy: {proxy}")
        
        # Create data directory if it doesn't exist
        os.makedirs('data', exist_ok=True)
        self.load_existing_profiles()

    def make_request(self, url: str, timeout: int = 10, max_retries: int = 3) -> Optional[requests.Response]:
        """Make HTTP request with proxy support and error handling"""
        for attempt in range(max_retries):
            try:
                headers = Headers(os="win", headers=True).generate()
                headers['Accept-Encoding'] = '' # Disable compression
                
                response = requests.get(
                    url, 
                    headers=headers, 
                    proxies=self.proxies,
                    timeout=timeout,
                    verify=False  
                )
                if response.status_code == 404:
                    # If this is a profile URL, remove it from profiles
                    profile_id = url.split('/')[-1]
                    if profile_id in self.profiles:
                        logger.info(f"Profile {profile_id} returned 404, removing from database")
                        del self.profiles[profile_id]
                        # Save profiles after deletion
                        with open('data/profiles.json', 'w', encoding='utf-8') as f:
                            json.dump(self.profiles, f, ensure_ascii=False, indent=2)
                    return None
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                if attempt < max_retries - 1:
                    retry_delay = random.uniform(10, 30)
                    logger.warning(f"Request failed for {url} (attempt {attempt + 1}/{max_retries}): {str(e)}. Retrying in {retry_delay:.1f} seconds...")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"Request failed for {url} after {max_retries} attempts: {str(e)}")
                    # If this was a 404 error on the last attempt, handle profile deletion
                    if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 404:
                        profile_id = url.split('/')[-1]
                        if profile_id in self.profiles:
                            logger.info(f"Profile {profile_id} returned 404, removing from database")
                            del self.profiles[profile_id]
                            # Save profiles after deletion
                            with open('data/profiles.json', 'w', encoding='utf-8') as f:
                                json.dump(self.profiles, f, ensure_ascii=False, indent=2)
        return None

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
        
        response = self.make_request(url)
        if response:
            logger.info(f"Successfully loaded page {page} with parameters: age {age_from}-{age_to}, gender {gender}, location {location_id}")
            return response.text
        return None

    def calculate_profile_score(self, profile_data: dict) -> float:
        score = 0
        
        # Score for description length
        if "about" in profile_data and isinstance(profile_data["about"], str):
            score += len(profile_data["about"]) // 50 * self.SCORE_PER_50_CHARS
            
        # Score for additional photos
        if "additional_photos" in profile_data and profile_data["additional_photos"]:
            try:
                additional_photos = int(profile_data["additional_photos"].split()[0])
                score += additional_photos * self.SCORE_PER_PHOTO
            except (ValueError, IndexError):
                pass
                
        # Score for goals
        if "goals" in profile_data and isinstance(profile_data["goals"], list):
            score += sum(self.SCORE_PER_GOAL for goal in profile_data["goals"] if goal != "спонсора")
            
        # Score for profile lifetime
        profile_id = profile_data.get("id")
        if profile_id and profile_id in self.profiles:
            stored_profile = self.profiles[profile_id]
            if "first_seen" in stored_profile:
                try:
                    first_seen = datetime.strptime(stored_profile["first_seen"], "%Y-%m-%d %H:%M:%S")
                    now = datetime.now()
                    days_alive = (now - first_seen).total_seconds() / (24 * 3600)  # Convert to days
                    score += days_alive * self.SCORE_PER_DAY
                except (ValueError, TypeError) as e:
                    logger.error(f"Failed to calculate lifetime score for profile {profile_id}: {str(e)}")
            
        return round(score, 2)  # Round to 2 decimal places for cleaner display

    def get_profile_details(self, profile_url: str) -> Optional[dict]:
        try:
            delay = random.uniform(1, 5)
            logger.info(f"Waiting {delay:.2f} seconds before requesting profile details")
            time.sleep(delay)
            
            response = self.make_request(profile_url)
            if not response:
                return None
            
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
                                "profile_url": profile_url,
                                "first_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
                                
                            # Calculate and add score
                            profile_data["score"] = self.calculate_profile_score(profile_data)
                            
                            # Add to new profiles and all profiles
                            self.new_profiles[profile_id] = profile_data
                            self.profiles[profile_id] = profile_data
                            logger.info(f"Found new profile: {profile_id} with score: {profile_data['score']}")
            else:
                logger.error("Results container not found")
                return None
        except Exception as e:
            logger.error(f"Failed to parse HTML: {str(e)}")
            return None

    def recheck_low_score_profiles(self):
        """Recheck all profiles with score < min_score_threshold"""
        low_score_profiles = [p for p in self.profiles.items() if p[1].get('score', 0) < self.min_score_threshold]
        if not low_score_profiles:
            logger.info("No low-score profiles to recheck")
            return
            
        logger.info(f"Found {len(low_score_profiles)} profiles with low score, starting recheck")
        
        for index, (profile_id, profile_data) in enumerate(low_score_profiles, 1):
            if profile_id not in self.new_profiles:
                logger.info(f"Rechecking low-score profile {profile_id} ({index}/{len(low_score_profiles)})")
                
                try:
                    # Get fresh profile page
                    response = self.make_request(profile_data['profile_url'])
                    if not response:
                        continue
                        
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Update basic profile data
                    link = soup.find("a", class_="viewed")
                    if link:
                        img = link.find("img")
                        if img and "no-photo" not in img.get("class", []):
                            profile_data["photo_url"] = urljoin(self.domain, img['src'])
                            
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
                    
                    # Get fresh profile details
                    if details := self.get_profile_details(profile_data['profile_url']):
                        profile_data.update(details)
                    
                    # Recalculate score
                    profile_data['score'] = self.calculate_profile_score(profile_data)
                    
                    if profile_data.get('score', 0) >= self.min_score_threshold:
                        logger.info(f"Profile {profile_id} score increased to {profile_data['score']}")
                        # Add to new profiles for notification
                        self.new_profiles[profile_id] = profile_data
                    else:
                        logger.info(f"Profile {profile_id} score still low ({profile_data.get('score', 0)})")
                    
                except Exception as e:
                    logger.error(f"Failed to recheck profile {profile_id}: {str(e)}")
                
                time.sleep(random.uniform(1, 5))

    def collect_profiles(self, end_page, age_from, age_to, location_id):
        logger.info(f"Starting collection from page 1 to {end_page}")
        
        # Clear new profiles at the start of collection
        self.new_profiles = {}
        
        # First recheck existing low-score profiles
        self.recheck_low_score_profiles()
        
        # Then collect new profiles
        for page in range(1, end_page + 1):
            logger.info(f"Processing page {page}")
            content = self.get_search_page(gender=0, age_from=age_from, age_to=age_to, location_id=location_id, page=page)
            
            if content:
                self.get_results_container(content)
                
                # Random delay between requests to avoid blocking
                delay = random.uniform(1, 5)
                logger.info(f"Waiting {delay:.2f} seconds before next request")
                time.sleep(delay)
            else:
                logger.error(f"Failed to get content for page {page}")
            
        # Save all profiles to profiles.json
        if self.profiles:
            with open('data/profiles.json', 'w', encoding='utf-8') as f:
                json.dump(self.profiles, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved {len(self.profiles)} total profiles to data/profiles.json")
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
