import event_calendar as EC

import discord
from discord import app_commands
import typing
import os
import os.path
import pickle
from datetime import date as date_cls, datetime, time, timedelta
import logging
import pytz
import random
import re

# Move this data to firebase
MAPS = [
    # Escort
    'Circuit Royal',
    'Dorado',
    'Havana',
    'Junkertown',
    'Rialto',
    'Route 66',
    'Shambali Monastery',
    'Watchpoint: Gibraltar',

    # Hybrid
    'Blizzard World',
    'Eichenwalde',
    'Hollywood',
    'King\'s Row',
    'Midtown',
    'Numbani',
    'Paraíso',

    # Control
    'Antarctic Peninsula',
    'Busan',
    'Ilios',
    'Lijiang Tower',
    'Nepal',
    'Oasis',
    'Samoa',

    # Push
    'Colosseo',
    'Esperança',
    'New Queen Street',
    'Runasapi',

    # Flashpoint
    'New Junk City',
    'Suravasa',

    # Clash
    'Throne of Anubis',
    'Hanaoka',
]

TANK = 'Tank'
DPS = 'DPS'
SUPPORT = 'Support'
ROLES = [TANK, DPS, SUPPORT]
HEROES = {
    # Tanks
    'D.Va': TANK,
    'Doomfist': TANK,
    'Hazard': TANK,
    'Junker Queen': TANK,
    'Mauga': TANK,
    'Orisa': TANK,
    'Ramattra': TANK,
    'Reinhardt': TANK,
    'Roadhog': TANK,
    'Sigma': TANK,
    'Winston': TANK,
    'Wrecking Ball': TANK,
    'Zarya': TANK,

    # DPS
    'Ashe': DPS,
    'Bastion': DPS,
    'Cassidy': DPS,
    'Echo': DPS,
    'Freja': DPS,
    'Genji': DPS,
    'Hanzo': DPS,
    'Junkrat': DPS,
    'Mei': DPS,
    'Pharah': DPS,
    'Reaper': DPS,
    'Soldier: 76': DPS,
    'Sojourn': DPS,
    'Sombra': DPS,
    'Symmetra': DPS,
    'Torbjörn': DPS,
    'Tracer': DPS,
    'Venture': DPS,
    'Widowmaker': DPS,

    # Support
    'Ana': SUPPORT,
    'Baptiste': SUPPORT,
    'Brigitte': SUPPORT,
    'Illari': SUPPORT,
    'Juno': SUPPORT,
    'Kiriko': SUPPORT,
    'Lifeweaver': SUPPORT,
    'Lúcio': SUPPORT,
    'Mercy': SUPPORT,
    'Moira': SUPPORT,
    'Zenyatta': SUPPORT,
}

# Map from heroes available in stadium to list of powers.
# TODO Have a way to keep old powers that removed documented somewhere.
STADIUM_HEROES = {
    # Tank
    'D.Va': [
        'Focused Fusion',
        'Legendary Loadout',
        'Overstocked',
        'Countermeasures',
        'Facetanking',
        'Ultrawide Matrix',
        'Ignition Burst',
        'MEKA Punch',
        'Stat Boost',
        'Tokki Slam',
        'Express Detonation',
        'Party Protector',
    ],
    'Junker Queen': [
        'Thrill of Battle',
        'Royal Bullets',
        'Twist the Knife',
        'Blade Parade',
        'Cut \'em Gracie!',
        'Let\'s Go Win',
        'Merciless Magnetism',
        'Reckoner\'s Roar',
        'Chop Chop',
        'Soaring Stone',
        'Bloodcrazed',
        'Bow Down',
    ],
    'Orisa': [
        'Scorched Earh',
        'Shield Divergence',
        'Advanced Throwbotics',
        'Hot Rotate-O',
        'Spynstem Update',
        'Factory Reset',
        'Hooves of Steel',
        'Restortify'
        'Ride with Me',
        'Lassoed',
        'Centripetal Charge',
        'Supercharger',
    ],
    'Reinhardt': [
        'Amplification Barrier',
        'Barrier Reconstruction',
        'To Me, My Friends!',
        'Wilhelmwagen',
        'Shield Stampede',
        'Vanguard',
        'Vroom Boom Boom',
        'Blazing Blitz',
        'Impact Burst',
        'Magma Strike',
        'Feeling the Burn',
        'Smashing!',
    ],
    'Zarya': [
        'No Limits',
        'Royal Bullets',
        'Piercing Beam',
        'Pre-workout',
        'Barrier Benefits',
        'Containment Shield',
        'Fission Field',
        'Here to Spot You',
        'Lifelift',
        'Major Flex',
        'Volskaya Vortex',
        'Graviton Anomaly',
    ],

    # DPS
    'Ashe': [
        'Head Honcho',
        'Incendiary Rounds',
        'My Business, My Rules',
        'Reload Therapy',
        'Calamity',
        'Double Barreled',
        'Incendiary Blast',
        'Early Detonation',
        'Molten Munitions',
        'Out With a Bang',
        'B.O.B. Jr.',
        'Partners in Crime',
    ],
    'Cassidy': [
        'Bullseye',
        'Dead Man Walking',
        'Full House',
        'Quick Draw',
        'Think Flasht',
        'Barrel Roll',
        'Just Roll with It',
        'Flash in the Pan',
        'Hot Potato',
        'Easy Rider',
        'Sunrise',
        'Sunset',
    ],
    'Genji': [
        'Cybernetic Speed',
        'Hashimoto\'s Bane',
        'Sacred Shuriken',
        'Hanamura Healing',
        'Hidden Blade',
        'Laceration',
        'Wyrm\'s Maw',
        'Deflect-o-bot',
        'Forged Under Fire',
        'Iaido Strike',
        'Spirit of Sojiro',
        'Dragon\'s Breath',
    ],
    'Mei': [
        'Extendothermics',
        'Frost Armor',
        'Permafrost',
        'Slowball',
        'Iceberg',
        'Snowball Flight',
        'Twice As Ice',
        'Coulder',
        'Cyclone',
        'Frost Nova',
        'Avalanche',
        'Blizznado',
    ],
    'Reaper': [
        'Backstabber',
        'Harvest Fest',
        'Revolving Ruin',
        'Shared Siphon',
        'Shrouded Shrapnel',
        'Spirited to Slay',
        'Vampiric Touch',
        'Death Step',
        'Silen as the Grave',
        'Strangle Step',
        'Ghosted',
        'Wraith Renewal',
    ],
    'Soldier: 76': [
        'Peripheral Pulse',
        'Super Visor',
        'Chaingun',
        'Man on the Run',
        'Cratered',
        'Double Helix',
        'Hunker Down',
        'Back Off',
        'Biotic Bullseye',
        'Frontliners',
        'On Me!',
        'Track and Field',
    ],

    # Support
    'Ana': [
        'No Scope Needed',
        'Pinpoint Prescription',
        'Tactical Rifle',
        'Comfy Cloud',
        'Dreamy',
        'Sleep Regimen',
        'Home Remedy',
        'Time Out',
        'Venomous',
        'My Turn',
        'Our Turn',
        'Your Full Potential',
    ],
    'Juno': [
        'Medimaster',
        'Stinger',
        'Cosmic Coolant',
        'Medicinal Missiles',
        'Pulsar Plus',
        'Blink Boots',
        'Torpedo Glide',
        'Black Hole',
        'Hyper Healer',
        'Rally Ring',
        'Orbital Allignment',
        'Stellar Focus',
    ],
    'Kiriko': [
        'Foxy Fireworks',
        'Keen Kunai',
        'Triple Threat',
        'Leaf on the Wind',
        'Self-care',
        'Supported Shooting',
        'Clone Conjuration',
        'Fleet Foot',
        'Cleansing Charge',
        'Two-zu',
        'Crossing Guard',
        'Spirit Veil',
    ],
    'Lúcio': [
        'Fast Forward',
        'Signature Shift',
        'Sonic Boom',
        'Mixtape',
        'Megaphone',
        'Radio Edit',
        'Vivace',
        'Wallvibing',
        'Crowd Pleaser',
        'Let\'s Bounce',
        'Reverb',
        'Beat Drop',
    ],
    'Mercy': [
        'Distortion',
        'Glass Extra Full',
        'Protective Beam',
        'Serenity',
        'Threads of Fate',
        'Battle Medic',
        'Equivalent Exchange',
        'First Responder',
        'Renaissance',
        'The Whambulance',
        'Triage Unit',
        'Crepuscular Circle'
    ],
    'Moira': [
        'Chain Grasph',
        'Deconstruction',
        'Empowering You',
        'Ethereal Excision',
        'Optimal Overflow',
        'Precarious Potency',
        'Cross-orbal',
        'Multiball',
        'Phantasm',
        'Scientific Deathod',
        'Voidhoppers',
        'Descruction\'s Divide',
    ],
}


# Move this to a central util file.
def customEditDistance(v1, v2):
    # Convert to lower case
    v1 = v1.lower()
    v2 = v2.lower()

    # Swap the strings if v1 is longer.
    if len(v1) > len(v2):
        v1, v2 = v2, v1

    best_score = None
    for ind in range(0, len(v2) - len(v1) + 1):
        this_score = 0
        for c1, c2 in zip(v1, v2[ind:ind + len(v1)]):
            # TODO handle special characters
            if c1 != c2:
                this_score += 1
        if best_score is None or this_score < best_score:
            best_score = this_score
        if best_score == 0:
            return best_score
    return best_score


def getMap(map):
    if map not in MAPS:
        best_match = None
        best_ed = None
        for m in MAPS:
            m_ed = customEditDistance(map, m)
            if best_match is None or m_ed < best_ed:
                best_match = m
                best_ed = m_ed
        map = best_match
    return map


def getHero(hero):
    if hero not in HEROES:
        best_match = None
        best_ed = None
        for h, _ in HEROES.items():
            h_ed = customEditDistance(hero, h)
            if best_match is None or h_ed < best_ed:
                best_match = h
                best_ed = h_ed
        hero = best_match
    return hero


OW_TRACKER_FILENAME = 'data/ow_tracker.pickle'
SEASON_FILENAME = 'data/season.pickle'
HERO_CHALLENGE_FILENAME = 'data/hero_challenge.pickle'

AUTOCOMPLETE_LIMIT = 25


class OwTrackerDiscordCommands(app_commands.Group):
    RESULT_CHOICES = [
        app_commands.Choice(name=result, value=result)
        for result in ['Win', 'Loss', 'Draw']
    ]

    def __init__(self, ow_tracker_manager, *args, **kwargs):
        super(OwTrackerDiscordCommands, self).__init__(name='ow-tracker',
                                                       *args,
                                                       **kwargs)

        self.ow_tracker_manager = ow_tracker_manager

        # This is a workaround to make hero_autocomplete accept an optional role.
        self.autocomplete_role = None

    MAP_CHOICES = [app_commands.Choice(name=map, value=map) for map in MAPS]

    async def map_autocomplete(
            self, interaction: discord.Interaction,
            current: str) -> typing.List[app_commands.Choice[str]]:
        map_choices = list(OwTrackerDiscordCommands.MAP_CHOICES)

        # Get the edit distance between the current string and map name.
        map_edit_distance = {
            map: customEditDistance(map, current)
            for map in MAPS
        }

        # Sort maps by edit distance
        map_choices.sort(
            key=lambda map: (map_edit_distance[map.value], map.value))

        if len(map_choices) > AUTOCOMPLETE_LIMIT:
            map_choices = map_choices[:AUTOCOMPLETE_LIMIT]

        return map_choices

    HERO_CHOICES = [
        app_commands.Choice(name=hero, value=hero)
        for hero, _ in HEROES.items()
    ]

    async def hero_autocomplete_with_role(
            self, interaction: discord.Interaction,
            current: str) -> typing.List[app_commands.Choice[str]]:
        # This is a workaround to make hero_autocomplete accept an optional role.
        self.autocomplete_role = self.ow_tracker_manager.getSelectedRole(
            interaction.user.id)
        return await self.hero_autocomplete(interaction, current)

    async def hero_autocomplete(
            self, interaction: discord.Interaction,
            current: str) -> typing.List[app_commands.Choice[str]]:
        hero_choices = [
            v for v in OwTrackerDiscordCommands.HERO_CHOICES
            if self.autocomplete_role is None
            or HEROES[v.value] == self.autocomplete_role
        ]
        # This is a workaround to make hero_autocomplete accept an optional role.
        self.autocomplete_role = None

        # Get the edit distance between the current string and heroes. Subtract
        # out the difference between the hero name and current string to account
        # for extra characters.
        hero_edit_distance = {
            hero: customEditDistance(hero, current)
            for hero, _ in HEROES.items()
        }

        # Get the usage rate of the heroes
        hero_usage = self.ow_tracker_manager.getHeroUsage(interaction.user.id)

        # The heroes are sorted by (hero edit distance ascending, hero usage descending, hero name ascending)
        hero_choices.sort(key=lambda hero: (hero_edit_distance[
            hero.value], -hero_usage.get(hero.value, 0.0), hero.value))

        if len(hero_choices) > AUTOCOMPLETE_LIMIT:
            hero_choices = hero_choices[:AUTOCOMPLETE_LIMIT]

        return hero_choices

    async def stadium_hero_autocomplete(
            self, interaction: discord.Interaction,
            current: str) -> typing.List[app_commands.Choice[str]]:
        hero_choices = [
            v for v in OwTrackerDiscordCommands.HERO_CHOICES
            if v.value in STADIUM_HEROES.keys()
        ]

        # Get the edit distance between the current string and heroes.
        hero_edit_distance = {
            hero: customEditDistance(hero, current)
            for hero, _ in STADIUM_HEROES.items()
        }

        # The heroes are sorted by (hero edit distance ascending, hero name ascending)
        hero_choices.sort(key=lambda hero: (hero_edit_distance[hero.value], hero.value))

        if len(hero_choices) > AUTOCOMPLETE_LIMIT:
            hero_choices = hero_choices[:AUTOCOMPLETE_LIMIT]

        return hero_choices

    async def power_autocomplete(
            self, interaction: discord.Interaction,
            current: str) -> typing.List[app_commands.Choice[str]]:
        current_hero = interaction.namespace['hero']
        logging.info(f'power_autocomplete: interaction.namespace["hero"] = "{current_hero}"')

        if current_hero in STADIUM_HEROES:
            powers = [power for power in STADIUM_HEROES[current_hero]]
        else:
            powers = [power for _, powers in STADIUM_HEROES for power in powers]


        power_choices = [
            app_commands.Choice(name=power, value=power)
            for power in powers
        ]
        power_edit_distances = {
            power: customEditDistance(power, current)
            for power in powers
        }

        power_choices.sort(key=lambda power: (power_edit_distances[power.value], power.value))

        if len(power_choices) > AUTOCOMPLETE_LIMIT:
            power_choices = power_choices[:AUTOCOMPLETE_LIMIT]

        return power_choices

    @app_commands.command(name='add-win', description='Record win')
    @app_commands.describe(
        map='Map the game was played on.',
        hero=
        'Main hero played on the map. (Use add-hero to add additional heroes to this game)',
        percent='Percent of the map where this hero was played.')
    @app_commands.autocomplete(map=map_autocomplete, hero=hero_autocomplete)
    async def add_win(self,
                      interaction: discord.Interaction,
                      map: str,
                      hero: str,
                      percent: typing.Optional[float] = 1.0):
        await self._addGame(
            interaction,
            OverwatchGame(
                OverwatchGame.WIN, map, hero, percent,
                self.ow_tracker_manager.getSeason(interaction.user.id)))

    @app_commands.command(name='add-loss', description='Record lose')
    @app_commands.describe(
        map='Map the game was played on.',
        hero=
        'Main hero played on the map. (Use add-hero to add additional heroes to this game)',
        percent='Percent of the map where this hero was played.')
    @app_commands.autocomplete(map=map_autocomplete, hero=hero_autocomplete)
    async def add_loss(self,
                       interaction: discord.Interaction,
                       map: str,
                       hero: str,
                       percent: typing.Optional[float] = 1.0):
        await self._addGame(
            interaction,
            OverwatchGame(
                OverwatchGame.LOSS, map, hero, percent,
                self.ow_tracker_manager.getSeason(interaction.user.id)))

    @app_commands.command(name='add-draw', description='Record lose')
    @app_commands.describe(
        map='Map the game was played on.',
        hero=
        'Main hero played on the map. (Use add-hero to add additional heroes to this game)',
        percent='Percent of the map where this hero was played.')
    @app_commands.autocomplete(map=map_autocomplete, hero=hero_autocomplete)
    async def add_draw(self,
                       interaction: discord.Interaction,
                       map: str,
                       hero: str,
                       percent: typing.Optional[float] = 1.0):
        await self._addGame(
            interaction,
            OverwatchGame(
                OverwatchGame.DRAW, map, hero, percent,
                self.ow_tracker_manager.getSeason(interaction.user.id)))

    async def _addGame(self, interaction, new_game):
        latest_game = self.ow_tracker_manager.addGame(interaction.user.id,
                                                      new_game)
        message = 'Game added.\n' + self._getRecentResultMessage(
            interaction.user.id,
            num_days=7) + '\nAdded Game:\n' + latest_game.msgStr()

        await interaction.response.send_message(message, ephemeral=True)

    def _getRecentResultMessage(self, user_id, num_days=7):
        session_games = self.ow_tracker_manager.getGamesFromPastDays(
            user_id, num_days=1)
        total_games = self.ow_tracker_manager.getGamesFromPastDays(
            user_id, num_days=num_days)

        #  Today's Results     |   Recent Results (k days)
        # -------------------------------------------------
        #  Total -> XX-XX-XX   |   Total -> X-X-X
        #  Tank  -> X-X-X      |   Tank  -> X-X-X
        #  DPS   -> X-X-X      |   DPS   -> X-X-X
        #  Supp  -> X-X-X      |   Supp  -> X-X-X
        #
        # Weekly Goal: XX out of XX games played

        session_header = 'Today\'s Results'
        session_lines = self._getSummaryMessageByLine(session_games)

        total_header = 'Recent Results ({} days)'.format(num_days)
        total_lines = self._getSummaryMessageByLine(total_games)

        session_width = max(map(len, [session_header] + session_lines))

        joiner = '   |   '

        header = ' ' + session_header + ' ' * (
            session_width - len(session_header)) + joiner + total_header
        lines = [
            ' ' + sl + ' ' * (session_width - len(sl)) + joiner + tl
            for sl, tl in zip(session_lines, total_lines)
        ]

        msg = '\n'.join(['```', header, '-' * (len(header) + 1)] + lines + ['```'])

        goal, goal_games = self.ow_tracker_manager.getCurrentWeeklyGoalStatus(user_id)
        if goal is not None:
            msg += '\n\n```Weekly Goal: ' + str(len(goal_games)) + ' out of ' + str(goal) + ' games played```'

        return msg

    def _getSummaryMessageByLine(self, games):
        overall_result = {result: 0 for result in OverwatchGame.RESULTS}
        result_by_role = {(role, result): 0
                          for role in ROLES
                          for result in OverwatchGame.RESULTS}
        for game in games:
            overall_result[game.result] += 1
            if (game.role, game.result) in result_by_role:
                result_by_role[(game.role, game.result)] += 1

        return [
            'Total -> {}-{}-{}'.format(overall_result[OverwatchGame.WIN],
                                       overall_result[OverwatchGame.LOSS],
                                       overall_result[OverwatchGame.DRAW]),
            'Tank  -> {}-{}-{}'.format(
                result_by_role[(TANK, OverwatchGame.WIN)],
                result_by_role[(TANK, OverwatchGame.LOSS)],
                result_by_role[(TANK, OverwatchGame.DRAW)]),
            'DPS   -> {}-{}-{}'.format(
                result_by_role[(DPS, OverwatchGame.WIN)],
                result_by_role[(DPS, OverwatchGame.LOSS)],
                result_by_role[(DPS, OverwatchGame.DRAW)]),
            'Supp  -> {}-{}-{}'.format(
                result_by_role[(SUPPORT, OverwatchGame.WIN)],
                result_by_role[(SUPPORT, OverwatchGame.LOSS)],
                result_by_role[(SUPPORT, OverwatchGame.DRAW)])
        ]

    def _getSummaryMessage(self, games):
        lines = self._getSummaryMessageByLine(games)
        return '```\n' + '\n'.join(lines) + '\n```'

    @app_commands.command(name='add-hero',
                          description='Add extra hero info to latest game')
    @app_commands.describe(
        hero='Additional hero played on the map.',
        percent='Percent of the map where this hero was played.')
    @app_commands.autocomplete(hero=hero_autocomplete_with_role)
    async def add_hero(self, interaction: discord.Interaction, hero: str,
                       percent: float):
        result = self.ow_tracker_manager.addHeroToSelectedGame(
            interaction.user.id, hero, percent)
        message = ''
        if result is not None:
            message = 'Hero successful appending to last game.\n' + result.msgStr(
            )
        else:
            message = 'Unable able to add hero to last game'
        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(name='list-recent-games',
                          description='Stats on recent results.')
    @app_commands.describe(num_games='Number of games to show.')
    async def list_recent_games(self,
                                interaction: discord.Interaction,
                                num_games: typing.Optional[int] = 10):
        if num_games < 1:
            num_games = 1

        recent_games = self.ow_tracker_manager.getRecentGames(
            interaction.user.id, num_games=num_games)

        message = 'Results (W-L-D) of the {} game(s):\n'.format(
            len(recent_games))
        message += self._getSummaryMessage(recent_games)

        for i, game in enumerate(reversed(recent_games)):
            message += '\nGame {}'.format(i + 1) + game.msgStr()

        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(
        name='select-recent-game',
        description=
        'Changes the selected game which can be editted by "update-game" and "add-hero" commands.'
    )
    @app_commands.describe(
        game_ind=
        'Index of the game to select. Use "list-recent-games" to see recent games with index.'
    )
    async def select_recent_game(self, interaction: discord.Interaction,
                                 game_ind: int):
        new_selected_game = self.ow_tracker_manager.selectGame(
            interaction.user.id, game_ind)
        if new_selected_game is None:
            message = 'Invalid "game_ind" specified'
        else:
            message = 'Selected game is now:\n' + new_selected_game.msgStr()

        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(
        name='update-game',
        description=
        'Update selected game. Use "select-recent-game" to select a recent game.'
    )
    @app_commands.describe(
        result='Result of the match.',
        map='Map the game was played on.',
        hero=
        'Main hero played on the map. (Use add-hero to add additional heroes to this game)',
        percent='Percent of the map where this hero was played.')
    @app_commands.choices(result=RESULT_CHOICES)
    @app_commands.autocomplete(map=map_autocomplete, hero=hero_autocomplete)
    async def update_game(
            self,
            interaction: discord.Interaction,
            result: typing.Optional[app_commands.Choice[str]] = None,
            map: typing.Optional[str] = None,
            hero: typing.Optional[str] = None,
            percent: typing.Optional[float] = 1.0,
            season: typing.Optional[int] = None):
        if result is not None:
            result = result.value

        updated_game = self.ow_tracker_manager.updateGame(
            interaction.user.id, result, map, hero, percent, season)

        if updated_game is None:
            message = 'Unable to update game.'
        else:
            message = 'Game updated to:\n' + updated_game.msgStr()

        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(
        name='update-season',
        description=
        'Updates the season for anyone new games. If no arg is given, then the current value will be printed.'
    )
    @app_commands.describe(
        season=
        'Value to update the tracked season to. If not given, the current tracked value.'
    )
    async def update_season(self,
                            interaction: discord.Interaction,
                            season: typing.Optional[int] = None):
        if season is not None:
            self.ow_tracker_manager.updateSeason(interaction.user.id, season)

        message = 'Tracker will set new games to season {}'.format(
            self.ow_tracker_manager.getSeason(interaction.user.id))
        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(
        name='hero-usage-stats',
        description=
        'Output stats about hero usage and winrate for the last 3 seasons.')
    @app_commands.describe(
        include_zero_gp_heroes=
        'Whether or not to include heroes with zero games played. False by default.',
        num_heroes='Maximum number of heroes PER ROLE to display.')
    async def hero_usage_stats(
            self,
            interaction: discord.Interaction,
            include_zero_gp_heroes: typing.Optional[bool] = False,
            num_heroes: typing.Optional[int] = None):
        # Tank --> GP XX, WLD WW.W-LL.L-DD.D
        # -----------------------------------------
        # Hero #1 --> GP XX, R WW.W-LL.L-DD.D
        # ...
        # -----------------------------------------
        #
        # DPS --> GP XX, WLD WW-LL-DD
        # -----------------------------------------
        # Hero #1 --> GP XX, R WW.W-LL.L-DD.D
        # ...
        # -----------------------------------------
        #
        # Support --> GP XX, WLD WW-LL-DD
        # -----------------------------------------
        # Hero #1 --> GP XX, R WW.W-LL.L-DD.D
        # ...
        # -----------------------------------------
        hero_usage = self.ow_tracker_manager.getHeroUsage(interaction.user.id)
        hero_usage_by_result = self.ow_tracker_manager.getHeroUsageByResult(
            interaction.user.id)

        num_format = lambda v: '{:.2f}'.format(v).rstrip('0').rstrip('.')

        lines = []
        for role in ROLES:
            gp_role = sum(
                hero_usage.get(h, 0.0) for h, r in HEROES.items() if r == role)
            result_role = {
                result: sum(
                    hero_usage_by_result.get(h, {result: 0.0})[result]
                    for h, r in HEROES.items() if r == role)
                for result in OverwatchGame.RESULTS
            }

            rows = []
            for hero, hr in HEROES.items():
                if hr != role:
                    continue

                if not include_zero_gp_heroes and hero_usage.get(hero,
                                                                 0.0) <= 0.0:
                    continue

                rows.append(
                    (hero, hero_usage.get(hero, 0.0),
                     hero_usage_by_result.get(
                         hero, {OverwatchGame.WIN: 0.0})[OverwatchGame.WIN],
                     hero_usage_by_result.get(
                         hero, {OverwatchGame.LOSS: 0.0})[OverwatchGame.LOSS],
                     hero_usage_by_result.get(
                         hero, {OverwatchGame.DRAW: 0.0})[OverwatchGame.DRAW]))

            # Sort heroes by (usage descending, name ascending)
            rows.sort(key=lambda vs: (-vs[1], vs[0]))

            if num_heroes is not None and len(rows) > num_heroes:
                rows = rows[:num_heroes]

            # Format each value
            rows = [(h, num_format(u), num_format(w), num_format(l),
                     num_format(d)) for i, (h, u, w, l, d) in enumerate(rows)]

            if len(rows) > 0:
                # Add padding to make each row evenly spaced
                max_row_size = [max(len(r[i]) for r in rows) for i in range(2)]
                rows = [(row[0] + ' ' * (max_row_size[0] - len(row[0])),
                         ' ' * (max_row_size[1] - len(row[1])) + row[1],
                         row[2], row[3], row[4]) for row in rows]

                lines.append('{0} -> GP {1}, WLD {2}-{3}-{4}'.format(
                    role, num_format(gp_role),
                    num_format(result_role[OverwatchGame.WIN]),
                    num_format(result_role[OverwatchGame.LOSS]),
                    num_format(result_role[OverwatchGame.DRAW])))
                lines.append('-')

                for vs in rows:
                    lines.append(' {} -> GP {}, WLD {}-{}-{}'.format(*vs))
                lines.append('-')
                lines.append('')
        max_len = max(len(line) for line in lines)
        for i in range(len(lines)):
            if lines[i] == '-':
                lines[i] = '-' * (max_len)

        message = '```\n' + '\n'.join(lines) + '```'
        if len(message) >= 2000:
            message = 'Result is too large, use the "num_heroes" arg to decrease size of the result.'
        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(
        name='weekly-goal',
        description=
        'Set or get the number of games for the weekly goal.')
    @app_commands.describe(
        new_weekly_goal='The value for the new goal. If not set, then the current weekly goal will be returned.')
    async def weekly_goal(
        self,
        interaction: discord.Interaction,
        new_weekly_goal: typing.Optional[int] = None,
        # TODO Add a way to clear the weekly goal.
    ):
        # If user didn't include a parameter, just return their current goal.
        if new_weekly_goal is None:
            current_weekly_goal = self.ow_tracker_manager.getWeeklyGoal(interaction.user.id)

            if current_weekly_goal is None:
                message = 'Weekly goal is not set.'
            else:
                message = f'Weekly goal is {current_weekly_goal} games.'

            await interaction.response.send_message(message, ephemeral=True)
            return
        # If the user set a new goal, then update their tracker.
        if new_weekly_goal is not None:
            self.ow_tracker_manager.setWeeklyGoal(interaction.user.id, new_weekly_goal)
            await interaction.response.send_message(f'Weekly goal updated to {new_weekly_goal} games.', ephemeral=True)


    # TODO Add commands/support for
    #    Weekly goals
    #    Look at arbirtary range of dates
    #    Look at stats per hero/map/mode
    #    Look at stats per season

    @app_commands.command(name='add-stadium-game', description='Record stadium game.')
    @app_commands.describe(
        result='Whether you won or lost the game.',
        hero='The hero played in this game.',
        round_1_power='The power selected in Round #1.',
        round_3_power='The power selected in Round #3.',
        round_5_power='The power selected in Round #5. Leave blank, if the game didn\'t reach Round #5.',
        round_7_power='The power selected in Round #7. Leave blank, if the game didn\'t reach Round #7.',
        date='Optional way to record games that happened at a previous date. Use MM/DD(/YYYY)? format. If not set, game is recorded as today.')
    @app_commands.autocomplete(
        hero=stadium_hero_autocomplete,
        round_1_power=power_autocomplete,
        round_3_power=power_autocomplete,
        round_5_power=power_autocomplete,
        round_7_power=power_autocomplete)
    @app_commands.choices(result=[
        app_commands.Choice(name='Win', value='Win'),
        app_commands.Choice(name='Loss', value='Loss'),
    ])
    async def add_stadium_game(
            self,
            interaction: discord.Interaction,
            result: str,
            hero: str,
            round_1_power: str,
            round_3_power: str,
            round_5_power: typing.Optional[str] = None,
            round_7_power: typing.Optional[str] = None,
            date: typing.Optional[str] = None):

        season = self.ow_tracker_manager.getSeason(interaction.user.id)

        # Get current time in PT or use the supplied date parameter.
        dt = datetime.now(tz=pytz.timezone('US/Pacific'))
        if date is not None:
            # If date is given override that date.
            pattern = re.compile(r'^(?P<month>\d{1,2})\/(?P<day>\d{1,2})(?:\/(?P<year>\d{2}|\d{4}))?$')
            # TODO Define this REGEX in a common place
            date_match = HeroChallengeDiscordCommands.DATE_REGEX.match(date)
            if date_match is None:
                await interaction.response.send_message('Invalid date format!', ephemeral=True)
                return
            month = int(date_match.group('month'))
            day = int(date_match.group('day'))
            year = date_match.group('year')

            if year is not None:
                year = int(year)
                if year < 100:
                    year += 2000
            else:
                year = dt.date().year

            try:
                date = date_cls(year, month, day)
                dt = datetime.combine(date, dt.time())
            except ValueError:
                await interaction.response.send_message('Invalid date!', ephemeral=True)
                return

        stadium_game = StadiumGame(
            result, hero, season,
            round_1_power, round_3_power, round_5_power, round_7_power,
            dt)

        latest_game = self.ow_tracker_manager.addStadiumGame(interaction.user.id, stadium_game)
        message = 'Game added.\n' + self._getRecentStadiumResultMessage(interaction.user.id, num_days=7)
        message += '\nAdded Game:\n' + latest_game.msgStr()

        await interaction.response.send_message(message, ephemeral=True)

    def _getRecentStadiumResultMessage(self, user_id, num_days=7):
        session_games = self.ow_tracker_manager.getStadiumGamesFromPastDays(
            user_id, num_days=1)
        total_games = self.ow_tracker_manager.getStadiumGamesFromPastDays(
            user_id, num_days=num_days)

        #  Today's Results | Recent Results (k days)
        # ----------------------------------------------
        #  Total -> XX-XX  | Total -> XX-XX
        #  Tank  -> X-X    | Tank  -> X-X
        #  DPS   -> X-X    | DPS   -> X-X
        #  Supp  -> X-X    | Supp  -> X-X
        #
        # Weekly Goal: XX out of XX games played

        session_header = 'Today\'s Results'
        session_lines = self._getStadiumSummaryMessageByLine(session_games)

        total_header = 'Recent Results ({} days)'.format(num_days)
        total_lines = self._getStadiumSummaryMessageByLine(total_games)

        session_width = max(map(len, [session_header] + session_lines))

        joiner = ' | '

        header = ' ' + session_header + ' ' * (
            session_width - len(session_header)) + joiner + total_header
        lines = [
            ' ' + sl + ' ' * (session_width - len(sl)) + joiner + tl
            for sl, tl in zip(session_lines, total_lines)
        ]

        msg = '\n'.join(['```', header, '-' * (len(header) + 1)] + lines + ['```'])

        # TODO integrate stadium into the weekly goal
        # goal, goal_games = self.ow_tracker_manager.getCurrentWeeklyGoalStatus(user_id)
        # if goal is not None:
        #     msg += '\n\n```Weekly Goal: ' + str(len(goal_games)) + ' out of ' + str(goal) + ' games played```'

        return msg

    def _getStadiumSummaryMessageByLine(self, games):
        overall_result = {result: 0 for result in StadiumGame.RESULTS}
        result_by_role = {(role, result): 0
                          for role in ROLES
                          for result in StadiumGame.RESULTS}
        for game in games:
            overall_result[game.result] += 1
            if (game.role, game.result) in result_by_role:
                result_by_role[(game.role, game.result)] += 1

        return [
            'Total -> {}-{}'.format(overall_result[StadiumGame.WIN],
                                       overall_result[StadiumGame.LOSS]),
            'Tank  -> {}-{}'.format(
                result_by_role[(TANK, StadiumGame.WIN)],
                result_by_role[(TANK, StadiumGame.LOSS)]),
            'DPS   -> {}-{}'.format(
                result_by_role[(DPS, StadiumGame.WIN)],
                result_by_role[(DPS, StadiumGame.LOSS)]),
            'Supp  -> {}-{}'.format(
                result_by_role[(SUPPORT, StadiumGame.WIN)],
                result_by_role[(SUPPORT, StadiumGame.LOSS)])
        ]


class OverwatchTrackerManager:

    def __init__(self, ow_tracker_fname=OW_TRACKER_FILENAME, event_calendar=None):
        self.ow_tracker_fname = ow_tracker_fname
        self.loadTrackersFromFile()

        self.event_calendar = event_calendar

        if self.event_calendar is not None:
            self.event_calendar.addEvent(EC.Event(self.getNextWeeklyGoalEventTime(), self.upateWeeklyChallenge))

    def getDiscordCommands(self):
        return [OwTrackerDiscordCommands(self)]

    # TODO make this async
    def loadTrackersFromFile(self):
        # If file does not exist, then init self.overwatch_trackers to empty dict
        if not os.path.exists(self.ow_tracker_fname):
            self.overwatch_trackers = {}
            self.saveTrackersToFile()
            return

        f = open(self.ow_tracker_fname, 'rb')
        self.overwatch_trackers = pickle.load(f)

        # TMP While debugging
        for _, owt in self.overwatch_trackers.items():
            owt.stadium_games = []
            owt.selected_stadium_game = None

    # TODO make this async
    def saveTrackersToFile(self):
        f = open(self.ow_tracker_fname, 'wb')
        pickle.dump(self.overwatch_trackers, f)

    def addGame(self, user_id, overwatch_game):
        overwatch_tracker = self._getOrCreateOwTrackerForUser(user_id)
        rv = overwatch_tracker.addGame(overwatch_game)
        self.saveTrackersToFile()
        return rv

    def addHeroToSelectedGame(self, user_id, hero, weight):
        overwatch_tracker = self._getOrCreateOwTrackerForUser(user_id)
        result = overwatch_tracker.addHeroToSelectedGame(hero, weight)
        if result is not None:
            self.saveTrackersToFile()
        return result

    def getGamesFromPastDays(self, user_id, num_days=7):
        overwatch_tracker = self._getOrCreateOwTrackerForUser(user_id)
        return overwatch_tracker.getGamesFromPastDays(num_days=num_days)

    def getRecentGames(self, user_id, num_games=10):
        overwatch_tracker = self._getOrCreateOwTrackerForUser(user_id)
        return overwatch_tracker.getRecentGames(num_games=num_games)

    def selectGame(self, user_id, game_ind):
        overwatch_tracker = self._getOrCreateOwTrackerForUser(user_id)
        return overwatch_tracker.selectGame(game_ind)

    def updateGame(self, user_id, result, map, hero, weight, season):
        overwatch_tracker = self._getOrCreateOwTrackerForUser(user_id)
        updated_game = overwatch_tracker.updateGame(result, map, hero, weight,
                                                    season)
        if updated_game is not None:
            self.saveTrackersToFile()
        return updated_game

    def _getOrCreateOwTrackerForUser(self, user_id):
        if user_id not in self.overwatch_trackers:
            self.overwatch_trackers[user_id] = OverwatchTracker()
        return self.overwatch_trackers[user_id]

    def getSeason(self, user_id):
        overwatch_tracker = self._getOrCreateOwTrackerForUser(user_id)
        return overwatch_tracker.season

    def updateSeason(self, user_id, new_season):
        overwatch_tracker = self._getOrCreateOwTrackerForUser(user_id)
        season_changed = overwatch_tracker.updateSeason(new_season)
        if season_changed:
            self.saveTrackersToFile()

    def getHeroUsage(self, user_id):
        return self._getOrCreateOwTrackerForUser(user_id).getHeroUsage()

    def getHeroUsageByResult(self, user_id):
        return self._getOrCreateOwTrackerForUser(
            user_id).getHeroUsageByResult()

    def getSelectedRole(self, user_id):
        if user_id not in self.overwatch_trackers:
            return None
        return self._getOrCreateOwTrackerForUser(user_id).getSelectedRole()

    def getWeeklyGoal(self, user_id):
        if user_id not in self.overwatch_trackers:
            return None
        return self._getOrCreateOwTrackerForUser(user_id).getWeeklyGoal()
    
    def setWeeklyGoal(self, user_id, new_weekly_goal):
        return self._getOrCreateOwTrackerForUser(user_id).setWeeklyGoal(new_weekly_goal)

    def getCurrentWeeklyGoalStatus(self, user_id):
        return self._getOrCreateOwTrackerForUser(user_id).getCurrentWeeklyGoalStatus()

    async def upateWeeklyChallenge(self):
        for _, tracker in self.overwatch_trackers.items():
            # TODO Send a message to user's. They should be able to enable or disable this message and configure where its sent.
            tracker.advanceWeek()

        return EC.Event(self.getNextWeeklyGoalEventTime(), self.upateWeeklyChallenge)

    def getNextWeeklyGoalEventTime(self):
        now = datetime.now(pytz.timezone('US/Pacific'))
        pt = time(hour=8, tzinfo=pytz.timezone('US/Pacific'))

        # Advance to the next tuesday
        # weekday returns Monday to Sunday as 0 to 6.
        pd = 1 - now.weekday()
        if pd < 0 or (pd == 0 and now.time() >= time(hour=7, minute=45, tzinfo=pytz.timezone('US/Pacific'))): # This is purposefully 15 minutes before pt.
            pd += 7

        et = datetime.combine((now + timedelta(days=pd)).date(), pt)

        logging.info('getNextWeeklyGoalEventTime(): now = %s, et = %s', now.isoformat(), et.isoformat())
        return et

    # Stadium
    def addStadiumGame(self, user_id, stadium_game):
        overwatch_tracker = self._getOrCreateOwTrackerForUser(user_id)
        rv = overwatch_tracker.addStadiumGame(stadium_game)
        self.saveTrackersToFile()
        return rv

    def getStadiumGamesFromPastDays(self, user_id, num_days=7):
        overwatch_tracker = self._getOrCreateOwTrackerForUser(user_id)
        return overwatch_tracker.getStadiumGamesFromPastDays(num_days=num_days)


# Tracks OW games for a single person
class OverwatchTracker:

    def __init__(self):
        # List of OverwatchGames (regular comp)
        self.games = []
        self.selected_game = None
        
        # Hero usage is just for regular comp
        self.hero_usage = None

        # List of StadiumGames (stadium)
        self.stadium_games = []
        self.selected_stadium_game = None

        # Season is shared between Regular comp + Stadium
        self.season = -1

        # Tracker for weekly goal of number of games.
        self.weekly_tracker = WeeklyTracker()

    # Regular Comp
    def addGame(self, overwatch_game):
        self.games.append(overwatch_game)
        self.selected_game = self.games[-1]
        self._addGameToHeroUsage(self.selected_game)
        if hasattr(self, 'weekly_tracker'):
            self.weekly_tracker.addGame(overwatch_game)
        return self.selected_game

    def addHeroToSelectedGame(self, hero, weight):
        if self.selected_game is None:
            return None
        self._removeGameFromHeroUsage(self.selected_game)
        self.selected_game.heroes.append((getHero(hero), weight))
        self._addGameToHeroUsage(self.selected_game)
        return self.selected_game

    def getGamesFromPastDays(self, num_days=7):
        return self._getRecentGames(self.games, num_days)

    def getRecentGames(self, num_games=10):
        if len(self.games) == 0:
            return []

        if len(self.games) < num_games:
            num_games = len(self.games)

        return self.games[-num_games:]

    def selectGame(self, game_ind):
        if len(self.games) < game_ind:
            return None

        self.selected_game = self.games[-game_ind]
        return self.selected_game

    def updateGame(self, result, map, hero, weight, season):
        if self.selected_game is None:
            return None

        if result is not None:
            self.selected_game.result = result

        if map is not None:
            self.selected_game.map = map

        if hero is not None:
            self._removeGameFromHeroUsage(self.selected_game)
            if hero in HEROES:
                self.selected_game.role = HEROES[hero]
            else:
                self.selected_game.role = 'Invalid hero: ' + hero
            self.selected_game.heroes = [(hero, weight)]
            self._addGameToHeroUsage(self.selected_game)

        if season is not None:
            self.selected_game.season = season

        return self.selected_game

    def getSelectedRole(self):
        if self.selected_game is None:
            return None
        return self.selected_game.role

    # Season
    def updateSeason(self, new_season):
        season_changed = (self.season != new_season)
        self.season = new_season

        # When the season is changed, redo hero usage statistics, since we only care about last two seasons.
        if season_changed:
            self._calculateHeroUsage()
        return season_changed

    # Hero Usage
    # TODO Add a function to check that hero_usage is consistent (Sum should be total games in last k seasons, no values should be negative)
    def getHeroUsage(self):
        if self.hero_usage is None:
            self._calculateHeroUsage()
        return self.hero_usage

    def getHeroUsageByResult(self):
        if self.hero_usage_by_result is None:
            self._calculateHeroUsage()
        return self.hero_usage_by_result

    def _calculateHeroUsage(self):
        self.hero_usage = {}
        self.hero_usage_by_result = {}

        for game in self.games:
            if not hasattr(game, 'season'):
                game.season = 5

            # Only consider games from the current season and previous 2 seasons.
            if self.season - game.season >= 2:
                continue
            self._addGameToHeroUsage(game)

    def _removeGameFromHeroUsage(self, game):
        total_weight = sum(w for _, w in game.heroes)
        for h, w in game.heroes:
            if h in self.hero_usage:
                self.hero_usage[h] -= w / total_weight
                self.hero_usage_by_result[h][game.result] -= w / total_weight

            if self.hero_usage[h] <= 0:
                del self.hero_usage[h]
                del self.hero_usage_by_result[h]

    def _addGameToHeroUsage(self, game):
        total_weight = sum(w for _, w in game.heroes)
        for h, w in game.heroes:
            if h not in self.hero_usage:
                self.hero_usage[h] = 0.0
                self.hero_usage_by_result[h] = {
                    v: 0.0
                    for v in OverwatchGame.RESULTS
                }

            self.hero_usage[h] += w / total_weight
            self.hero_usage_by_result[h][game.result] += w / total_weight

    # Weekly Goal
    def getWeeklyGoal(self):
        if not hasattr(self, 'weekly_tracker'):
            return None
        return self.weekly_tracker.getGoal()

    def setWeeklyGoal(self, new_weekly_goal):
        if not hasattr(self, 'weekly_tracker'):
            self.weekly_tracker = WeeklyTracker()

        self.weekly_tracker.setGoal(new_weekly_goal)

    def getCurrentWeeklyGoalStatus(self):
        if not hasattr(self, 'weekly_tracker'):
            return None, None
        return self.weekly_tracker.getCurrentStatus()

    def advanceWeek(self):
        if not hasattr(self, 'weekly_tracker'):
            return None, None
        return self.weekly_tracker.advanceWeek()

    # Stadium
    def _initStadium(self):
        if not hasattr(self, 'stadium_games'):
            self.stadium_games = []
            self.selected_stadium_game = None

    def addStadiumGame(self, stadium_game):
        self._initStadium()
        self.stadium_games.append(stadium_game)
        self.selected_stadium_game = self.stadium_games[-1]
        # TODO Add stadium games to the weekly tracker
        # if hasattr(self, 'weekly_tracker'):
        #     self.weekly_tracker.addStadiumGame(stadium_game)
        return self.selected_stadium_game

    def getStadiumGamesFromPastDays(self, num_days=7):
        self._initStadium()
        return self._getRecentGames(self.stadium_games, num_days)

    def getRecentStadiumGames(self, num_games=10):
        self._initStadium()
        if len(self.stadium_games) == 0:
            return []

        if len(self.stadium_games) < num_games:
            num_games = len(self.stadium_games)

        return self.stadium_games[-num_games:]

    def selectStadiumGame(self, game_ind):
        self._initStadium()
        if len(self.stadium_games) < game_ind:
            return None

        self.selected_stadium_game = self.stadium_games[-game_ind]
        return self.selected_stadium_game

    def updateStadiumGame(self, result, hero, season, power1, power2, power3, power4):
        if result is not None:
            self.selected_stadium_game.result = result

        if hero is not None:
            self.selected_stadium_game.hero = getHero(hero)

        if season is not None:
            self.selected_stadium_game.season = season

        if power1 is not None and power2 is not None:
            self.selected_stadium_game.power1 = power1
            self.selected_stadium_game.power2 = power2
            self.selected_stadium_game.power3 = power3
            self.selected_stadium_game.power4 = power4

    # Helper functions with code shared between regular comp and stadium
    def _getRecentGames(self, games, num_days):
        # TMP check that games are in sorted order by date.
        prev_date = None
        for game in games:
            if prev_date is not None and game.datetime < prev_date:
                logging.info('Games are not in sorted order by date.')
            prev_date = game.datetime

        rv = []
        tz = pytz.timezone("US/Pacific")
        todays_cutoff = datetime.combine(date_cls.today(), time(hour=6, minute=0),
                                         tz)
        cutoff_day = todays_cutoff - timedelta(
            days=num_days - (1 if datetime.now(tz=tz) >= todays_cutoff else 0))

        logging.info('todays_cutoff: %s, cutoff_day: %s', str(todays_cutoff),
                     str(cutoff_day))
        for game in reversed(games):
            logging.info('game.datetime: %s', str(game.datetime))
            if game.datetime <= cutoff_day:
                break
            rv.append(game)
        return reversed(rv)

class OverwatchGame:
    WIN = 'Win'
    LOSS = 'Loss'
    DRAW = 'Draw'
    RESULTS = [WIN, LOSS, DRAW]

    def __init__(self, result, map, hero, weight, season):
        self.result = result

        self.map = getMap(map)

        hero = getHero(hero)
        self.role = HEROES[hero]

        self.season = season

        # List of two-ples of (hero, weight)
        self.heroes = [(hero, weight)]

        # Date is now deprecated!
        self.date = date_cls.today()
        self.datetime = datetime.now(tz=pytz.timezone('US/Pacific'))
        logging.info('Created game with datetime: %s', str(self.datetime))

    def heroList(self):
        if len(self.heroes) == 0:
            return ''
        if len(self.heroes) == 1:
            return self.heroes[0][0]

        total_weight = sum(weight for _, weight in self.heroes)
        return ', '.join(
            map(
                lambda x: '{}({}%)'.format(x[0],
                                           round(x[1] / total_weight * 100)),
                self.heroes))

    def msgStr(self):
        # TODO format this message better
        return '```\nMap    --> {}\nRole   --> {}\nResult --> {}\nHeroes --> {}\n```'.format(
            self.map, self.role, self.result, self.heroList())


class StadiumGame:
    WIN = 'Win'
    LOSS = 'Loss'
    RESULTS = [WIN, LOSS]

    def __init__(self, result, hero, season, power1, power2, power3, power4, dt):
        self.result = result
        self.hero = getHero(hero)
        self.role = HEROES[self.hero]
        self.season = season
        self.datetime = dt

        self.power1 = power1  # Round 1 power
        self.power2 = power2  # Round 3 power
        self.power3 = power3  # Round 5 power (if None, then game ended before round 5)
        self.power4 = power4  # Round 7 power (if None, then game ended before round 7)

    def msgStr(self):
        power_str = f'{self.power1}, {self.power2}'
        if self.power3 is not None:
            power_str += f', {self.power3}'
            if self.power4 is not None:
                power_str += f', {self.power4}'

        dt_str = self.datetime.strftime('%b %-d %Y, %I:%M %p')

        return f'```\nResult --> {self.result}\nHero --> {self.hero}\nPowers: {power_str}\nSeason: {self.season}\nDateTime: {dt_str}\n```'

        

class WeeklyTracker:
    def __init__(self, goal = None):
        self.current_goal = goal
        self.current_games = []  # TODO Double check that if a game is uppdpated, it is doesn't need to be updated here and in self.previous_weeks
        self.current_start = datetime.now(tz=pytz.timezone("US/Pacific"))

        # 4-tuple of (goal: int, start: datetime, end: datetime, games: list of OverwatchGame)
        self.previous_weeks = []

    def getGoal(self):
        return self.current_goal

    def setGoal(self, new_goal):
        self.current_goal = new_goal

    def addGame(self, game):
        self.current_games.append(game)

    def getCurrentStatus(self):
        return self.current_goal, self.current_games

    def getPreviousWeeks(self):
        return self.previous_weeks

    def advanceWeek(self):
        games = list(self.current_games)

        end = datetime.now(tz=pytz.timezone("US/Pacific"))
        self.previous_weeks.append((self.current_goal, self.current_start, end, games))
        self.current_start = end
        self.current_games.clear()

        return self.current_goal, games

# Hero Challenge Sub-Feature:

class HeroChallengeDiscordCommands(app_commands.Group):
    def __init__(self, hero_challenge_manager, *args, **kwargs):
        super(HeroChallengeDiscordCommands, self).__init__(
            name='hero-challenge', *args, **kwargs)
        self.hero_challenge_manager = hero_challenge_manager

    DATE_REGEX = re.compile(
        r'^(?P<month>\d{1,2})\/(?P<day>\d{1,2})(?:\/(?P<year>\d{2}|\d{4}))?$')

    HERO_CHOICES = [
        app_commands.Choice(name=hero, value=hero)
        for hero, _ in HEROES.items()
    ]

    async def hero_autocomplete(
            self, interaction: discord.Interaction,
            current: str) -> typing.List[app_commands.Choice[str]]:
        hero_choices = [
            v for v in HeroChallengeDiscordCommands.HERO_CHOICES
        ]

        # Get the edit distance between the current string and heroes. Subtract
        # out the difference between the hero name and current string to account
        # for extra characters.
        hero_edit_distance = {
            hero: customEditDistance(hero, current)
            for hero, _ in HEROES.items()
        }

        # The heroes are sorted by (hero edit distance ascending, hero usage descending, hero name ascending)
        hero_choices.sort(key=lambda hero: (hero_edit_distance[hero.value], hero.value))

        if len(hero_choices) > AUTOCOMPLETE_LIMIT:
            hero_choices = hero_choices[:AUTOCOMPLETE_LIMIT]

        return hero_choices

    @app_commands.command(
        name='random-heroes',
        description='Gives some random heroes for the hero challenge.',
    )
    @app_commands.describe(
        num_heroes='The number of heroes to randomly choose. Default is 5.',
        tank='Whether or not to include Tank hereos. Default is True.',
        dps='Whether or not to include DPS hereos. Default is True.',
        support='Whether or not to include Support hereos. Default is True.',
        allow_repeats='Whether or not to include repeat heroes. Default is False.',
    )
    async def random_heroes(self,
                      interaction: discord.Interaction,
                      num_heroes: typing.Optional[int]=5,
                      tank: typing.Optional[bool]=True,
                      dps: typing.Optional[bool]=True,
                      support: typing.Optional[bool]=True,
                      allow_repeats: typing.Optional[bool] = False):
        hero_challenge_tracker = self.hero_challenge_manager.getTrackerForUser(interaction.user.id)
        heroes = hero_challenge_tracker.getRandomSetOfHeroes(
            num_heroes=num_heroes,
            tank=tank,
            dps=dps,
            support=support,
            allow_repeats=allow_repeats,
        )

        msg = ''
        if len(heroes) == 0:
            msg = 'There were no heroes that matched the input params!'
        else:
            msg = 'Choose from one of the following heroes:\n' + \
                  '\n'.join(hero_challenge_tracker.formatHeroForRandomHero(h) for h in heroes)
        await interaction.response.send_message(msg, ephemeral=True)
    
    @app_commands.command(
        name='set-hero',
        description='Updates whether a hero was used in the heoro challenge.',
    )
    @app_commands.describe(
        hero='The name of the hero to update.',
        add_or_remove='Whether or not to add or remove the hero from the given date. Default is to add.',
        date='The date to update in MM/DD/YYYY or MM/DD (year assumed to be current year) format. Default is today (in PT).'
    )
    @app_commands.autocomplete(hero=hero_autocomplete)
    @app_commands.choices(add_or_remove=[
        app_commands.Choice(name='Add', value=1),
        app_commands.Choice(name='Remove', value=0),
    ])
    async def set_hero(self,
            interaction: discord.Interaction,
            hero: str,
            add_or_remove: typing.Optional[int]=1,
            date: typing.Optional[str]=None):
        today = datetime.now(tz=pytz.timezone('US/Pacific')).date()
        if date is None:
            # Use today as default.
            date = today
        else:
            # Otherwise parse date.
            match = HeroChallengeDiscordCommands.DATE_REGEX.match(date)
            if match is None:
                await interaction.response.send_message('Invalid date format!', ephemeral=True)
                return
            month = int(date_match.group('month'))
            day = int(date_match.group('day'))
            year = date_match.group('year')

            if year is not None:
                year = int(year)
                if year < 100:
                    year += 2000
            else:
                year = today.year

            try:
                date = date_cls(year, monthy, day)
            except ValueError:
                await interaction.response.send_message('Invalid date!', ephemeral=True)
                return

        hero_challenge_tracker = self.hero_challenge_manager.getTrackerForUser(interaction.user.id)
        if add_or_remove == 1:
            changed = hero_challenge_tracker.addHeroWithDate(hero, date)
        else:
            changed = hero_challenge_tracker.removeHeroWithDate(hero, date)

        if changed:
            self.hero_challenge_manager.saveTrackersToFile()
            await interaction.response.send_message('Hero challenge tracker sucessfullly updated!', ephemeral=True)
        else:
            await interaction.response.send_message('Error when updating tracker!', ephemeral=True)

    @app_commands.command(
        name='challenge-status',
        description='Prints out the status of the challenge.',
    )
    async def challenge_status(self, interaction: discord.Interaction):
        hero_challenge_tracker = self.hero_challenge_manager.getTrackerForUser(interaction.user.id)

        # Heroes are sorted by (# of repeats (high to low), hero_name (low to high))
        sorted_heroes = sorted([(-len(ds), h) for h, ds in hero_challenge_tracker.heroes_with_date.items()])

        # TODO Use a different formating function.
        msg = 'The status of the hero challenge (sorted from most to least frequently played):\n' + \
              '\n'.join(hero_challenge_tracker.formatHeroForRandomHero(h) for _, h in sorted_heroes)

        # TODO List heroes that have been played by last time they were played.
        # TODO Group all heroes that haven't been played together.
        await interaction.response.send_message(msg, ephemeral=True)

# Tracks the hero challenge for all users.
class HeroChallengeManager:
    def __init__(self, hero_challenge_fname=HERO_CHALLENGE_FILENAME):
        self.hero_challenge_fname = hero_challenge_fname
        self.loadTrackersFromFile()

    def loadTrackersFromFile(self):
        # If file does not exist, then init self.hero_challenge_trackers to empty dict, and save to file (to create it).
        if not os.path.exists(self.hero_challenge_fname):
            self.hero_challenge_trackers = {}
            self.saveTrackersToFile()
            return

        f = open(self.hero_challenge_fname, 'rb')
        self.hero_challenge_trackers = pickle.load(f)

        for _, hct in self.hero_challenge_trackers.items():
            # Adds empty entries for any new heroes that have been added.
            hct.addMissingHeroes()

    def saveTrackersToFile(self):
        f = open(self.hero_challenge_fname, 'wb')
        pickle.dump(self.hero_challenge_trackers, f)


    def getDiscordCommands(self):
        return [HeroChallengeDiscordCommands(self)]

    def getTrackerForUser(self, user_id):
        if user_id not in self.hero_challenge_trackers:
            self.hero_challenge_trackers[user_id] = HeroChallengeTracker()
            self.saveTrackersToFile()
        return self.hero_challenge_trackers[user_id]

# Tracks the hero challenge for a single person
class HeroChallengeTracker:
    def __init__(self):
        # Key is a hero name, value is a list of dates where that hero was played.
        self.heroes_with_date = {}
        self.addMissingHeroes()

    def addMissingHeroes(self):
        for h, _ in HEROES.items():
            if h not in self.heroes_with_date:
                self.heroes_with_date[h] = []

    def addHeroWithDate(self, hero, date):
        if hero not in self.heroes_with_date:
            return False
        self.heroes_with_date[hero].append(date)
        return True
    
    def removeHeroWithDate(self, hero, date):
        if hero not in self.heroes_with_date:
            return False
        if date not in self.heroes_with_date[hero]:
            return False
        self.heroes_with_date[hero].remove(date)
        return True

    def getRandomSetOfHeroes(self,
            num_heroes=5,
            tank=True, dps=True, support=True,
            allow_repeats=False):
        pos_heroes = [
            h for h, r in HEROES.items()
            if ((tank and r == TANK) or (dps and r == DPS) or (support and r == SUPPORT))
            and (allow_repeats or len(self.heroes_with_date[h]) == 0)
        ]
        # TODO Change how the heroes are chosen to take into account roles (i.e. ensure that all roles are represented), repeats (weight each hero by how often they have been chosen in the past), and previous roles (prefer roles based on how recently they were played).
        return random.sample(pos_heroes, min(num_heroes, len(pos_heroes)))

    def formatHeroForRandomHero(self, hero):
        if hero not in self.heroes_with_date:
            return f'- Error with {hero}: not found in heroes_with_date'
        if len(self.heroes_with_date[hero]) == 0:
            return f'- {hero}'
        if len(self.heroes_with_date[hero]) > 0:
            plural = 's' if len(self.heroes_with_date[hero]) >= 2 else ''
            date_list = ', '.join(d.strftime('%x') for d in self.heroes_with_date[hero])
            return f'- {hero} (Played {len(self.heroes_with_date[hero])} time{plural} on {date_list})'
    