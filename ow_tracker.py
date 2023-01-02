import discord
from discord import app_commands
import typing
import os
import os.path
import pickle
from datetime import date, timedelta

MAPS = [
    # Escort
    'Circuit Royal',
    'Dorado',
    'Havana',
    'Junkertown',
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
    'Busan',
    'Ilios',
    'Lijiang Tower',
    'Nepal',
    'Oasis',

    # Push
    'Colosseo',
    'Esperança',
    'New Queen Street',
]
TANK = 'Tank'
DPS = 'DPS'
SUPPORT = 'Support'
ROLES = [TANK, DPS, SUPPORT]
HEROES = [
    # Tanks
    'D.Va',
    'Doomfist',
    'Junker Queen',
    'Orisa',
    'Ramattra',
    'Reinhardt',
    'Roadhog',
    'Sigma',
    'Winston',
    'Wrecking Ball',
    'Zarya',

    # DPS
    'Ashe',
    'Bastion',
    'Cassidy',
    'Echo',
    'Genji',
    'Hanzo',
    'Junkrat',
    'Mei',
    'Pharah',
    'Reaper',
    'Soldier: 76',
    'Sojourn',
    'Sombra',
    'Symmetra',
    'Torbjörn',
    'Tracer',
    'Widowmaker',

    # Support
    'Ana',
    'Baptiste',
    'Brigitte',
    'Kiriko',
    'Lúcio',
    'Mercy',
    'Moira',
    'Zenyatta',
]

OW_TRACKER_FILENAME = 'data/ow_tracker.pickle'


class OwTrackerDiscordCommands(app_commands.Group):
    ROLE_CHOICES = [
        app_commands.Choice(name=role, value=role) for role in ROLES
    ]

    def __init__(self, ow_tracker_manager, *args, **kwargs):
        super(OwTrackerDiscordCommands, self).__init__(name='ow-tracker',
                                                       *args,
                                                       **kwargs)

        self.ow_tracker_manager = ow_tracker_manager

    async def map_autocomplete(
            self, interaction: discord.Interaction,
            current: str) -> typing.List[app_commands.Choice[str]]:
        return [
            app_commands.Choice(name=map, value=map) for map in MAPS
            if current.lower() in map.lower()
        ]

    async def hero_autocomplete(
            self, interaction: discord.Interaction,
            current: str) -> typing.List[app_commands.Choice[str]]:
        return [
            app_commands.Choice(name=hero, value=hero) for hero in HEROES
            if current.lower() in hero.lower()
        ]

    @app_commands.command(name='add-win', description='Record win')
    @app_commands.describe(
        map='Map the game was played on.',
        role='Role played on the map.',
        hero=
        'Main hero played on the map. (Use add-hero to add additional heroes to this game)',
        percent='Percent of the map where this hero was played.')
    @app_commands.choices(role=ROLE_CHOICES)
    @app_commands.autocomplete(map=map_autocomplete, hero=hero_autocomplete)
    async def add_win(self,
                      interaction: discord.Interaction,
                      map: str,
                      role: app_commands.Choice[str],
                      hero: str,
                      percent: typing.Optional[float] = 1.0):
        await self._addGame(
            interaction,
            OverwatchGame(OverwatchGame.WIN, map, role.value, hero, percent))

    @app_commands.command(name='add-loss', description='Record lose')
    @app_commands.describe(
        map='Map the game was played on.',
        role='Role played on the map.',
        hero=
        'Main hero played on the map. (Use add-hero to add additional heroes to this game)',
        percent='Percent of the map where this hero was played.')
    @app_commands.choices(role=ROLE_CHOICES)
    @app_commands.autocomplete(map=map_autocomplete, hero=hero_autocomplete)
    async def add_loss(self,
                       interaction: discord.Interaction,
                       map: str,
                       role: app_commands.Choice[str],
                       hero: str,
                       percent: typing.Optional[float] = 1.0):
        await self._addGame(
            interaction,
            OverwatchGame(OverwatchGame.LOSS, map, role.value, hero, percent))

    @app_commands.command(name='add-draw', description='Record lose')
    @app_commands.describe(
        map='Map the game was played on.',
        role='Role played on the map.',
        hero=
        'Main hero played on the map. (Use add-hero to add additional heroes to this game)',
        percent='Percent of the map where this hero was played.')
    @app_commands.choices(role=ROLE_CHOICES)
    @app_commands.autocomplete(map=map_autocomplete, hero=hero_autocomplete)
    async def add_draw(self,
                       interaction: discord.Interaction,
                       map: str,
                       role: app_commands.Choice[str],
                       hero: str,
                       percent: typing.Optional[float] = 1.0):
        await self._addGame(
            interaction,
            OverwatchGame(OverwatchGame.DRAW, map, role.value, hero, percent))

    async def _addGame(self, interaction, new_game):
        self.ow_tracker_manager.addGame(interaction.user.id, new_game)
        message = 'Game added.\n' + self._getRecentResultMessage(
            interaction.user.id, 7)

        await interaction.response.send_message(message, ephemeral=True)

    def _getRecentResultMessage(self, user_id, num_days):
        recent_games = self.ow_tracker_manager.getRecentGames(
            user_id, num_days=num_days)

        total_games = len(recent_games)
        if total_games <= 0:
            message = 'No games within the last {} day(s).'.format(num_days)
        else:
            overall_result = {result: 0 for result in OverwatchGame.RESULTS}
            result_by_role = {(role, result): 0
                              for role in ROLES
                              for result in OverwatchGame.RESULTS}
            for game in recent_games:
                overall_result[game.result] += 1
                result_by_role[(game.role, game.result)] += 1
            message = 'Results (W-L-D) from the last {} day(s):\n```\n'.format(
                num_days)

            # Overall
            message += 'Total -> {}-{}-{}\n'.format(
                overall_result[OverwatchGame.WIN],
                overall_result[OverwatchGame.LOSS],
                overall_result[OverwatchGame.DRAW])
            message += 'Tank  -> {}-{}-{}\n'.format(
                result_by_role[(TANK, OverwatchGame.WIN)],
                result_by_role[(TANK, OverwatchGame.LOSS)],
                result_by_role[(TANK, OverwatchGame.DRAW)])
            message += 'DPS   -> {}-{}-{}\n'.format(
                result_by_role[(DPS, OverwatchGame.WIN)],
                result_by_role[(DPS, OverwatchGame.LOSS)],
                result_by_role[(DPS, OverwatchGame.DRAW)])
            message += 'Supp  -> {}-{}-{}\n'.format(
                result_by_role[(SUPPORT, OverwatchGame.WIN)],
                result_by_role[(SUPPORT, OverwatchGame.LOSS)],
                result_by_role[(SUPPORT, OverwatchGame.DRAW)])
            message += '```'

        # Progress towards weekly goal?
        return message

    @app_commands.command(name='add-hero',
                          description='Add extra hero info to latest game')
    @app_commands.describe(
        hero='Additional hero played on the map.',
        percent='Percent of the map where this hero was played.')
    @app_commands.autocomplete(hero=hero_autocomplete)
    async def add_hero(self, interaction: discord.Interaction, hero: str,
                       percent: float):
        result = self.ow_tracker_manager.addHeroToLatestGame(
            interaction.user.id, hero, percent)
        message = ''
        if result:
            message = 'Hero successful appending to last game'
        else:
            message = 'Unable able to add hero to last game'
        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(name='recent-results',
                          description='Stats on recent results.')
    @app_commands.describe(
        num_days='Numbr of days since today (inclusive) to get stats for.')
    async def recent_results(self, interaction: discord.Interaction,
                             num_days: int):
        if num_days < 1:
            num_days = 1
        message = self._getRecentResultMessage(interaction.user.id, num_days)
        await interaction.response.send_message(message, ephemeral=True)

    # TODO Add commands/support for
    #    Weekly goals
    #    Progress towards rank updates
    #    Look at arbirtary range of dates
    #    Look at stats per hero/map/mode
    #    Look at stats per season


class OverwatchTrackerManager:

    def __init__(self, ow_tracker_fname=OW_TRACKER_FILENAME):
        self.ow_tracker_fname = ow_tracker_fname
        self.loadTrackersFromFile()

    def getDiscordCommands(self):
        return [OwTrackerDiscordCommands(self)]

    # TODO make this async
    def loadTrackersFromFile(self):
        # If file does not exist, then init self.twitch_streams to empty dict
        if not os.path.exists(self.ow_tracker_fname):
            self.overwatch_trackers = {}
            self.saveTrackersToFile()
            return

        f = open(self.ow_tracker_fname, 'rb')
        self.overwatch_trackers = pickle.load(f)

    # TODO make this async
    def saveTrackersToFile(self):
        f = open(self.ow_tracker_fname, 'wb')
        pickle.dump(self.overwatch_trackers, f)

    def addGame(self, user_id, overwatch_game):
        overwatch_tracker = self._getOrCreateOwTrackerForUser(user_id)
        overwatch_tracker.games.append(overwatch_game)
        self.saveTrackersToFile()

    def addHeroToLatestGame(self, user_id, hero, weight):
        overwatch_tracker = self._getOrCreateOwTrackerForUser(user_id)
        result = overwatch_tracker.addHeroToLatestGame(hero, weight)
        if result:
            self.saveTrackersToFile()
        return result

    def getRecentGames(self, user_id, num_days=7):
        overwatch_tracker = self._getOrCreateOwTrackerForUser(user_id)
        return overwatch_tracker.getGamesFromPastDays(num_days=num_days)

    def _getOrCreateOwTrackerForUser(self, user_id):
        if user_id not in self.overwatch_trackers:
            self.overwatch_trackers[user_id] = OverwatchTracker()
        return self.overwatch_trackers[user_id]


# Tracks OW games for a single person
class OverwatchTracker:

    def __init__(self):
        # List of OverwatchGames
        self.games = []

    def addHeroToLatestGame(self, hero, weight):
        if len(self.games) <= 0:
            return False
        self.games[-1].heroes.append((hero, weight))
        return True

    # TODO This may be inefficient
    def getGamesFromPastDays(self, num_days=7):
        return [
            game for game in self.games
            if game.date > date.today() - timedelta(days=num_days)
        ]


class OverwatchGame:
    WIN = 'Win'
    LOSS = 'Loss'
    DRAW = 'Draw'
    RESULTS = [WIN, LOSS, DRAW]

    def __init__(self, result, map, role, hero, weight):
        self.result = result
        self.map = map
        self.role = role

        # TODO Have a way to update this as time passes
        self.season = 2

        # List of two-ples of (hero, weight)
        self.heroes = [(hero, weight)]

        self.date = date.today()
