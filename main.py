from bot import CustomDiscordClient

from datetime import datetime
import discord
import logging
import os

# Configure logging
logging_fname = datetime.now().strftime('logs/log_%b-%d-%Y_%I:%M:%S_%p.txt')
logging_format = '[%(asctime)s] %(filename)s:%(lineno)d %(name)s:%(levelname)s --> %(message)s'
logging_level = logging.INFO  # logging.WARNING
logging.basicConfig(filename=logging_fname,
                    format=logging_format,
                    level=logging_level)

# Set discord intents
intents = discord.Intents.default()
intents.message_content = True

# Start discord bot
client = CustomDiscordClient(intents=intents)
client.run(os.getenv('DISCORD_TOKEN'))