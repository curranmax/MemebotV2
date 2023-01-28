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
HEROES = {
    # Tanks
    'D.Va': TANK,
    'Doomfist': TANK,
    'Junker Queen': TANK,
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
    'Widowmaker': DPS,

    # Support
    'Ana': SUPPORT,
    'Baptiste': SUPPORT,
    'Brigitte': SUPPORT,
    'Kiriko': SUPPORT,
    'Lúcio': SUPPORT,
    'Mercy': SUPPORT,
    'Moira': SUPPORT,
    'Zenyatta': SUPPORT,
}

OW_TRACKER_FILENAME = 'data/ow_tracker.pickle'


class OwTrackerDiscordCommands(app_commands.Group):
    RESULT_CHOICES = [
        app_commands.Choice(name=result, value=result)
        for result in ['Win', 'Loss', 'Draw']
    ]

    # TODO Auto detect role based
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
            app_commands.Choice(name=hero, value=hero)
            for hero, _ in HEROES.items()
            if current.lower() in hero.lower() or (
                hero == 'Lúcio' and current.lower() in 'lucio')
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
        latest_game = self.ow_tracker_manager.addGame(interaction.user.id,
                                                      new_game)
        message = 'Game added.\n' + self._getRecentResultMessage(
            interaction.user.id, 7) + '\n\n' + latest_game.msgStr()

        await interaction.response.send_message(message, ephemeral=True)

    def _getRecentResultMessage(self, user_id, num_days):
        recent_games = self.ow_tracker_manager.getGamesFromPastDays(
            user_id, num_days=num_days)

        if len(recent_games) <= 0:
            message = 'No games within the last {} day(s).'.format(num_days)
        else:
            message = 'Results (W-L-D) from the last {} day(s):\n'.format(
                num_days) + self._getSummaryMessage(recent_games)

        # Progress towards weekly goal?
        return message

    def _getSummaryMessage(self, games):
        overall_result = {result: 0 for result in OverwatchGame.RESULTS}
        result_by_role = {(role, result): 0
                          for role in ROLES
                          for result in OverwatchGame.RESULTS}
        for game in games:
            overall_result[game.result] += 1
            result_by_role[(game.role, game.result)] += 1
        message = '```\n'

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

        return message

    @app_commands.command(name='add-hero',
                          description='Add extra hero info to latest game')
    @app_commands.describe(
        hero='Additional hero played on the map.',
        percent='Percent of the map where this hero was played.')
    @app_commands.autocomplete(hero=hero_autocomplete)
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
        role='Role played on the map.',
        hero=
        'Main hero played on the map. (Use add-hero to add additional heroes to this game)',
        percent='Percent of the map where this hero was played.')
    @app_commands.choices(result=RESULT_CHOICES, role=ROLE_CHOICES)
    @app_commands.autocomplete(map=map_autocomplete, hero=hero_autocomplete)
    async def update_game(
            self,
            interaction: discord.Interaction,
            result: typing.Optional[app_commands.Choice[str]] = None,
            map: typing.Optional[str] = None,
            role: typing.Optional[app_commands.Choice[str]] = None,
            hero: typing.Optional[str] = None,
            percent: typing.Optional[float] = 1.0):
        if result is not None:
            result = result.value
        if role is not None:
            role = role.value

        updated_game = self.ow_tracker_manager.updateGame(
            interaction.user.id, result, map, role, hero, percent)

        if updated_game is None:
            message = 'Unable to update game.'
        else:
            message = 'Game updated to:\n' + updated_game.msgStr()

        await interaction.response.send_message(message, ephemeral=True)

    # List games from a certain day --> Include an "id"
    # Completely update the selected game

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

    def updateGame(self, user_id, result, map, role, hero, weight):
        overwatch_tracker = self._getOrCreateOwTrackerForUser(user_id)
        updated_game = overwatch_tracker.updateGame(result, map, role, hero,
                                                    weight)
        if updated_game is not None:
            self.saveTrackersToFile
        return updated_game

    def _getOrCreateOwTrackerForUser(self, user_id):
        if user_id not in self.overwatch_trackers:
            self.overwatch_trackers[user_id] = OverwatchTracker()
        return self.overwatch_trackers[user_id]


# Tracks OW games for a single person
class OverwatchTracker:

    def __init__(self):
        # List of OverwatchGames
        self.games = []

        self.selected_game = None

    def addGame(self, overwatch_game):
        self.games.append(overwatch_game)
        self.selected_game = self.games[-1]
        return self.selected_game

    def addHeroToSelectedGame(self, hero, weight):
        if self.selected_game is None:
            return None
        self.selected_game.heroes.append((hero, weight))
        return self.selected_game

    # TODO This may be inefficient
    def getGamesFromPastDays(self, num_days=7):
        return [
            game for game in self.games
            if game.date > date.today() - timedelta(days=num_days)
        ]

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

    def updateGame(self, result, map, role, hero, weight):
        if self.selected_game is None:
            return None

        if result is not None:
            self.selected_game.result = result

        if map is not None:
            self.selected_game.map = map

        if role is not None:
            self.selected_game.role = role

        if hero is not None:
            self.selected_game.heroes = [(hero, weight)]

        return self.selected_game


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
