import os
import logging
from telegram import Bot
from telegram.error import TelegramError, RetryAfter
import asyncio
from parser import AtolinParser
import json
from datetime import datetime
import re

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ProfileBot:
    def __init__(self, token, channel_id):
        self.bot = Bot(token=token)
        self.channel_id = channel_id
        self.parser = AtolinParser()
        self.default_delay = 10  # Default delay between messages in seconds

    def escape_markdown(self, text: str) -> str:
        """Escape special characters for MarkdownV2"""
        need_escape = r'_*[]()~`>#+-=|{}.!'
        return ''.join(f'\\{c}' if c in need_escape else c for c in str(text))

    async def send_profile(self, profile_data):
        max_retries = 3
        current_retry = 0
        
        while current_retry < max_retries:
            try:
                message_parts = []
                
                # Combine all basic info into one line
                first_line = self.escape_markdown(profile_data['name_location'])
                if 'data' in profile_data and profile_data['data']:
                    params = []
                    if 'height' in profile_data['data']:
                        params.append(self.escape_markdown(profile_data['data']['height']))
                    if 'weight' in profile_data['data']:
                        params.append(self.escape_markdown(profile_data['data']['weight']))
                    if params:
                        first_line += f", {', '.join(params)}"
                
                # Make first line a link
                was_prefix = "была " if profile_data['status'].lower() != "на сайте" else ""
                status_text = f"{was_prefix}{self.escape_markdown(profile_data['status'])}"
                message_parts.append(f"Новая анкета: 👤 [{first_line}]({profile_data['profile_url']}) \\({status_text}\\)")
                
                # Goals
                if 'goals' in profile_data and profile_data['goals']:
                    goals = [self.escape_markdown(goal) for goal in profile_data['goals']]
                    message_parts.append(f"🎯 {', '.join(goals)}")
                
                # About
                if 'about' in profile_data:
                    message_parts.append(f"💬 {self.escape_markdown(profile_data['about'])}")
                
                # Additional photos info
                if profile_data['additional_photos']:
                    message_parts.append(f"📸 {self.escape_markdown(profile_data['additional_photos'])}")

                # Score info
                if 'score' in profile_data:
                    message_parts.append(f"⭐️ Antifroud score: {self.escape_markdown(str(profile_data['score']))}")

                message_parts.append(f"\n")
                
                # Join with single line breaks
                message = "\n".join(message_parts)
                
                # Send photo with caption
                await self.bot.send_photo(
                    chat_id=self.channel_id,
                    photo=profile_data['photo_url'],
                    caption=message,
                    parse_mode='MarkdownV2'
                )
                logger.info(f"Sent profile {profile_data['id']} to channel")
                await asyncio.sleep(self.default_delay)  
                return
                
            except RetryAfter as e:
                retry_after = int(e.retry_after)
                logger.warning(f"Flood control exceeded. Waiting {retry_after} seconds")
                await asyncio.sleep(retry_after)
                current_retry += 1
                
            except TelegramError as e:
                error_msg = str(e)
                if "Flood control exceeded" in error_msg:
                    # Extract retry time from error message
                    retry_match = re.search(r'Retry in (\d+) seconds', error_msg)
                    retry_after = int(retry_match.group(1)) if retry_match else self.default_delay
                    logger.warning(f"Flood control exceeded. Waiting {retry_after} seconds")
                    await asyncio.sleep(retry_after)
                    current_retry += 1
                else:
                    logger.error(f"Failed to send profile {profile_data['id']}: {str(e)}")
                    if "Timed out" in error_msg:
                        await asyncio.sleep(self.default_delay)  # Wait default delay on timeout
                        current_retry += 1
                    else:
                        break  # Break on other errors

        if current_retry >= max_retries:
            logger.error(f"Failed to send profile {profile_data['id']} after {max_retries} retries")

    async def process_new_profiles(self, end_page, age_from, age_to, location):
        logger.info("Starting profile collection")
        
        # Check if this is first run (no profiles.json exists)
        is_first_run = not os.path.exists('data/profiles.json')
        
        if is_first_run:
            logger.info("First run detected (no profiles.json) - initializing profiles database without sending messages")
        
        # Validate location
        if location not in self.parser.LOCATIONS:
            logger.error(f"Invalid location: {location}")
            return
            
        self.parser.collect_profiles(
            end_page=end_page,
            age_from=age_from,
            age_to=age_to,
            location_id=self.parser.LOCATIONS[location]
        )
        
        if not self.parser.new_profiles:
            logger.info("No new profiles to send")
            return
            
        logger.info(f"Found {len(self.parser.new_profiles)} new profiles")
        
        if not is_first_run:
            # Send only profiles with score >= min_score_threshold
            for profile_id, profile_data in self.parser.new_profiles.items():
                if profile_data.get('score', 0) >= self.parser.min_score_threshold:
                    await self.send_profile(profile_data)
                    logger.info(f"Sent profile {profile_id} with score {profile_data.get('score', 0)}")
                else:
                    logger.info(f"Profile {profile_id} has low score ({profile_data.get('score', 0)}), skipping")
            
            # Clear new_profiles after processing
            self.parser.new_profiles = {}

async def run_periodic_check():
    # Load config from environment variables
    token = os.getenv('TG_BOT_TOKEN')
    channel_id = os.getenv('TG_CHANNEL_ID')
    
    if not token or not channel_id:
        logger.error("Please set TG_BOT_TOKEN and TG_CHANNEL_ID environment variables")
        return
    
    # Load search parameters from environment variables
    try:
        end_page = int(os.getenv('SEARCH_END_PAGE'))
        age_from = int(os.getenv('SEARCH_AGE_FROM'))
        age_to = int(os.getenv('SEARCH_AGE_TO'))
        location = os.getenv('SEARCH_LOCATION')
        check_interval = int(os.getenv('CHECK_INTERVAL', '3600'))  # Default 1 hour
        retry_interval = int(os.getenv('RETRY_INTERVAL', '300'))   # Default 5 minutes
        
        logger.info(f"Search parameters: pages 1-{end_page}, age {age_from}-{age_to}, location {location}")
        logger.info(f"Intervals: check {check_interval}s, retry {retry_interval}s")
        
        if not all([end_page, age_from, age_to, location]):
            logger.error("Please set all required environment variables: SEARCH_END_PAGE, SEARCH_AGE_FROM, SEARCH_AGE_TO, SEARCH_LOCATION")
            return
            
    except (TypeError, ValueError) as e:
        logger.error(f"Invalid environment variables: {str(e)}")
        return
        
    bot = ProfileBot(token, channel_id)
    
    while True:
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"Starting periodic check at {current_time}")
            
            await bot.process_new_profiles(
                end_page=end_page,
                age_from=age_from,
                age_to=age_to,
                location=location
            )
            
            logger.info(f"Waiting for {check_interval} seconds before next check")
            await asyncio.sleep(check_interval)
            
        except Exception as e:
            logger.error(f"Error during periodic check: {str(e)}")
            logger.info(f"Retrying in {retry_interval} seconds")
            await asyncio.sleep(retry_interval)

if __name__ == "__main__":
    asyncio.run(run_periodic_check()) 