import discord
from discord import app_commands
import typing
import os
import os.path
import pickle
from datetime import date, timedelta
import logging

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
    'Lifeweaver': SUPPORT,
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
            interaction, OverwatchGame(OverwatchGame.WIN, map, hero, percent))

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
            interaction, OverwatchGame(OverwatchGame.LOSS, map, hero, percent))

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
            interaction, OverwatchGame(OverwatchGame.DRAW, map, hero, percent))

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

        # Progress towards weekly goal?
        return '\n'.join(['```', header, '-' * (len(header) + 1)] + lines +
                         ['```'])

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
        hero=
        'Main hero played on the map. (Use add-hero to add additional heroes to this game)',
        percent='Percent of the map where this hero was played.')
    @app_commands.autocomplete(map=map_autocomplete, hero=hero_autocomplete)
    async def update_game(
            self,
            interaction: discord.Interaction,
            result: typing.Optional[app_commands.Choice[str]] = None,
            map: typing.Optional[str] = None,
            hero: typing.Optional[str] = None,
            percent: typing.Optional[float] = 1.0):
        if result is not None:
            result = result.value

        updated_game = self.ow_tracker_manager.updateGame(
            interaction.user.id, result, map, hero, percent)

        if updated_game is None:
            message = 'Unable to update game.'
        else:
            message = 'Game updated to:\n' + updated_game.msgStr()

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

    def updateGame(self, user_id, result, map, hero, weight):
        overwatch_tracker = self._getOrCreateOwTrackerForUser(user_id)
        updated_game = overwatch_tracker.updateGame(result, map, hero, weight)
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

    def getGamesFromPastDays(self, num_days=7):
        # TMP check that games are in sorted order by date.
        prev_date = None
        for game in self.games:
            if prev_date is not None and game.date < prev_date:
                logging.info('Games are not in sorted order by date.')

        rv = []
        cutoff_day = date.today() - timedelta(days=num_days)
        for game in reversed(self.games):
            if game.date <= cutoff_day:
                break
            rv.append(game)
        return reversed(rv)

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

    def updateGame(self, result, map, hero, weight):
        if self.selected_game is None:
            return None

        if result is not None:
            self.selected_game.result = result

        if map is not None:
            self.selected_game.map = map

        if hero is not None:
            if hero in HEROES:
                self.selected_game.role = HEROES[hero]
            else:
                self.selected_game.role = 'Invalid hero: ' + hero
            self.selected_game.heroes = [(hero, weight)]

        return self.selected_game


class OverwatchGame:
    WIN = 'Win'
    LOSS = 'Loss'
    DRAW = 'Draw'
    RESULTS = [WIN, LOSS, DRAW]

    def __init__(self, result, map, hero, weight):
        self.result = result
        self.map = map
        if hero in HEROES:
            self.role = HEROES[hero]
        else:
            self.role = 'Invalid hero: ' + hero

        # TODO Have a way to update this as time passes
        self.season = 4

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
