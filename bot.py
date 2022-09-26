import auto_reacts
import emote_speller
import memes
import pugs

import discord
from discord import app_commands
import logging

DEFAULT_GUILDS = [
    discord.Object(id=599237897580970005),
    discord.Object(id=525174584526241803),
    discord.Object(id=400805068934348800)
]


class CustomDiscordClient(discord.Client):

    def __init__(self, *args, **kwargs):
        super(CustomDiscordClient, self).__init__(command_prefix='/',
                                                  *args,
                                                  **kwargs)

        self.command_tree = app_commands.CommandTree(self)

        # Add copy pasta / meme commands
        self.command_tree.add_command(memes.MemesCommands(),
                                      guilds=DEFAULT_GUILDS)

        # Add PUGs commands
        self.pugs_manager = pugs.PugsManager()
        for command_group in self.pugs_manager.getDiscordCommands():
            self.command_tree.add_command(command_group, guilds=DEFAULT_GUILDS)

        self.auto_react_manager = auto_reacts.AutoReactManager()

    async def on_ready(self):
        logging.info(
            'Logged in as (name: {0.user.name}, id: {0.user.id})'.format(self))

        print('-' * 50)
        print('Logged in as')
        print(self.user.name)
        print(self.user.id)
        print('-' * 50)

        for guild in DEFAULT_GUILDS:
            await self.command_tree.sync(guild=guild)

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
