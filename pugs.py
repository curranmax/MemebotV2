from collections import defaultdict
import discord
from discord import app_commands
from fractions import Fraction
import itertools
import logging
import math
import random
import typing

TANK = 'Tank'
DPS = 'DPS'
SUPPORT = 'Support'
DEFAULT_COMP = [TANK, DPS, DPS, SUPPORT, SUPPORT]

MAPS_BY_MODE = {
    # TODO Add a way to choose these maps.
    'Clash': {
        'Hanaoka': [],
        'Throne of Anubis': [],
    },
    'Control': {
        'Antarctic Peninsula': ['Night', 'Morning'],
        'Busan': ['Overcast', 'Night', 'Morning'],
        'Ilios': ['Evening', 'Morning'],
        'Lijiang': ['Dawn', 'Night', 'Lunar New Year'],
        'Nepal': ['Evening', 'Morning'],
        'Oasis': ['Evening', 'Night', 'Morning'],
        'Samoa': [],
    },
    'Escort': {
        'Circuit Royal': ['Morning', 'Night'],
        'Dorado': ['Evening', 'Night'],
        'Havana': ['Morning', 'Night'],
        'Junkertown': ['Morning', 'Night'],
        'Rialto': ['Evening', 'Morning'],
        'Route 66': ['Morning', 'Overcast', 'Night'],
        'Shambali Monastery': [],
        'Watchpoint: Gibraltar': ['Evening', 'Morning'],
    },
    'Flashpoint': {
        'Aatlis': [],
        'New Junk City': [],
        'Suravasa': [],
    },
    'Hybrid': {
        'Blizzard World': ['Overcast', 'Night', 'Morning', 'Winter'],
        'Eichenwalde': ['Evening', 'Morning', 'Halloween'],
        'Hollywood': ['Night', 'Morning', 'Halloween'],
        'King\'s Row': ['Night', 'Evening', 'Winter'],
        'Midtown': ['Night', 'Morning'],
        'Numbani': [],
        'Paraíso': ['Evening', 'Morning'],
    },
    'Push': {
        'Colosseo': ['Evening', 'Morning'],
        'Esperança': [],
        'New Queen Street': ['Dawn', 'Morning'],
        'Runasapi': [],
    },
}


def RolesListFromInt(role_int):
    if role_int == 1:
        return [TANK]
    elif role_int == 2:
        return [DPS]
    elif role_int == 3:
        return [SUPPORT]
    elif role_int == 4:
        return [TANK, DPS]
    elif role_int == 5:
        return [TANK, SUPPORT]
    elif role_int == 6:
        return [DPS, SUPPORT]
    elif role_int == 7:
        return [TANK, DPS, SUPPORT]
    return []


def normalizeWeight(v, min_v, max_v):
    if min_v is None or max_v is None:
        return 0.0
    if min_v > max_v:
        min_v, max_v = max_v, min_v
    if abs(max_v - min_v) <= 1e-6:
        return 0.0
    return (v - min_v) / (max_v - min_v)


# Set of discord commands to interact with the PUGs feature.
async def sendUpdatedPlayerCount(channel, pugs_count):
    if pugs_count == 0:
        message = 'PUGs are now empty :('
    if pugs_count == 1:
        message = 'PUGs now have 1 player!'
    if pugs_count >= 2:
        message = 'PUGs now have {} players!'.format(pugs_count)
    if pugs_count < 0:
        message = 'PUGs have transcended and have {} players'.format(
            pugs_count)
    await channel.send(message)


class PugsDiscordCommands(app_commands.Group):

    def __init__(self, pugs_manager, *args, **kwargs):
        super(PugsDiscordCommands, self).__init__(name='pugs', *args, **kwargs)

        # TODO Also send a general message about the number of people in PUGs.
        self.pugs_manager = pugs_manager

    # Allows a user to join PUGs and specify what roles they want as well as specify a nickname.
    @app_commands.command(name='join', description='Join PUGs')
    @app_commands.describe(
        roles='What role(s) you are willing to play in PUGs.',
        nickname=
        'Nickname to use when announcing PUGs team. If not set, uses your name in this server.'
    )
    @app_commands.choices(roles=[
        app_commands.Choice(name='Just Tank', value=1),
        app_commands.Choice(name='Just DPS', value=2),
        app_commands.Choice(name='Just Support', value=3),
        app_commands.Choice(name='Tank and DPS', value=4),
        app_commands.Choice(name='Tank and Support', value=5),
        app_commands.Choice(name='DPS and Support', value=6),
        app_commands.Choice(name='Everything: Tank, DPS, and Support', value=7)
    ])
    async def join(self,
                   interaction: discord.Interaction,
                   roles: app_commands.Choice[int],
                   nickname: typing.Optional[str] = None):
        pugs_picker = self.pugs_manager.getPugsPicker(interaction.channel_id)
        if pugs_picker == None:
            await interaction.response.send_message(
                'No PUGs currently running!', ephemeral=True)
            return

        roles = RolesListFromInt(roles.value)
        if len(roles) <= 0:
            await interaction.response.send_message(
                'ERROR WHILE JOINING PUGs!!!', ephemeral=True)
            return

        discord_id = interaction.user.id
        discord_name = interaction.user.display_name
        nickname = nickname
        action, player = pugs_picker.addPlayer(discord_id, discord_name, roles,
                                               nickname)

        message = ''
        send_updated_player_count_message = False
        if action == PugsPicker.ADDED:
            message = 'You have successfully joined PUGs. Your current roles are: {}. Your display name is "{}"'.format(
                player.getRolesStr(), player.getDisplayName())

            send_updated_player_count_message = True
        elif action == PugsPicker.UPDATED:
            message = 'You are already in PUGs. Your current roles are: {}. Your display name is "{}"'.format(
                player.getRolesStr(), player.getDisplayName())
        else:
            message = 'Error joining PUGs.'

        await interaction.response.send_message(message, ephemeral=True)

        if send_updated_player_count_message:
            # Send general message that the count of PUGs has changed
            await sendUpdatedPlayerCount(
                interaction.client.get_channel(interaction.channel_id),
                len(pugs_picker.players))

    # Allows a user to update their info in PUGs.
    @app_commands.command(
        name='update',
        description='Update your roles (Tank, DPS, and/or Support) or nickname'
    )
    @app_commands.describe(
        roles='What role(s) you are willing to play in PUGs.',
        nickname=
        'Nickname to use when announcing PUGs team. If not set, uses your name in this server.'
    )
    @app_commands.choices(roles=[
        app_commands.Choice(name='Just Tank', value=1),
        app_commands.Choice(name='Just DPS', value=2),
        app_commands.Choice(name='Just Support', value=3),
        app_commands.Choice(name='Tank and DPS', value=4),
        app_commands.Choice(name='Tank and Support', value=5),
        app_commands.Choice(name='DPS and Support', value=6),
        app_commands.Choice(name='Everything: Tank, DPS, and Support', value=7)
    ])
    async def update(self,
                     interaction: discord.Interaction,
                     roles: app_commands.Choice[int],
                     nickname: typing.Optional[str] = None):
        pugs_picker = self.pugs_manager.getPugsPicker(interaction.channel_id)
        if pugs_picker == None:
            await interaction.response.send_message(
                'No PUGs currently running!', ephemeral=True)
            return

        roles = RolesListFromInt(roles.value)
        if len(roles) <= 0:
            await interaction.response.send_message(
                'ERROR WHILE JOINING PUGs!!!', ephemeral=True)
            return

        discord_id = interaction.user.id
        discord_name = interaction.user.display_name
        nickname = nickname
        action, player = pugs_picker.updatePlayer(discord_id, discord_name,
                                                  roles, nickname)

        message = ''
        if action == PugsPicker.UPDATED:
            message = 'You are info for PUGs has been updated. Your current roles are: {}. Your display name is "{}"'.format(
                player.getRolesStr(), player.getDisplayName())
        else:
            message = 'Error updating info in PUGs.'

        await interaction.response.send_message(message, ephemeral=True)

    # Allows a user to check their roles / nickname in PUGs
    @app_commands.command(name='check', description='Join PUGs')
    async def check(self, interaction: discord.Interaction):
        pugs_picker = self.pugs_manager.getPugsPicker(interaction.channel_id)
        if pugs_picker == None:
            await interaction.response.send_message(
                'No PUGs currently running!', ephemeral=True)
            return

        player = pugs_picker.getPlayer(interaction.user.id)

        message = ''
        if player is not None:
            message = 'You are in PUGs. Your current roles are: {}. Your display name is "{}"'.format(
                player.getRolesStr(), player.getDisplayName())
        else:
            message = 'Not currently in PUGs.'

        await interaction.response.send_message(message, ephemeral=True)

    # Allows users to leave PUGs
    @app_commands.command(name='leave', description='Leave PUGs')
    async def leave(self, interaction: discord.Interaction):
        pugs_picker = self.pugs_manager.getPugsPicker(interaction.channel_id)
        if pugs_picker == None:
            await interaction.response.send_message(
                'No PUGs currently running!', ephemeral=True)
            return

        action = pugs_picker.removePlayer(interaction.user.id)

        send_updated_player_count_message = False
        if action == PugsPicker.REMOVED:
            message = 'You have successfully left PUGs!'
            send_updated_player_count_message = True
        elif action == PugsPicker.ERROR:
            message = 'You aren\'t in PUGs! No need to leave!'
        else:
            message = 'Unknown error!!!'

        await interaction.response.send_message(message, ephemeral=True)

        if send_updated_player_count_message:
            # Send general message that the count of PUGs has changed
            await sendUpdatedPlayerCount(
                interaction.client.get_channel(interaction.channel_id),
                len(pugs_picker.players))

    # TODO Add a map vote system


# Main class the stores the state of PUGs, and generates new games.
class PugsAdminDiscordCommands(app_commands.Group):

    def __init__(self, pugs_manager, *args, **kwargs):
        # Setting default_permissions to discord.Permissions() means that the only server admins can use these commands.
        super(PugsAdminDiscordCommands, self).__init__(name='pugs-admin',
                                                       *args,
                                                       **kwargs)

        self.pugs_manager = pugs_manager

        self.map_vote_choices = None

    # Allows an admin to add another user
    @app_commands.command(name='add-user', description='Add a user to PUGs')
    @app_commands.describe(
        user='The user to add to PUGs',
        roles='What role(s) they are willing to play in PUGs.',
        nickname=
        'Nickname to use when announcing PUGs team. If not set, uses their name in this server.'
    )
    @app_commands.choices(roles=[
        app_commands.Choice(name='Just Tank', value=1),
        app_commands.Choice(name='Just DPS', value=2),
        app_commands.Choice(name='Just Support', value=3),
        app_commands.Choice(name='Tank and DPS', value=4),
        app_commands.Choice(name='Tank and Support', value=5),
        app_commands.Choice(name='DPS and Support', value=6),
        app_commands.Choice(name='Everything: Tank, DPS, and Support', value=7)
    ])
    async def add_user(self,
                       interaction: discord.Interaction,
                       user: discord.User,
                       roles: app_commands.Choice[int],
                       nickname: typing.Optional[str] = None):
        pugs_picker = self.pugs_manager.getPugsPicker(interaction.channel_id)
        if pugs_picker == None:
            await interaction.response.send_message(
                'No PUGs currently running!', ephemeral=True)
            return

        roles = RolesListFromInt(roles.value)
        if len(roles) <= 0:
            await interaction.response.send_message(
                'ERROR WHILE ADDING TO PUGs!!!', ephemeral=True)
            return

        discord_id = user.id
        discord_name = user.display_name
        nickname = nickname
        action, player = pugs_picker.addPlayer(discord_id, discord_name, roles,
                                               nickname)

        message = ''
        send_updated_player_count_message = False
        if action == PugsPicker.ADDED:
            message = 'You have successfully added {} to PUGs. {}\'s current roles are: {}. {}\'s display name is "{}"'.format(
                user.name, user.name, player.getRolesStr(), user.name,
                player.getDisplayName())
            send_updated_player_count_message = True
        elif action == PugsPicker.UPDATED:
            message = '{} is already in PUGs. {}\'s current roles are: {}. {}\'s display name is "{}"'.format(
                user.name, user.name, player.getRolesStr(), user.name,
                player.getDisplayName())
        else:
            message = 'Error adding {} to PUGs.'.format(user.name)

        await interaction.response.send_message(message, ephemeral=True)

        if send_updated_player_count_message:
            # Send general message that the count of PUGs has changed
            await sendUpdatedPlayerCount(
                interaction.client.get_channel(interaction.channel_id),
                len(pugs_picker.players))

    # Allows an admin to update another user.
    @app_commands.command(name='update-user',
                          description='Update a user to PUGs')
    @app_commands.describe(
        user='The user to update in PUGs',
        roles='What role(s) they are willing to play in PUGs.',
        nickname=
        'Nickname to use when announcing PUGs team. If not set, uses their name in this server.'
    )
    @app_commands.choices(roles=[
        app_commands.Choice(name='Just Tank', value=1),
        app_commands.Choice(name='Just DPS', value=2),
        app_commands.Choice(name='Just Support', value=3),
        app_commands.Choice(name='Tank and DPS', value=4),
        app_commands.Choice(name='Tank and Support', value=5),
        app_commands.Choice(name='DPS and Support', value=6),
        app_commands.Choice(name='Everything: Tank, DPS, and Support', value=7)
    ])
    async def update_user(self,
                          interaction: discord.Interaction,
                          user: discord.User,
                          roles: app_commands.Choice[int],
                          nickname: typing.Optional[str] = None):
        pugs_picker = self.pugs_manager.getPugsPicker(interaction.channel_id)
        if pugs_picker == None:
            await interaction.response.send_message(
                'No PUGs currently running!', ephemeral=True)
            return

        roles = RolesListFromInt(roles.value)
        if len(roles) <= 0:
            await interaction.response.send_message(
                'ERROR WHILE JOINING PUGs!!!', ephemeral=True)
            return

        discord_id = user.id
        discord_name = user.display_name
        nickname = nickname
        action, player = pugs_picker.updatePlayer(discord_id, discord_name,
                                                  roles, nickname)

        message = ''
        if action == PugsPicker.UPDATED:
            message = '{}\'s info for PUGs has been updated. {}\'s current roles are: {}. {}\'s display name is "{}"'.format(
                user.name, user.name, player.getRolesStr(), user.name,
                player.getDisplayName())
        else:
            message = 'Error updating info in PUGs.'

        await interaction.response.send_message(message, ephemeral=True)

    # Allows an admin to remove someone from pugs
    @app_commands.command(name='remove-user',
                          description='Removes given user from PUGs')
    @app_commands.describe(user='The user to remove from PUGs')
    async def remove_user(self, interaction: discord.Interaction,
                          user: discord.User):
        pugs_picker = self.pugs_manager.getPugsPicker(interaction.channel_id)
        if pugs_picker == None:
            await interaction.response.send_message(
                'No PUGs currently running!', ephemeral=True)
            return

        action = pugs_picker.removePlayer(user.id)

        send_updated_player_count_message = False
        if action == PugsPicker.REMOVED:
            message = 'You have successfully removed {} from PUGs!'.format(
                user.name)
            send_updated_player_count_message = True
        elif action == PugsPicker.ERROR:
            message = '{} is not in PUGs! No need to remove!'.format(user.name)
        else:
            message = 'Unknown error!!!'

        await interaction.response.send_message(message, ephemeral=True)

        if send_updated_player_count_message:
            # Send general message that the count of PUGs has changed
            await sendUpdatedPlayerCount(
                interaction.client.get_channel(interaction.channel_id),
                len(pugs_picker.players))

    @app_commands.command(name='check-all',
                          description='Checks all players currently in PUGs')
    @app_commands.describe(
        show_all=
        'Whether or not the response message should be visible to everyone or just the user that issued the command.'
    )
    async def check_all(self,
                        interaction: discord.Interaction,
                        show_all: typing.Optional[bool] = False):
        pugs_picker = self.pugs_manager.getPugsPicker(interaction.channel_id)
        if pugs_picker == None:
            await interaction.response.send_message(
                'No PUGs currently running!', ephemeral=True)
            return

        # TODO print out the user's discord name/display_name just incase they set a dumb nickname.

        # Table of players
        # Name | Role(s)
        # -----------------------
        #  Player Name | Role(s)
        data = [['Name', 'Role(s)']
                ] + [[player.getDisplayName(),
                      player.getRolesStr()]
                     for _, player in pugs_picker.players.items()]
        column_widths = [
            max(len(row[0]) for row in data),
            max(len(row[1]) for row in data)
        ]
        padded_values = [[' ' * math.floor((column_widths[ind] - len(row[ind])) / 2) + \
                          row[ind] + \
                          ' ' * math.ceil((column_widths[ind] - len(row[ind])) / 2) \
                          for ind in range(2)] for row in data]
        rows = ['  {} | {}  '.format(*row) for row in padded_values]
        table_str = rows[0] + '\n' + '-' * len(rows[0]) + '\n' + '\n'.join(
            rows[1:])

        # Number of games played

        pugs_state_message = 'Currently have {} PUGs players:\n```\n{}\n```'.format(
            len(pugs_picker.players), table_str)
        await interaction.response.send_message(pugs_state_message,
                                                ephemeral=not show_all)

    # Allows an admin to start new PUGs.
    @app_commands.command(
        name='start-pugs',
        description=
        'Starts PUGs in this channel. If there is already an existing instance, nothing happens.'
    )
    async def start_pugs(self, interaction: discord.Interaction):
        if self.pugs_manager.createPugsPicker(interaction.channel_id):
            message = 'PUGs have started!! Use "/pugs join" in this channel to join!'
            ephemeral = False
        else:
            message = 'PUGs already running in this channel.'
            ephemeral = True
        await interaction.response.send_message(message, ephemeral=ephemeral)

    # Allows an admin to stop PUGs.
    @app_commands.command(
        name='stop-pugs',
        description='Stops the PUGs currently running in this channel.')
    async def stop_pugs(self, interaction: discord.Interaction):
        if self.pugs_manager.deletePugsPicker(interaction.channel_id):
            message = 'PUGs have ended!'
            ephemeral = False
        else:
            message = 'No PUGs running in this channel.'
            ephemeral = True
        await interaction.response.send_message(message, ephemeral=ephemeral)

    # Generates a potential game. The game isn't locked in until "lock-in" is run.
    @app_commands.command(
        name='generate',
        description=
        'Generates a lineup for PUGs. The lineup isn\'t saved until the "lock-in" command is run'
    )
    @app_commands.describe(
        num_choices=
        'Number of possible to generate before choosing the one that minimizes the defined heuristic.',
        role_weight='Weight to give to the role balancing heuristic.',
        teammate_weight='Weight to give to the teammate balancing heuristic.')
    async def generate(self,
                       interaction: discord.Interaction,
                       num_choices: typing.Optional[int] = 50,
                       role_weight: typing.Optional[float] = 1.0,
                       teammate_weight: typing.Optional[float] = 1.0):
        pugs_picker = self.pugs_manager.getPugsPicker(interaction.channel_id)
        if pugs_picker == None:
            await interaction.response.send_message(
                'No PUGs currently running!', ephemeral=True)
            return

        if len(pugs_picker.players) < 2 * len(DEFAULT_COMP):
            await interaction.response.send_message(
                'Not enough players for PUGs. Need {}, but only have {}.'.
                format(2 * len(DEFAULT_COMP), len(pugs_picker.players)),
                ephemeral=True)

        pending_game, failure_reason = pugs_picker.generateGame(
            DEFAULT_COMP,
            num_choices=num_choices,
            role_weight=role_weight,
            teammate_weight=teammate_weight)

        if pending_game is None:
            # TODO Figure out why no game could be generated (not enough of a given role)
            await interaction.response.send_message(
                'Unable to generate a valid game. Lacking players in the following combination of roles: {}. Try using "check-all" to figure out what the problem is.'
                .format(','.join(failure_reason)),
                ephemeral=True)
        else:
            await interaction.response.send_message(
                'Generated Lineup:\n```\n{}\n\nSpectators: {}\n```\nUse the "lock-in" command to save this lineup.'
                .format(pending_game.getTableStr(),
                        pending_game.getSpectatorStr()),
                ephemeral=True)

    @app_commands.command(
        name='lock-in',
        description=
        'Locks in the most recently generated game. Use "generate" to generate a game.'
    )
    async def lock_in(self, interaction: discord.Interaction):
        pugs_picker = self.pugs_manager.getPugsPicker(interaction.channel_id)
        if pugs_picker == None:
            await interaction.response.send_message(
                'No PUGs currently running!', ephemeral=True)
            return

        if len(pugs_picker.players) < 2 * len(DEFAULT_COMP):
            await interaction.response.send_message(
                'Not enough players for PUGs. Need {}, but only have {}.'.
                format(2 * len(DEFAULT_COMP), len(pugs_picker.players)),
                ephemeral=True)

        next_game = pugs_picker.lockInPendingGame()

        if next_game is None:
            await interaction.response.send_message(
                'Unable to lock-in game. Use "generate" to generate a game',
                ephemeral=True)
        else:
            if len(next_game.specs) == 0:
                message = 'The next PUGs game will be:\n```\n{}\n```'.format(
                    next_game.getTableStr())
            else:
                message = 'The next PUGs game will be:\n```\n{}\n\nSpectators: {}\n```'.format(
                    next_game.getTableStr(), next_game.getSpectatorStr())

            await interaction.response.send_message(message, ephemeral=False)

    @app_commands.command(name='random-map',
                          description='Generates a random map')
    @app_commands.describe(
        control='Include Control maps.',
        escort='Include Escort maps.',
        hybrid='Include Hybrid maps.',
        push='Include Push maps.',
        flashpoint='Includ Flashpoint maps.',
    )
    async def random_map(self,
                         interaction: discord.Interaction,
                         control: typing.Optional[bool] = True,
                         escort: typing.Optional[bool] = True,
                         hybrid: typing.Optional[bool] = True,
                         push: typing.Optional[bool] = True,
                         flashpoint: typing.Optional[bool] = True):
        modes = []
        if control:
            modes.append('Control')
        if escort:
            modes.append('Escort')
        if hybrid:
            modes.append('Hybrid')
        if push:
            modes.append('Push')
        if flashpoint:
            modes.append('Flashpoint')

        if len(modes) == 0:
            await interaction.response.send_message(
                'No modes selected. Select at least one mode', ephemeral=True)
            return

        random_mode = random.choice(modes)
        if random_mode not in MAPS_BY_MODE:
            await interaction.response.send_message(
                'The random mode is not in the MAPS_BY_MODE dictionary. FIX THE DAMN CODE!!!',
                ephemeral=True)
            return

        base_map, variants = random.choice(
            list(MAPS_BY_MODE[random_mode].items()))

        message = 'The randomly chosen map is --> '
        if len(variants) == 0:
            message += '`{}`'.format(base_map)
        else:
            message += '`{} --> {}`'.format(base_map, random.choice(variants))

        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(name='make-map-vote',
                          description='Creates a vote for map to play in PUGs')
    @app_commands.describe(
        num_maps='Number of maps to add to map vote',
        control='Include Control maps.',
        escort='Include Escort maps.',
        hybrid='Include Hybrid maps.',
        push='Include Push maps.',
        flashpoint='Includ Flashpoint maps.',
    )
    async def make_map_vote(self,
                            interaction: discord.Interaction,
                            num_maps: typing.Optional[int] = 3,
                            control: typing.Optional[bool] = True,
                            escort: typing.Optional[bool] = True,
                            hybrid: typing.Optional[bool] = True,
                            push: typing.Optional[bool] = True,
                            flashpoint: typing.Optional[bool] = True,
                            make_post: typing.Optional[bool] = False):
        if not make_post:
            self.map_vote_choices = None

        if self.map_vote_choices is None:
            modes = []
            if control:
                modes.append('Control')
            if escort:
                modes.append('Escort')
            if hybrid:
                modes.append('Hybrid')
            if push:
                modes.append('Push')
            if flashpoint:
                modes.append('Flashpoint')

            if len(modes) == 0:
                await interaction.response.send_message(
                    'No modes selected. Select at least one mode',
                    ephemeral=True)
                return

            random_mode = random.choice(modes)
            if random_mode not in MAPS_BY_MODE:
                await interaction.response.send_message(
                    'The random mode is not in the MAPS_BY_MODE dictionary. FIX THE DAMN CODE!!!',
                    ephemeral=True)
                return

            maps_with_variants = random.sample(
                list(MAPS_BY_MODE[random_mode].items()),
                min(num_maps, len(MAPS_BY_MODE[random_mode])))

            self.map_vote_choices = [
                (base_map,
                 (None if len(variants) == 0 else random.choice(variants)))
                for base_map, variants in maps_with_variants
            ]

        vote_emotes = [
            '1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟'
        ]
        if len(vote_emotes) < len(self.map_vote_choices):
            await interaction.response.send_message(
                'Not enough voting options for the number of maps selected.',
                ephemeral=True)
            return

        final_maps = [
            '{}'.format(base_map) if variant is None else '{} --> {}'.format(
                base_map, variant)
            for base_map, variant in self.map_vote_choices
        ]

        if make_post:
            message = 'Vote for the next map for PUGs:\n' + '\n'.join(
                '  {} {}'.format(emote, map) for map, emote in zip(
                    final_maps, vote_emotes[:len(final_maps)]))

            await interaction.response.send_message(message)

            msg_obj = await interaction.original_response()
            for emote in vote_emotes[:len(final_maps)]:
                await msg_obj.add_reaction(emote)

            self.map_vote_choices = None
        else:
            message = 'The map vote will be:\n' + '\n'.join(
                '  {} {}'.format(emote, map) for map, emote in zip(
                    final_maps, vote_emotes[:len(final_maps)])
            ) + '\n\nRerun this command with "make_post" set to True to post publicly'

            await interaction.response.send_message(message, ephemeral=True)


class PugsManager:

    def __init__(self):
        self.pugs_pickers = {}

    def getDiscordCommands(self):
        return [PugsDiscordCommands(self), PugsAdminDiscordCommands(self)]

    def getPugsPicker(self, channel_id):
        if channel_id in self.pugs_pickers:
            return self.pugs_pickers[channel_id]
        return None

    def createPugsPicker(self, channel_id):
        if channel_id in self.pugs_pickers:
            return False
        self.pugs_pickers[channel_id] = PugsPicker()
        return True

    def deletePugsPicker(self, channel_id):
        if channel_id in self.pugs_pickers:
            del self.pugs_pickers[channel_id]
            return True
        return False


class PugsPicker:

    def __init__(self):
        self.players = {}
        self.old_players = {}

        self.pending_game = None
        self.past_games = []

    ADDED = 'added'
    UPDATED = 'updated'
    REMOVED = 'removed'
    ERROR = 'error'

    def addPlayer(self, discord_id, discord_name, roles, nickname=None):
        logging.info('Adding player: {}, {}'.format(discord_id, discord_name))
        if discord_id in self.players:
            logging.info('Player in PUGs, just updating info')
            return self.updatePlayer(discord_id, discord_name, roles, nickname)

        if discord_id in self.old_players:
            logging.info(
                'Player info in self.old_players, moving to self.players')
            new_player = self.old_players[discord_id]
            del self.old_players[discord_id]
        else:
            logging.info('Creating new Player')
            new_player = Player(discord_id, discord_name, roles, nickname)
        self.players[discord_id] = new_player
        return PugsPicker.ADDED, self.players[discord_id]

    def updatePlayer(self, discord_id, discord_name, roles, nickname=None):
        logging.info('Updating player: {}, {}'.format(discord_id,
                                                      discord_name))
        if discord_id not in self.players:
            logging.info('Player not in PUGs')
            return PugsPicker.ERROR, None
        player_to_update = self.players[discord_id]
        player_to_update.discord_name = discord_name
        player_to_update.nickname = nickname
        player_to_update.roles = roles
        logging.info('Player info updated')
        return PugsPicker.UPDATED, self.players[discord_id]

    def getPlayer(self, discord_id):
        if discord_id not in self.players:
            return None
        return self.players[discord_id]

    def removePlayer(self, discord_id):
        logging.info('Removing player: {}'.format(discord_id))
        if discord_id not in self.players:
            logging.info('Player not in PUGs')
            return PugsPicker.ERROR
        logging.info(
            'Moving player to self.old_players then removing from self.players'
        )
        self.old_players[discord_id] = self.players[discord_id]
        del self.players[discord_id]
        return PugsPicker.REMOVED

    def lockInPendingGame(self):
        logging.info('Locking in pending game')
        if self.pending_game == None:
            logging.info('No pending game')
            return None
        logging.info('Saving pending game')
        next_game = self.pending_game
        self._updateRoleWeights(next_game)
        self._updateTeammateCounts(next_game)
        self.pending_game = None
        self.past_games.append(next_game)
        return next_game

    def generateGame(self,
                     team_format=DEFAULT_COMP,
                     max_iterations=100,
                     num_choices=10,
                     role_weight=1.0,
                     teammate_weight=1.0):
        logging.info('Generating new PUGs game')
        valid, reason = self._checkIfGenerationPossible(team_format)
        logging.info('Check returned with: valid = {}, reason = {}'.format(
            str(valid), 'None' if reason is None else ', '.join(reason)))
        if not valid:
            return None, reason

        game_choices = []
        i = 0
        while len(game_choices) < num_choices and i < max(
                max_iterations, num_choices):
            pos_game = self._generateOneGame(team_format)
            if pos_game is not None:
                game_choices.append(pos_game)
            i += 1

        self.pending_game = self._chooseBestPossibleGame(
            game_choices,
            role_weight=role_weight,
            teammate_weight=teammate_weight)

        logging.info('Generation took {} iterations. {}'.format(
            i, 'Unable to generate game'
            if self.pending_game is None else 'Generated valid game'))
        return self.pending_game, reason

    def _checkIfGenerationPossible(self, team_format=DEFAULT_COMP):
        roles = list(set(team_format))
        combos = []
        for n in range(1, len(roles)):
            combos += itertools.combinations(roles, n)

        for roles in combos:
            num_required = 2 * sum(role in roles for role in team_format)
            num_players = sum(
                any(role in roles for role in player.roles)
                for _, player in self.players.items())
            if num_required > num_players:
                return False, roles
        return True, None

    def _sortPlayersByPriority(self):
        players_by_participation = defaultdict(list)
        for _, player in self.players.items():
            played_in = 0
            speced_in = 0
            for game in self.past_games:
                if player in game.team1 or player in game.team2:
                    played_in += 1
                if player in game.specs:
                    speced_in += 1
            players_by_participation[Fraction(
                played_in, played_in +
                speced_in if played_in + speced_in > 0 else 1)].append(player)
        return [
            players_by_participation[k]
            for k in sorted(players_by_participation)
        ]

    def _generateOneGame(self, team_format):
        priority_grouped_players = self._sortPlayersByPriority()

        new_team1 = [None] * len(team_format)
        new_team2 = [None] * len(team_format)
        new_specs = []

        for player_group in priority_grouped_players:
            random.shuffle(player_group)
            for player in player_group:
                # TODO Prefer to make teams with varied lineups (i.e. if two people have been on the same team together, prefer to place them on different teams).
                # TODO Prefer to make teams with balanced win-rates
                pos_spots = [(tn, i) for tn in (1, 2) \
                                for i, role in enumerate(team_format) \
                                    if role in player.roles and \
                                       ((tn == 1 and new_team1[i] is None) or \
                                        (tn == 2 and new_team2[i] is None))]

                if len(pos_spots) == 0:
                    new_specs.append(player)
                    continue

                rtn, ri = random.choice(pos_spots)
                (new_team1 if rtn == 1 else new_team2)[ri] = player

        if all(p is not None for p in new_team1 + new_team2):
            return Game(team_format, new_team1, new_team2, new_specs)
        # TODO If no game was generated, figure out if its impossible, and why (are there not enough tanks?)
        return None

    def _chooseBestPossibleGame(self,
                                game_choices,
                                role_weight=1.0,
                                teammate_weight=1.0):
        min_role_val = None
        max_role_val = None

        min_teammate_val = None
        max_teammate_val = None

        weighted_choices = []
        for game in game_choices:
            role_val = self._evaluateRoleFrequency(game)
            teammate_val = self._evaluateTeammateFrequency(game)

            weighted_choices.append((game, role_val, teammate_val))

            if min_role_val is None or role_val < min_role_val:
                min_role_val = role_val
            if max_role_val is None or role_val > max_role_val:
                max_role_val = role_val

            if min_teammate_val is None or teammate_val < min_teammate_val:
                min_teammate_val = teammate_val
            if max_teammate_val is None or teammate_val > max_teammate_val:
                max_teammate_val = teammate_val

        best_game = None
        best_game_val = None

        for g, rv, tv in weighted_choices:
            # Normalizes weights
            nrv = normalizeWeight(rv, min_role_val, max_role_val)
            ntv = normalizeWeight(tv, min_teammate_val, max_teammate_val)

            # Combine normalized weights
            val = nrv * role_weight + ntv * teammate_weight

            if best_game_val is None or val < best_game_val:
                best_game = game
                best_game_val = val
        return best_game

    def _evaluateRoleFrequency(self, game):
        total_weight = 0.0
        for _, player in self.players.items():
            role_in_game = None
            if player in game.team1:
                role_in_game = game.team_format[game.team1.index(player)]
            if player in game.team2:
                role_in_game = game.team_format[game.team2.index(player)]

            if role_in_game is None:
                total_weight += sum(w for _, w in player.role_weights.items())
                continue

            if role_in_game not in player.roles:
                continue

            role_count = {
                role: game.team_format.count(role)
                for role in player.roles
            }
            for role in [TANK, DPS, SUPPORT]:
                w = player.role_weights[role]
                if role in player.roles:
                    if role == role_in_game:
                        w += 1.0 - (role_count[role] /
                                    sum(c for _, c in role_count.items()))
                    else:
                        w += -role_count[role] / sum(
                            c for _, c in role_count.items())
                total_weight += abs(w)

        return total_weight

    def _updateRoleWeights(self, game):
        for _, player in self.players.items():
            role_in_game = None
            if player in game.team1:
                role_in_game = game.team_format[game.team1.index(player)]
            if player in game.team2:
                role_in_game = game.team_format[game.team2.index(player)]

            if role_in_game is None:
                continue

            if role_in_game not in player.roles:
                continue

            role_count = {
                role: game.team_format.count(role)
                for role in player.roles
            }
            for role in player.roles:
                if role == role_in_game:
                    player.role_weights[role] += 1.0 - (
                        role_count[role] / sum(c
                                               for _, c in role_count.items()))
                else:
                    player.role_weights[role] += -role_count[role] / sum(
                        c for _, c in role_count.items())

    def _evaluateTeammateFrequency(self, game):
        total_weight = 0.0
        for _, player in self.players.items():
            teammates = None
            if player in game.team1:
                teammates = game.team1
            if player in game.team2:
                teammates = game.team2

            if teammates is None:
                continue

            for teammate in teammates:
                if player == teammates:
                    continue
                total_weight += player.teammate_counts[teammate]

        return total_weight

    def _updateTeammateCounts(self, game):
        for _, player in self.players.items():
            teammates = None
            if player in game.team1:
                teammates = game.team1
            if player in game.team2:
                teammates = game.team2

            if teammates is None:
                continue

            for teammate in teammates:
                if teammate == player:
                    continue
                player.teammate_counts[teammate] += 1


class Player:

    def __init__(self, discord_id, discord_name, roles, nickname=None):
        self.discord_id = discord_id
        self.discord_name = discord_name
        self.nickname = nickname
        self.roles = roles

        self.role_weights = {TANK: 0.0, DPS: 0.0, SUPPORT: 0.0}

        # Key is other player, value is count of games as teammates
        self.teammate_counts = defaultdict(int)

    def getRolesStr(self):
        if len(self.roles) == 0:
            return 'None'
        if len(self.roles) == 1:
            return self.roles[0]
        if len(self.roles) == 2:
            return '{} and {}'.format(*self.roles)
        if len(self.roles) == 3:
            return '{}, {}, and {}'.format(*self.roles)
        return 'ERROR! Unexpected number of roles'

    def getDisplayName(self):
        if self.nickname is not None:
            return self.nickname
        return self.discord_name

    def __eq__(self, other):
        if not isinstance(other, Player):
            return False
        return self.discord_id == other.discord_id

    def __hash__(self):
        return hash(self.discord_id)


class Game:

    def __init__(self, team_format, team1, team2, specs):
        self.team_format = team_format
        self.team1 = team1
        self.team2 = team2
        self.specs = specs

    def getTableStr(self):
        #       |  Team 1  |  Team 2
        # ----------------------------
        #  Tank | Player 1 | Player 2
        # ...
        data = [['', 'Team 1', 'Team 2']] + \
               [[role, pt1.getDisplayName(), pt2.getDisplayName()] \
                    for role, pt1, pt2 in zip(self.team_format, self.team1, self.team2)]

        column_widths = [
            max(len(row[ind]) for row in data) for ind in range(3)
        ]
        padded_values = [[' ' * math.floor((column_widths[ind] - len(row[ind])) / 2) + \
                          row[ind] + \
                          ' ' * math.ceil((column_widths[ind] - len(row[ind])) / 2) \
                          for ind in range(3)] for row in data]
        rows = [' {} | {} | {} '.format(*row) for row in padded_values]
        table_str = rows[0] + '\n' + '-' * len(rows[0]) + '\n' + '\n'.join(
            rows[1:])
        return table_str

    def getSpectatorStr(self):
        return ', '.join(map(lambda p: p.getDisplayName(), self.specs))


if __name__ == "__main__":
    test_picker = PugsPicker()

    test_picker.addPlayer(1, 'a', [TANK, DPS, SUPPORT])
    test_picker.addPlayer(2, 'b', [TANK, DPS, SUPPORT])
    test_picker.addPlayer(3, 'c', [TANK, DPS, SUPPORT])
    test_picker.addPlayer(4, 'd', [TANK, DPS, SUPPORT])
    test_picker.addPlayer(5, 'e', [TANK, DPS, SUPPORT])

    test_picker.addPlayer(6, 'f', [TANK, DPS, SUPPORT])
    test_picker.addPlayer(7, 'g', [TANK, DPS, SUPPORT])
    test_picker.addPlayer(8, 'h', [TANK, DPS, SUPPORT])
    test_picker.addPlayer(9, 'i', [TANK, DPS, SUPPORT])
    test_picker.addPlayer(10, 'j', [TANK, DPS, SUPPORT])

    game, failure_reason = test_picker.generateGame(num_choices=10)
    test_picker.lockInPendingGame()
    print(game.getTableStr())

    game, failure_reason = test_picker.generateGame(num_choices=10)
    test_picker.lockInPendingGame()
    print(game.getTableStr())

    game, failure_reason = test_picker.generateGame(num_choices=10)
    test_picker.lockInPendingGame()
    print(game.getTableStr())

    game, failure_reason = test_picker.generateGame(num_choices=10)
    test_picker.lockInPendingGame()
    print(game.getTableStr())

    game, failure_reason = test_picker.generateGame(num_choices=10)
    test_picker.lockInPendingGame()
    print(game.getTableStr())

    print(test_picker.getPlayer(1).role_weights)
    print(test_picker.getPlayer(2).role_weights)
    print(test_picker.getPlayer(3).role_weights)
    print(test_picker.getPlayer(4).role_weights)
    print(test_picker.getPlayer(5).role_weights)
