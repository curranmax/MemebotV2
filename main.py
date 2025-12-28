import bot
import feature_tracker as FT

from datetime import datetime
import discord
import logging
import os

feature_tracker = FT.FeatureTracker()

# Get discord tokens and guilds.

if feature_tracker.isTestingMode():
    print('RUNNING IN TESTING MODE')
    token = os.getenv('DISCORD_TESTING_TOKEN')
    command_guilds = bot.TESTING_GUILDS
elif feature_tracker.isChorebot():
    token = os.getenv('CHOREBOT_TOKEN')
    command_guilds = bot.CHOREBOT_GUILDS
elif feature_tracker.isHoKbot():
    token = os.getenv('DATABASEBOT_TOKEN')
    command_guilds = bot.HOKBOT_GUILDS
else:
    token = os.getenv('DISCORD_TOKEN')
    command_guilds = bot.DEFAULT_GUILDS

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
client = bot.CustomDiscordClient(feature_tracker=feature_tracker,
                                 command_guilds=command_guilds,
                                 intents=intents)
client.run(token)
