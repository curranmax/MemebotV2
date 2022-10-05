import bot

from datetime import datetime
import discord
import logging
import os

TESTING_MODE = False
token = os.getenv('DISCORD_TOKEN')
command_guilds = bot.DEFAULT_GUILDS
if TESTING_MODE:
    print('RUNNING IN TESTING MODE')
    token = os.getenv('DISCORD_TESTING_TOKEN')
    command_guilds = bot.TESTING_GUILDS

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
client = bot.CustomDiscordClient(command_guilds=command_guilds,intents=intents)
client.run(token)