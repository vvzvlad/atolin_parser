import os
import logging
from telegram import Bot
from telegram.error import TelegramError
import asyncio
from parser import AtolinParser
import json
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ProfileBot:
    def __init__(self, token, channel_id):
        self.bot = Bot(token=token)
        self.channel_id = channel_id
        self.parser = AtolinParser()

    async def send_profile(self, profile_data):
        try:
            message = [f"👤 {profile_data['name_location']} (🕒 {profile_data['status']})"]
            
            if 'data' in profile_data and profile_data['data']:
                params = []
                if 'height' in profile_data['data']:
                    params.append(profile_data['data']['height'])
                if 'weight' in profile_data['data']:
                    params.append(profile_data['data']['weight'])
                if params:
                    message.append(f"\n📋 {', '.join(params)}")
                    
            if 'goals' in profile_data and profile_data['goals']:
                message.append(f"\n🎯 {', '.join(profile_data['goals'])}")
                    
            if 'about' in profile_data:
                message.append(f"\n💬 {profile_data['about']}")
                
            message.append(f"\n🔗 <a href='{profile_data['profile_url']}'>Анкета</a>")

            if profile_data['additional_photos']:
                message.append(f"(📸 {profile_data['additional_photos']})")
            
            # Send photo with caption
            await self.bot.send_photo(
                chat_id=self.channel_id,
                photo=profile_data['photo_url'],
                caption="\n".join(message),
                parse_mode='HTML'
            )
            logger.info(f"Sent profile {profile_data['id']} to channel")
            
        except TelegramError as e:
            logger.error(f"Failed to send profile {profile_data['id']}: {str(e)}")

    async def process_new_profiles(self):
        logger.info("Starting profile collection")
        
        # Check if this is first run (no profiles.json exists)
        is_first_run = not os.path.exists('profiles.json')
        
        self.parser.collect_profiles(
            start_page=1,
            end_page=1,
            age_from=18,
            age_to=35,
            location_id=self.parser.LOCATIONS["MOSCOW"]
        )
        
        if is_first_run:
            logger.info("First run detected - initializing profiles database without sending messages")
            return
        
        if not self.parser.new_profiles:
            logger.info("No new profiles found")
            return
            
        logger.info(f"Found {len(self.parser.new_profiles)} new profiles")
        
        for _profile_id, profile_data in self.parser.new_profiles.items():
            await self.send_profile(profile_data)
            # Add delay between messages to avoid flood limits
            await asyncio.sleep(2)

async def run_periodic_check():
    # Load config from environment variables
    token = os.getenv('TG_BOT_TOKEN')
    channel_id = os.getenv('TG_CHANNEL_ID')
    
    if not token or not channel_id:
        logger.error("Please set TG_BOT_TOKEN and TG_CHANNEL_ID environment variables")
        return
        
    bot = ProfileBot(token, channel_id)
    
    while True:
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"Starting periodic check at {current_time}")
            
            await bot.process_new_profiles()
            
            logger.info("Waiting for 1 hour before next check")
            await asyncio.sleep(3600)  # 1 hour in seconds
            
        except Exception as e:
            logger.error(f"Error during periodic check: {str(e)}")
            logger.info("Retrying in 5 minutes")
            await asyncio.sleep(300)  # 5 minutes in seconds

if __name__ == "__main__":
    asyncio.run(run_periodic_check()) 