import auto_reacts
import emote_speller
import memes
import pugs
import twitch_checker
import ow_tracker

import discord
from discord import app_commands
import logging

DEFAULT_GUILDS = [
    discord.Object(id=599237897580970005),
    discord.Object(id=525174584526241803),
    discord.Object(id=400805068934348800)
]

TESTING_GUILDS = [discord.Object(id=599237897580970005)]


class CustomDiscordClient(discord.Client):

    def __init__(self, command_guilds=[], *args, **kwargs):
        super(CustomDiscordClient, self).__init__(command_prefix='/',
                                                  *args,
                                                  **kwargs)

        self.command_guilds = command_guilds
        self.command_tree = app_commands.CommandTree(self)

        # Add copy pasta / meme commands
        self.command_tree.add_command(memes.MemesCommands(),
                                      guilds=self.command_guilds)

        # Add OWL calendar.
        # self.owl_calendar_manager = owl_calendar.OwlCalendarManager()
        # for command_group in self.owl_calendar_manager.getDiscordCommands():
        #     self.command_tree.add_command(command_group,
        #                                   guilds=self.command_guilds)

        # Add PUGs commands
        self.pugs_manager = pugs.PugsManager()
        for command_group in self.pugs_manager.getDiscordCommands():
            self.command_tree.add_command(command_group,
                                          guilds=self.command_guilds)

        # Creates the class to add auto reacts
        self.auto_react_manager = auto_reacts.AutoReactManager()

        # Creates the class for the twitch checker
        self.twitch_manager = twitch_checker.TwitchManager()
        for command_group in self.twitch_manager.getDiscordCommands():
            self.command_tree.add_command(command_group,
                                          guilds=self.command_guilds)

        # Add commands for Overwatch Tracker
        self.ow_tracker_manager = ow_tracker.OverwatchTrackerManager()
        for command_group in self.ow_tracker_manager.getDiscordCommands():
            self.command_tree.add_command(command_group,
                                          guilds=self.command_guilds)

    async def on_ready(self):
        logging.info(
            'Logged in as (name: {0.user.name}, id: {0.user.id})'.format(self))

        print('-' * 50)
        print('Logged in as')
        print(self.user.name)
        print(self.user.id)
        print('-' * 50)

        for guild in self.command_guilds:
            await self.command_tree.sync(guild=guild)

        # Setup twitch task to incremently check streams
        self.twitch_cog = twitch_checker.TwitchCog(self, self.twitch_manager)

    async def on_message(self, message):
        if message.author == self.user:
            return

        if message.content.startswith('||') and message.content.endswith('||'):
            logging.info(
                'Ignoring message, because it is surronded by spoiler tags')
            return

        emotes = self.auto_react_manager.getEmotes(message.content)
        for emote in emotes:
            logging.info(
                'Adding automatic reaction to message: message = "{}" reaction = {}'
                .format(message.content, emote))
            await message.add_reaction(emote)

    async def on_reaction_add(self, reaction, user):
        if user == self.user:
            logging.info('Ignoring reaction, because it is from the bot')
            return

        if reaction.emoji in emote_speller.TRIGGER_EMOJIS:
            logging.info('Trying to spell words on message: "{}"'.format(
                reaction.message.content))
            spelling = emote_speller.onReactionAdd(reaction)
            if spelling is not None:
                logging.info('Found a valid spelling: {}'.format(
                    ', '.join(spelling)))
                for emote in spelling:
                    await reaction.message.add_reaction(emote)
            else:
                logging.info('No valid spelling')
