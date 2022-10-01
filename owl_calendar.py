import discord
from discord import app_commands


class OwlTeam:

    def __init__(self, abbreviation, short_name, full_name, emote=None):
        self.abbreviation = abbreviation
        self.short_name = short_name
        self.full_name = full_name
        self.emote = emote

    def getChoiceName(self):
        return self.short_name


# This is useful playoff games where the team isn't known
class TbdTeam:

    def getChoiceName(self):
        return 'TBD'


OWL_TEAMS = [
    OwlTeam('ATL', 'Atlanta', 'Atlanta Reign'),
    OwlTeam('BOS', 'Boston', 'Boston Uprising', emote='🆙'),
    OwlTeam('CHD', 'Chengdu', 'Chengdu Hunters', emote='🐼'),
    OwlTeam('DAL', 'Dallas', 'Dallas Fuel', emote='🔥'),
    OwlTeam('FLA', 'Florida', 'Florida Mayhem', emote='💣'),
    OwlTeam('GZC', 'Guangzhou', 'Guangzhou Charge', emote='🔋'),
    OwlTeam('HZS', 'Hangzhou', 'Hangzhou Spark', emote='✨'),
    OwlTeam('HOU', 'Houston', 'Houston Outlaws', emote='🤠'),
    OwlTeam('LDN', 'London', 'London Spitfire', emote='🛩️'),
    OwlTeam('LAG', 'LA Sadiators', 'Los Angeles Gladiators', emote='🦁'),
    OwlTeam('LAV', 'LA Valiant', 'Los Angeles Valiant'),
    OwlTeam('NYE', 'NYXL', 'New York Excelsior', emote='🗽'),
    OwlTeam('PAR', 'Paris', 'Paris Eternal', emote='🐓'),
    OwlTeam('PHI', 'Philly', 'Philadelphia Fusion', emote='⚛️'),
    OwlTeam('SFS', 'San Francisco', 'San Francisco Shock', emote='🌉'),
    OwlTeam('SEO', 'Seoul', 'Seoul Dynasty', emote='🐯'),
    OwlTeam('SHD', 'Shanghai', 'Shanghai Dragons', emote='🐉'),
    OwlTeam('TOR', 'Toronto', 'Toronto Defiant', emote='🇩'),
    OwlTeam('VAN', 'Vancouver', 'Vancouver Titans'),
    OwlTeam('WAS', 'Washington', 'Washington Justice', emote='🇺🇸'),
    TbdTeam()
]


class OwlDiscordCommandsBase(app_commands.Group):
    OWL_TEAM_CHOICES = [
        app_commands.Choice(name=owl_team.getChoiceName(), value=i)
        for i, owl_team in enumerate(OWL_TEAMS)
    ]

    MONTH_CHOICES = [
        app_commands.Choice(name=month, value=i + 1)
        for i, month in enumerate(('January', 'February', 'March', 'April',
                                   'May', 'June', 'July', 'August',
                                   'September', 'October', 'November',
                                   'December'))
    ]

    def __init__(self, owl_calendar_manager, name, *args, **kwargs):
        super(OwlDiscordCommandsBase, self).__init__(name=name,
                                                     *args,
                                                     **kwargs)
        self.owl_calendar_manager = owl_calendar_manager


class OwlDiscordCommands(OwlDiscordCommandsBase):

    def __init__(self, owl_calendar_manager, *args, **kwargs):
        super(OwlDiscordCommands, self).__init__(owl_calendar_manager, 'owl',
                                                 *args, **kwargs)

    @app_commands.command(name='test', description='Test!')
    async def test(self, interaction: discord.Interaction):
        await interaction.response.send_message('Test!', ephemeral=True)


class OwlAdminDiscordCommands(OwlDiscordCommandsBase):

    def __init__(self, owl_calendar_manager, *args, **kwargs):
        super(OwlAdminDiscordCommands,
              self).__init__(owl_calendar_manager, 'owl-admin', *args,
                             **kwargs)

    @app_commands.command(name='add-game', description='Better test!')
    @app_commands.describe(team1='OWL Team playing in this match',
                           team2='OWL Team playing in this match',
                           month='Month when the game takes place',
                           day='Day of the month when the game takes place')
    @app_commands.choices(team1=OwlDiscordCommandsBase.OWL_TEAM_CHOICES,
                          team2=OwlDiscordCommandsBase.OWL_TEAM_CHOICES,
                          month=OwlDiscordCommandsBase.MONTH_CHOICES)
    async def add_game(self, interaction: discord.Interaction,
                       team1: app_commands.Choice[int],
                       team2: app_commands.Choice[int],
                       month: app_commands.Choice[int],
                       day: app_commands.Range[int, 1, 31]):
        # TODO Check that month/day is valid
        # TODO Maybe add an optional year input. If none set then just assume it will be the next occurence of that date.
        # TODO Add an optional title so that things like "Grand Finals" can be added to a game.
        
        owl_team1 = OWL_TEAMS[team1.value]
        owl_team2 = OWL_TEAMS[team2.value]
        message = '{} vs. {} on {}/{}'.format(owl_team1.getChoiceName(),
                                              owl_team2.getChoiceName(), month.value,
                                              day)

        await interaction.response.send_message(message, ephemeral=True)


class OwlCalendarManager:

    def __init__(self):
        pass

    def getDiscordCommands(self):
        return [OwlDiscordCommands(self), OwlAdminDiscordCommands(self)]
