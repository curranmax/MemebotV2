import discord
from discord import app_commands
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

    def checkStateOfAllStreams(self, retry=False):
        if len(self.twitch_streams) <= 0:
            return

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
            return None

        new_states = {
            user_name: TwitchState(status=TwitchState.OFFLINE)
            for user_name in self.twitch_streams
        }

        # response.json()['data'] is a list that contains an entry for each live stream in the set of streams included in the 'user_login' params on the URL. Offline streams won't have any entry in the list.
        for live_stream in response.json()['data']:
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
        '{user_name} is now live playing {game_name}!\n{twitch_link}'
    ]

    def __init__(self, user_name, discord_user_id, discord_channel_id):
        self.user_name = user_name
        self.discord_user_id = discord_user_id
        self.discord_channel_id = discord_channel_id

        # Add in cooldown, allow_list, custom message formats,

        self.state = TwitchState()

    # Returns None if a message should not be sent, otherwise ()
    def updateState(self, new_state):
        rv = None
        if (self.state.status in (TwitchState.NONE, TwitchState.OFFLINE)
                and new_state.status == TwitchState.ONLINE):
            message_format = random.choice(
                TwitchStream.DEFAULT_LIVE_MESSAGE_FORMATS)
            message = message_format.format(user_name=self.user_name,
                                            game_name=new_state.game,
                                            twitch_link='twitch.tv/{}'.format(
                                                self.user_name))
            rv = (message, self.discord_channel_id)
        self.state = new_state
        return rv


class TwitchState:
    NONE = 1
    OFFLINE = 2
    ONLINE = 3

    def __init__(self, status=NONE, game=None, title=None):
        self.status = status
        self.game = game
        self.title = title


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
        'Add your twitch stream to the bot, so when you go live a post, the bot automatically makes a post!'
    )
    @app_commands.describe(
        twitch_user_name='This requires the correct capitalization')
    async def test(self, interaction: discord.Interaction,
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


class TwitchAdminDiscordCommands(TwitchDiscordCommandsBase):

    def __init__(self, twitch_manager, *args, **kwargs):
        super(TwitchAdminDiscordCommands,
              self).__init__(twitch_manager, 'twitch-admin', *args, **kwargs)


if __name__ == '__main__':
    twitch_manager = TwitchManager()
    twitch_manager.addTwitchStream(TwitchStream('KryticZeuz', 0, 1))
    twitch_manager.addTwitchStream(TwitchStream('burninate32', 2, 3))
    twitch_manager.addTwitchStream(TwitchStream('kolvia', 4, 5))
    twitch_manager.checkStateOfAllStreams()
