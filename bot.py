import auto_reacts
import emote_speller
import memes
import pugs
import twitch_checker
import ow_tracker
import event_calendar
import chore_calendar
import custom_commands
import food_chooser

import discord
from discord import app_commands
import logging

DEFAULT_GUILDS = [
    discord.Object(id=599237897580970005),
    discord.Object(id=525174584526241803),
    discord.Object(id=400805068934348800)
]

CHOREBOT_GUILDS = [discord.Object(id=400805068934348800)]
FOODBOT_GUILDS = [discord.Object(id=400805068934348800)]

TESTING_GUILDS = [discord.Object(id=599237897580970005)]


class CustomDiscordClient(discord.Client):

    def __init__(self,
                 feature_tracker=None,
                 command_guilds=[],
                 command_prefix='/',
                 *args,
                 **kwargs):
        super(CustomDiscordClient,
              self).__init__(command_prefix=command_prefix, *args, **kwargs)

        self.feature_tracker = feature_tracker

        self.command_guilds = command_guilds
        self.command_tree = app_commands.CommandTree(self)

        # TODO only create this if its needed.
        if self.feature_tracker is not None and self.feature_tracker.isEnabled(
                'chore_calendar'):
            self.event_calendar = event_calendar.EventCalendar(self)
        else:
            self.event_calendar = None

        # Add copy pasta / meme commands
        if self.feature_tracker is not None and self.feature_tracker.isEnabled(
                'memes'):
            self.command_tree.add_command(memes.MemesCommands(),
                                          guilds=self.command_guilds)

        # Add OWL calendar.
        # if self.feature_tracker is not None and self.feature_tracker.isEnabled('owl_calendar'):
        #     self.owl_calendar_manager = owl_calendar.OwlCalendarManager()
        #     for command_group in self.owl_calendar_manager.getDiscordCommands():
        #         self.command_tree.add_command(command_group,
        #                                       guilds=self.command_guilds)

        # Add PUGs commands
        if self.feature_tracker is not None and self.feature_tracker.isEnabled(
                'pugs'):
            self.pugs_manager = pugs.PugsManager()
            for command_group in self.pugs_manager.getDiscordCommands():
                self.command_tree.add_command(command_group,
                                              guilds=self.command_guilds)

        # Creates the class to add auto reacts
        if self.feature_tracker is not None and self.feature_tracker.isEnabled(
                'auto_reacts'):
            self.auto_react_manager = auto_reacts.AutoReactManager()
        else:
            self.auto_react_manager = None

        # Creates the class for the twitch checker
        if self.feature_tracker is not None and self.feature_tracker.isEnabled(
                'twitch_checker'):
            self.twitch_manager = twitch_checker.TwitchManager()
            for command_group in self.twitch_manager.getDiscordCommands():
                self.command_tree.add_command(command_group,
                                              guilds=self.command_guilds)
        else:
            self.twitch_manager = None

        # Add commands for Overwatch Tracker
        if self.feature_tracker is not None and self.feature_tracker.isEnabled(
                'ow_tracker'):
            self.ow_tracker_manager = ow_tracker.OverwatchTrackerManager()
            for command_group in self.ow_tracker_manager.getDiscordCommands():
                self.command_tree.add_command(command_group,
                                              guilds=self.command_guilds)

        # Add commands for the Chore Calendar
        if self.feature_tracker is not None and self.feature_tracker.isEnabled(
                'chore_calendar'):
            self.chore_calendar = chore_calendar.ChoreCalendar(
                self, self.event_calendar)
            for command_group in self.chore_calendar.getDiscordCommands():
                self.command_tree.add_command(command_group,
                                              guilds=self.command_guilds)

        # Add commands for custom commands
        if self.feature_tracker is not None and self.feature_tracker.isEnabled(
                'custom_commands'):
            self.custom_command_manager = custom_commands.CustomCommandManager(
            )
            for command_group in self.custom_command_manager.getDiscordCommands(
            ):
                self.command_tree.add_command(command_group,
                                              guilds=self.command_guilds)

        # Add commands for the Food Chooser
        if self.feature_tracker is not None and self.feature_tracker.isEnabled(
                'food_chooser'):
            self.food_chooser = food_chooser.FoodManager(firebase_key='/home/curranmax/keys/firebase.json')
            for command_group in self.food_chooser.getDiscordCommands():
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

        self.feature_tracker.printEnabledFeature()

        for guild in self.command_guilds:
            await self.command_tree.sync(guild=guild)

        # Setup twitch task to incremently check streams
        if self.twitch_manager is not None:
            self.twitch_cog = twitch_checker.TwitchCog(self,
                                                       self.twitch_manager)
        if self.event_calendar is not None:
            self.event_calendar.start()

    async def on_message(self, message):
        if message.author == self.user:
            return

        if message.content.startswith('||') and message.content.endswith('||'):
            logging.info(
                'Ignoring message, because it is surronded by spoiler tags')
            return

        if self.auto_react_manager is not None:
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

        if self.feature_tracker is not None and self.feature_tracker.isEnabled(
                'emote_speller'
        ) and reaction.emoji in emote_speller.TRIGGER_EMOJIS:
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

        if self.feature_tracker is not None and self.feature_tracker.isEnabled(
                'chore_calendar'):
            await self.chore_calendar.onReactionAdd(reaction, user)
