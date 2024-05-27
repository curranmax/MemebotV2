import asyncio
import datetime
import discord
from discord import app_commands
from discord.ext import commands, tasks
import os
import os.path
import pickle
import random
import requests

# Twitch API Client values
TWITCH_CLIENT_ID = 'vu554mt1v5ou3h34szcyk3mlx7ykig'
TWITCH_CLIENT_SECRET = os.getenv('TWITCH_CLIENT_SECRET')

# Twitch API URLs
TWITCH_ACCESS_TOKEN_URL = 'https://id.twitch.tv/oauth2/token'
TWITCh_STREAMS_URL = 'https://api.twitch.tv/helix/streams'

# File where streams are saved
TWITCH_STREAM_FILENAME = 'data/twitch_streams.pickle'


class TwitchManager:

    def __init__(self, twitch_stream_filename=TWITCH_STREAM_FILENAME):
        self.access_token = self.getTwitchAccessToken()

        self.twitch_stream_filename = twitch_stream_filename
        self.loadTwitchStreamsFromFile()

    def getDiscordCommands(self):
        return [TwitchDiscordCommands(self), TwitchAdminDiscordCommands(self)]

    def getTwitchAccessToken(self):
        params = {
            'client_id': TWITCH_CLIENT_ID,
            'client_secret': TWITCH_CLIENT_SECRET,
            'grant_type': 'client_credentials'
        }
        response = requests.post(url=TWITCH_ACCESS_TOKEN_URL, params=params)
        return response.json()['access_token']

    def loadTwitchStreamsFromFile(self):
        # If file does not exist, then init self.twitch_streams to empty dict
        if not os.path.exists(self.twitch_stream_filename):
            self.twitch_streams = {}
            self.saveTwitchStreamsToFile()
            return

        f = open(self.twitch_stream_filename, 'rb')
        self.twitch_streams = pickle.load(f)

        for _, twitch_stream in self.twitch_streams.items():
            twitch_stream.prev_state = TwitchState()
            twitch_stream.state = TwitchState()

    def saveTwitchStreamsToFile(self):
        f = open(self.twitch_stream_filename, 'wb')
        pickle.dump(self.twitch_streams, f)

    def addTwitchStream(self, twitch_stream):
        if twitch_stream.user_name in self.twitch_streams:
            return False

        self.twitch_streams[twitch_stream.user_name] = twitch_stream
        self.saveTwitchStreamsToFile()
        return True

    def getTwitchStreamByUserName(self, user_name):
        if user_name not in self.twitch_streams:
            return None
        return self.twitch_streams[user_name]

    def getTwitchStreamsByDiscordUser(self, discord_user_id):
        streams = []
        for _, twitch_stream in self.twitch_streams.items():
            if twitch_stream.discord_user_id == discord_user_id:
                streams.append(twitch_stream)
        return streams

    def getTwitchStreamByUserNameAndId(self, user_name, discord_user_id):
        if user_name not in self.twitch_streams:
            return None
        twitch_stream = self.twitch_streams[user_name]
        return twitch_stream if twitch_stream.discord_user_id == discord_user_id else None

    def removeTwitchStream(self, user_name, discord_user_id):
        if user_name not in self.twitch_streams or self.twitch_streams[
                user_name].discord_user_id != discord_user_id:
            return False

        del self.twitch_streams[user_name]
        self.saveTwitchStreamsToFile()
        return True

    def checkStateOfAllStreams(self, retry=False):
        if len(self.twitch_streams) <= 0:
            return []

        url = TWITCh_STREAMS_URL + '?first={}&{}'.format(
            len(self.twitch_streams), '&'.join(
                map(lambda ts: 'user_login={}'.format(ts.user_name),
                    (ts for _, ts in self.twitch_streams.items()))))
        headers = {
            'Authorization': 'Bearer {}'.format(self.access_token),
            'Client-Id': TWITCH_CLIENT_ID
        }
        response = requests.get(url=url, headers=headers)

        if response.status_code == 401:
            if not retry:
                self.access_token = self.getTwitchAccessToken()
                return self.checkStateOfAllStreams(retry=True)
            return []

        if response.status_code != 200:
            print("Got a non-200 response code: ", response.status_code)
            return []

        new_states = {
            user_name: TwitchState(status=TwitchState.OFFLINE)
            for user_name in self.twitch_streams
        }

        # response.json()['data'] is a list that contains an entry for each live stream in the set of streams included in the 'user_login' params on the URL. Offline streams won't have any entry in the list.
        try:
            data = response.json()['data']
        except requests.exceptions.JSONDecodeError as e:
            print("Failed to parse JSON; error = ", e)
            return []

        for live_stream in data:
            user_name = live_stream['user_name']
            game = live_stream['game_name']
            title = live_stream['title']

            new_states[user_name] = TwitchState(status=TwitchState.ONLINE,
                                                game=game,
                                                title=title)

        return [
            twitch_stream.updateState(new_states[user_name])
            for user_name, twitch_stream in self.twitch_streams.items()
        ]


class TwitchStream:
    DEFAULT_LIVE_MESSAGE_FORMATS = [
        '{user_name} has gone live, and is playing {game_name}!\n{twitch_link}',
        '{user_name} is now live playing {game_name}!\n{twitch_link}',
        'CRISIS ALERT! {user_name} is now live playing {game_name}!\n{twitch_link}',
        'CRISIS ALERT! {user_name} has gone live, and is playing {game_name}!\n{twitch_link}'
    ]

    JUST_CHATTING_MESSAGE_FORMATS = [
        '{user_name} is live now and is Just Chatting™!\n{twitch_link}',
        '{user_name} is Just Chatting™!\n{twitch_link}'
    ]

    def __init__(self,
                 user_name,
                 discord_user_id,
                 discord_channel_id,
                 game_allow_list=None,
                 post_cooldown=datetime.timedelta(hours=1),
                 super_mode=False):
        self.user_name = user_name
        self.discord_user_id = discord_user_id
        self.discord_channel_id = discord_channel_id

        self.game_allowlist = game_allow_list if game_allow_list is not None else []

        self.last_post = None
        self.post_cooldown = post_cooldown

        # If enabled, then a separate post is made when this stream changes games
        self.super_mode = super_mode

        # Add in custom message formats,
        # Add new fields to pickled objects

        self.prev_state = TwitchState()
        self.state = TwitchState()

    def getPostCooldownStr(self):
        # Posts the timedelta in HH:MM format
        return ':'.join(str(self.post_cooldown).split(':')[:2])

    # Returns None if a message should not be sent, otherwise returns the message to post.
    def updateState(self, new_state):
        rv = None
        # In order to post:
        # 1. Valid transition:
        #   a. Stream starting: self.state.status == OFFLINE and new_state.status == ONLINE.
        #   b. Stream starting in Just Chatting: self.state.status == OFFLINE and new_state.status == JUST_CHATTING.
        #   c. Stream that started in Just Chatting, starting a game: self.previous_state.status == OFFLINE and self.state.status == JUST_CHATTING and new_state.status == ONLINE.  Note that this case ignores the post cooldown requirement!!!!!!!!!!!
        #   d. Stream in super mode changing games: self.super_mode == TRUE and self.state.status == new_state.status == ONLINE and self.state.game != new_state.game.
        # 2. Allowlist:
        #   a. Stream doesn't have an allowlist: len(self.game_allowlist) == 0.
        #   b. Game is in stream's allowlist: new_state.game is in self.game_allowlist.
        # 3. Post cooldown:
        #   a. Bot never posted for stream: self.last_post is None.
        #   b. Post cooldown is disabled for stream: self.post_cooldown <= datetime.timedelta()
        #   c. It has been at least the post cooldown since the last post: self.last_post + self.post_cooldown <= datetime.datetime.now()
        #   d. Case 1c ignores the cooldown.

        # 1a
        stream_starting = (self.state.status == TwitchState.OFFLINE
                           and new_state.status == TwitchState.ONLINE)

        # 1b
        stream_starting_in_just_chatting = (
            self.state.status == TwitchState.OFFLINE
            and new_state.status == TwitchState.JUST_CHATTING)

        # 1c
        stream_starting_in_just_chatting_and_starting_a_game = (
            self.prev_state.status == TwitchState.OFFLINE
            and self.state.status == TwitchState.JUST_CHATTING
            and new_state.status == TwitchState.ONLINE)

        # 1d
        stream_in_super_mode_changing_games = (
            self.state.status == TwitchState.ONLINE
            and new_state.status == TwitchState.ONLINE and self.super_mode
            and self.state.game != new_state.game)

        # 2a
        empty_allowlist = (len(self.game_allowlist) <= 0)

        # 2b
        game_in_allowlist = (new_state.game in self.game_allowlist)

        # 3a
        never_posted = (self.last_post is None)

        # 3b
        post_cooldown_disabled = (self.post_cooldown <= datetime.timedelta())

        # 3c
        post_cooldown_check = (
            self.last_post is not None
            and self.last_post + self.post_cooldown <= datetime.datetime.now())

        post_on_transition = (
            stream_starting or stream_starting_in_just_chatting
            or stream_starting_in_just_chatting_and_starting_a_game
            or stream_in_super_mode_changing_games
        ) and (empty_allowlist or game_in_allowlist) and (
            never_posted or post_cooldown_disabled or post_cooldown_check
            or stream_starting_in_just_chatting_and_starting_a_game)

        if post_on_transition:
            self.last_post = datetime.datetime.now()

            mfs = []
            if new_state.status == TwitchState.JUST_CHATTING:
                mfs = TwitchStream.JUST_CHATTING_MESSAGE_FORMATS
            elif new_state.status == TwitchState.ONLINE:
                mfs = TwitchStream.DEFAULT_LIVE_MESSAGE_FORMATS
            else:
                print('Invalid state for making a post: ', new_state.status)
                return None

            message_format = random.choice(mfs)
            message = message_format.format(
                user_name=self.user_name,
                game_name=new_state.game,
                twitch_link='https://twitch.tv/{}'.format(self.user_name))
            rv = (message, self.discord_channel_id)
        if self.state.status != new_state.status:
            # Right now only care about the status of prev_state, so don't need to check game name or stream title.
            self.prev_state = self.state
        self.state = new_state
        return rv


class TwitchState:
    NONE = 1
    OFFLINE = 2
    ONLINE = 3
    # Special case where the stream is online but in the "Just Chatting" category.
    JUST_CHATTING = 4

    def __init__(self, status=NONE, game=None, title=None):
        # TODO Check the game_id or something instead of the game name.
        if game == "Just Chatting" and status == TwitchState.ONLINE:
            status = TwitchState.JUST_CHATTING
        else:
            self.status = status
        self.game = game
        self.title = title


class TwitchCog(commands.Cog):

    def __init__(self, discord_client, twitch_manager):
        self.discord_client = discord_client
        self.twitch_manager = twitch_manager

        self.lock = asyncio.Lock()
        self.checkTwitchStreams.start()

    def cog_unload(self):
        self.checkTwitchStreams.cancel()

    @tasks.loop(seconds=60)
    async def checkTwitchStreams(self):
        if not self.lock.locked():
            async with self.lock:
                twitch_messages = self.twitch_manager.checkStateOfAllStreams()
                for value in twitch_messages:
                    if value is None:
                        continue
                    message, channel_id = value
                    await self.discord_client.get_channel(channel_id).send(
                        message)

    @checkTwitchStreams.before_loop
    async def before_checkTwitchStreams(self):
        await self.discord_client.wait_until_ready()


class TwitchDiscordCommandsBase(app_commands.Group):

    def __init__(self, twitch_manager, name, *args, **kwargs):
        super(TwitchDiscordCommandsBase, self).__init__(name=name,
                                                        *args,
                                                        **kwargs)
        self.twitch_manager = twitch_manager


class TwitchDiscordCommands(TwitchDiscordCommandsBase):

    def __init__(self, twitch_manager, *args, **kwargs):
        super(TwitchDiscordCommands, self).__init__(twitch_manager, 'twitch',
                                                    *args, **kwargs)

    @app_commands.command(
        name='add-self',
        description=
        'Add your twitch stream to the bot, so it posts when you go live!')
    @app_commands.describe(
        twitch_user_name='This requires the correct capitalization')
    async def add_self(self, interaction: discord.Interaction,
                       twitch_user_name: str):
        new_twitch_stream = TwitchStream(twitch_user_name, interaction.user.id,
                                         interaction.channel_id)
        was_successful = self.twitch_manager.addTwitchStream(new_twitch_stream)

        message = ''
        if was_successful:
            message = 'Twitch stream was successfully added to the bot! If you have any problems, contact the mods for help.'
        else:
            message = 'The twitch stream is already being tracked, contact the mods if you have any problems.'

        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(name='remove-self',
                          description='Remove your twitch stream to the bot')
    @app_commands.describe(
        twitch_user_name=
        'This needs to be the same string as stored in the bot, use the "check-self" command to get the exact string'
    )
    async def remove_self(self, interaction: discord.Interaction,
                          twitch_user_name: str):
        was_successful = self.twitch_manager.removeTwitchStream(
            twitch_user_name, interaction.user.id)

        message = ''
        if was_successful:
            message = 'Twitch stream was successfully removed from the bot! If you have any problems, contact the mods for help.'
        else:
            message = 'Unable to remove the specified twitch stream from the bot, use the "check-self" command to check your streams. Contact the mods if you need additional help.'

        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(name='check-self',
                          description='Check your tracked streams in the bot.')
    async def check_self(self, interaction: discord.Interaction):
        streams = self.twitch_manager.getTwitchStreamsByDiscordUser(
            interaction.user.id)

        message = ''
        if len(streams) == 0:
            message = 'You haven\'t added any streams to the bot. Use "add-self" to add a twitch stream of the bot.'
        else:
            stream_strs = []
            for stream in streams:
                ss = 'Tracking "{0.user_name}" at https://twitch.tv/{0.user_name}'.format(
                    stream)
                if len(stream.game_allowlist) > 0:
                    ss += '\nGame Allowlist: {}'.format(', '.join(
                        map(lambda s: '"{}"'.format(s),
                            stream.game_allowlist)))
                if stream.post_cooldown > datetime.timedelta():
                    ss += '\nPost Cooldown: {}'.format(
                        stream.getPostCooldownStr())
                stream_strs.append(ss)
            message = '\n\n'.join(stream_strs)

        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(
        name='add-to-allowlist',
        description='Adds a game to your twitch stream allowlist.')
    @app_commands.describe(
        twitch_user_name=
        'This needs to be the same string as stored in the bot, use the "check-self" command to get the exact string',
        game_name=
        'This needs to be the exact string used for the game within Twitch.')
    async def add_to_allowlist(self, interaction: discord.Interaction,
                               twitch_user_name: str, game_name: str):
        twitch_stream = self.twitch_manager.getTwitchStreamByUserNameAndId(
            twitch_user_name, interaction.user.id)

        message = ''
        if twitch_stream is None:
            message = 'Unable to get stream, use the "check-self" command to check your streams. Contact the mods if you need additional help.'
        else:
            twitch_stream.game_allowlist.append(game_name)
            self.twitch_manager.saveTwitchStreamsToFile()
            message = 'Game added to "{0.user_name}" allowlist, which is now: {1}'.format(
                twitch_stream, ', '.join(twitch_stream.game_allowlist))

        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(name='clear-allowlist',
                          description='Clears allowlist for specified stream.')
    @app_commands.describe(
        twitch_user_name=
        'This needs to be the same string as stored in the bot, use the "check-self" command to get the exact string'
    )
    async def clear_allowlist(self, interaction: discord.Interaction,
                              twitch_user_name: str):
        twitch_stream = self.twitch_manager.getTwitchStreamByUserNameAndId(
            twitch_user_name, interaction.user.id)

        message = ''
        if twitch_stream is None:
            message = 'Unable to get stream, use the "check-self" command to check your streams. Contact the mods if you need additional help.'
        else:
            twitch_stream.game_allowlist.clear()
            self.twitch_manager.saveTwitchStreamsToFile()
            message = 'Allowlist cleared!'

        await interaction.response.send_message(message, ephemeral=True)


class TwitchAdminDiscordCommands(TwitchDiscordCommandsBase):

    def __init__(self, twitch_manager, *args, **kwargs):
        super(TwitchAdminDiscordCommands,
              self).__init__(twitch_manager, 'twitch-admin', *args, **kwargs)

    @app_commands.command(
        name='add-other',
        description=
        'Add a twitch stream to the bot, so the bot posts when it goes live!')
    @app_commands.describe(
        discord_user=
        'User to associate this stream with. They will be able to edit the stream if they want.',
        twitch_user_name='This requires the correct capitalization')
    async def add_other(self, interaction: discord.Interaction,
                        discord_user: discord.User, twitch_user_name: str):
        new_twitch_stream = TwitchStream(twitch_user_name, discord_user.id,
                                         interaction.channel_id)
        was_successful = self.twitch_manager.addTwitchStream(new_twitch_stream)

        message = ''
        if was_successful:
            message = 'Twitch stream was successfully added to the bot!'
        else:
            message = 'The twitch stream is already being tracked.'

        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(
        name='remove-other',
        description='Remove the given twitch stream to the bot')
    @app_commands.describe(
        discord_user='User that the stream is associated with',
        twitch_user_name=
        'This needs to be the same string as stored in the bot, use the "check-self" command to get the exact string'
    )
    async def remove_other(self, interaction: discord.Interaction,
                           discord_user: discord.User, twitch_user_name: str):
        was_successful = self.twitch_manager.removeTwitchStream(
            twitch_user_name, discord_user.id)

        message = ''
        if was_successful:
            message = 'Twitch stream was successfully removed from the bot!'
        else:
            message = 'Unable to remove the specified twitch stream from the bot.'

        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(
        name='check-all',
        description='List all twitch streams tracked by the bot.')
    async def check_all(self, interaction: discord.Interaction):
        message = ''
        if len(self.twitch_manager.twitch_streams) == 0:
            message = 'No tracked streams in this bot'
        else:
            stream_strs = []
            for _, stream in self.twitch_manager.twitch_streams.items():
                ss = 'Tracking "{0.user_name}" at https://twitch.tv/{0.user_name}'.format(
                    stream)
                user = await interaction.client.fetch_user(
                    stream.discord_user_id)
                if user is not None:
                    ss += ' , assocated with {}'.format(user.display_name)

                if len(stream.game_allowlist) > 0:
                    ss += '\nGame Allowlist: {}'.format(', '.join(
                        map(lambda s: '"{}"'.format(s),
                            stream.game_allowlist)))
                if stream.post_cooldown > datetime.timedelta():
                    # Posts the timedelta in HH:MM format
                    ss += '\nPost Cooldown: {}'.format(
                        stream.getPostCooldownStr())
                if stream.super_mode:
                    ss += '\nSUPER MODE ENABLED'
                stream_strs.append(ss)
            message = '\n\n'.join(stream_strs)

        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(
        name='add-to-other-allowlist',
        description='Adds a game to a twitch stream\'s allowlist.')
    @app_commands.describe(
        discord_user='Discord user the stream is associated with',
        twitch_user_name=
        'This needs to be the same string as stored in the bot, use the "check-self" command to get the exact string',
        game_name=
        'This needs to be the exact string used for the game within Twitch.')
    async def add_to_other_allowlist(self, interaction: discord.Interaction,
                                     discord_user: discord.User,
                                     twitch_user_name: str, game_name: str):
        twitch_stream = self.twitch_manager.getTwitchStreamByUserNameAndId(
            twitch_user_name, discord_user.id)

        message = ''
        if twitch_stream is None:
            message = 'Unable to get stream, use the "check-all" command to check your streams. Contact the mods if you need additional help.'
        else:
            twitch_stream.game_allowlist.append(game_name)
            self.twitch_manager.saveTwitchStreamsToFile()
            message = 'Game added to "{0.user_name}" allowlist, which is now: {1}'.format(
                twitch_stream, ', '.join(twitch_stream.game_allowlist))

        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(name='clear-other-allowlist',
                          description='Clears allowlist for specified stream.')
    @app_commands.describe(
        discord_user='Discord user the stream is associated with',
        twitch_user_name=
        'This needs to be the same string as stored in the bot, use the "check-self" command to get the exact string'
    )
    async def clear_other_allowlist(self, interaction: discord.Interaction,
                                    discord_user: discord.User,
                                    twitch_user_name: str):
        twitch_stream = self.twitch_manager.getTwitchStreamByUserNameAndId(
            twitch_user_name, discord_user.id)

        message = ''
        if twitch_stream is None:
            message = 'Unable to get stream, use the "check-all" command to check your streams. Contact the mods if you need additional help.'
        else:
            twitch_stream.game_allowlist.clear()
            self.twitch_manager.saveTwitchStreamsToFile()
            message = 'Allowlist cleared!'

        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(
        name='set-post-cooldown',
        description='Set the cooldown for notifications for a stream.')
    @app_commands.describe(
        discord_user='Discord user the stream is associated with',
        twitch_user_name=
        'This needs to be the same string as stored in the bot, use the "check-all" command to get the exact string',
        hour_cooldown=
        'The cooldown for notifications to be posted. This value is in hours.')
    async def set_post_cooldown(self, interaction: discord.Interaction,
                                discord_user: discord.User,
                                twitch_user_name: str, hour_cooldown: float):
        twitch_stream = self.twitch_manager.getTwitchStreamByUserNameAndId(
            twitch_user_name, discord_user.id)

        message = ''
        if twitch_stream is None:
            message = 'Unable to get stream, use the "check-all" command to check your streams. Contact the mods if you need additional help.'
        else:
            twitch_stream.post_cooldown = datetime.timedelta(
                hours=hour_cooldown)
            self.twitch_manager.saveTwitchStreamsToFile()
            message = 'Updated twitch stream post cooldown to {}'.format(
                twitch_stream.getPostCooldownStr())

        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(name='toggle-super-mode',
                          description='Toggles super mode for given stream.')
    @app_commands.describe(
        discord_user='Discord user the stream is associated with',
        twitch_user_name=
        'This needs to be the same string as stored in the bot, use the "check-all" command to get the exact string'
    )
    async def toggle_super_mode(self, interaction: discord.Interaction,
                                discord_user: discord.User,
                                twitch_user_name: str):
        twitch_stream = self.twitch_manager.getTwitchStreamByUserNameAndId(
            twitch_user_name, discord_user.id)

        message = ''
        if twitch_stream is None:
            message = 'Unable to get stream, use the "check-all" command to check your streams. Contact the mods if you need additional help.'
        else:
            twitch_stream.super_mode = not twitch_stream.super_mode
            self.twitch_manager.saveTwitchStreamsToFile()
            message = 'Updated twitch stream so that super_mode = {}'.format(
                'true' if twitch_stream.super_mode else 'false')

        await interaction.response.send_message(message, ephemeral=True)


def addTestStreams(twitch_manager):
    BOT_TESTING_CHANNEL = 599237897580970013
    twitch_manager.addTwitchStream(
        TwitchStream('Fitzyhere', 0, BOT_TESTING_CHANNEL))
    twitch_manager.addTwitchStream(
        TwitchStream('burninate32', 2, BOT_TESTING_CHANNEL))
    twitch_manager.addTwitchStream(
        TwitchStream('kolvia', 4, BOT_TESTING_CHANNEL))


if __name__ == '__main__':
    twitch_manager = TwitchManager()
    addTestStreams(twitch_manager)
    print(twitch_manager.checkStateOfAllStreams())
