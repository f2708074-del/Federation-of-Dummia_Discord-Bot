import discord
from discord.ext import commands
import random
import logging
from typing import Dict, List

# Configure logging
logger = logging.getLogger('ping_response')

class PingResponse(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger('ping_response')
        
        # List of random responses
        self.responses = [
            "bro I got this",
            "Shut the fuck up bro",
            "Hi, I'm mcloving",
            "I guess you can call me a lumberjack because I cut LOGS",
            "no"
        ]

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore messages from bots
        if message.author.bot:
            return
            
        # Check if the bot is mentioned in the message
        if self.bot.user in message.mentions:
            # Choose a random response
            response = random.choice(self.responses)
            
            # Send the response as an ephemeral message (only visible to the user who pinged)
            try:
                await message.reply(response, mention_author=False, delete_after=10)
                self.logger.info(f"Responded to ping from {message.author} with: {response}")
            except discord.Forbidden:
                self.logger.warning(f"Could not send message to {message.author} - missing permissions")
            except Exception as e:
                self.logger.error(f"Error responding to ping: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(PingResponse(bot))
    logger.info("PingResponse cog loaded successfully")
