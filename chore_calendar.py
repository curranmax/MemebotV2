import event_calendar as EC

import asyncio
import discord
from discord import app_commands
from datetime import date, datetime, time, timedelta
import pytz
import calendar

DAILY = 'Daily'
WEEKLY = 'Weekly'
MONTHLY = 'Monthly'

ALL_FREQUENCIES = [DAILY, WEEKLY, MONTHLY]


# TODO split this off into its own bot.
class ChoreCalendarDiscordCommands(app_commands.Group):

    def __init__(self, chore_calendar, *args, **kwargs):
        super(ChoreCalendarDiscordCommands,
              self).__init__(name='chore-calendar', *args, **kwargs)

        self.chore_calendar = chore_calendar

    # Add a chore (with a name/description, emote, when should it happen (weekly/monthly, day of the week/day of the month))
    # Maybe separate monthly/weekly commands
    # Change the time the daily post occurs
    # Debug/print command

    @app_commands.context_menu(name='test')
    async def test(interaction: discord.Interaction, message: discord.Message):
        await interaction.response.send_message('Chore added!', ephemeral=True)

    @app_commands.command(
        name='add-daily-chore',
        description='Adds a new chore that must be done every day.')
    @app_commands.describe(
        name='Name of the chore.', )
    async def add_daily_chore(self, interaction: discord.Interaction,
                              name: str):
        chore_frequency = DailyFrequency()
        await self._addChore(interaction, name, chore_frequency)

    @app_commands.command(
        name='add-weekly-chore',
        description='Adds a new chore that must be done every week.')
    @app_commands.describe(
        name='Name of the chore.',
        day_of_the_week='Day of the week the chore needs to be done.')
    @app_commands.choices(day_of_the_week=[
        app_commands.Choice(name='Monday', value=0),
        app_commands.Choice(name='Tuesday', value=1),
        app_commands.Choice(name='Wednesday', value=2),
        app_commands.Choice(name='Thursday', value=3),
        app_commands.Choice(name='Friday', value=4),
        app_commands.Choice(name='Saturday', value=5),
        app_commands.Choice(name='Sunday', value=6),
    ])
    async def add_weekly_chore(self, interaction: discord.Interaction,
                               name: str,
                               day_of_the_week: app_commands.Choice[int]):
        chore_frequency = WeeklyFrequency(day_of_the_week.value, 0)
        await self._addChore(interaction, name, chore_frequency)

    @app_commands.command(
        name='add-monthly-chore',
        description='Adds a new chore that must be done every week.')
    @app_commands.describe(
        name='Name of the chore.',
        day_of_the_month='Day of the week the chore needs to be done.')
    async def add_monthly_chore(self, interaction: discord.Interaction,
                                name: str, day_of_the_month: int):
        if day_of_the_month < 1 or day_of_the_month > 31:
            await interaction.response.send_message(
                'Invalid day of the month!', ephemeral=True)
            return
        chore_frequency = MonthlyFrequency(day_of_the_month, 0)
        await self._addChore(interaction, name, chore_frequency)

    async def _addChore(self, interaction, name, chore_frequency):
        result = await self.chore_calendar.addChore(
            Chore(name, chore_frequency))
        if result:
            await interaction.response.send_message('Chore added!',
                                                    ephemeral=True)
        else:
            await interaction.response.send_message('Error adding chore!',
                                                    ephemeral=True)

    @app_commands.command(
        name='bind',
        description=
        'Binds the calendar to this channel, so updates will be posted there')
    async def bind(self, interaction: discord.Interaction):
        self.chore_calendar.setChannel(interaction.channel_id)

        await interaction.response.send_message('Done', ephemeral=True)

    @app_commands.command(name='debug', description='Triggers the daily post')
    async def debug(self, interaction: discord.Interaction):
        await self.chore_calendar.postDailyUpdate(
            schedule_new_post=False, channel=interaction.channel_id)

        await interaction.response.send_message('Done', ephemeral=True)


class ChoreFrequency:

    def __init__(self, frequency):
        self.frequency = frequency


class DailyFrequency(ChoreFrequency):

    def __init__(self):
        super(DailyFrequency, self, DAILY)


class WeeklyFrequency(ChoreFrequency):

    def __init__(self, day_of_the_week, offset):
        super(WeeklyFrequency, self, WEEKLY)

        self.day_of_the_week = self.day_of_the_week
        self.offset = offset


class MonthlyFrequency(ChoreFrequency):

    def __init__(self, day_of_the_month, offset):
        super(MonthlyFrequency, self, MONTHLY)

        self.day_of_the_month = day_of_the_month
        self.offset = offset


class Chore:

    def __init__(self, name, chore_frequency):
        self.name = name

        self.chore_frequency = chore_frequency

        self.last_post = None

    def shouldPost(self, date):
        if self.chore_frequency.frequency == DAILY:
            return True

        if self.chore_frequency.frequency == WEEKLY:
            # TODO account for offset
            return self.chore_frequency.day_of_the_week == date.weekday()

        if self.chore_frequency.frequency == MONTHLY:
            # TODO account for offset
            clamped_day_of_the_month = min(
                self.chore_frequency.day_of_the_month,
                calendar.monthrange(date.year, date.month)[1])
            return clamped_day_of_the_month == date.day

    def getMessageLine(self):
        # TODO Add a react for the calendar
        return str(self.name)


class ChoreCalendar:

    def __init__(self, discord_client, event_calendar):
        self.discord_client = discord_client
        self.event_calendar = event_calendar

        # TODO change this to two mapss with keys of name and react.
        self.chores = []
        self.chores_lock = asyncio.Lock()

        self.post_time = time(hour=8, tzinfo=pytz.timezone('US/Pacific'))
        self.channel = None

        self.event_calendar.addEvent(
            EC.Event(self.getPostTimeForTomorrow(), self.postDailyUpdate))

    def getDiscordCommands(self):
        return [ChoreCalendarDiscordCommands(self)]

    def setChannel(self, new_channel):
        self.channel = new_channel

    async def addChore(self, new_chore):
        async with self.chores_lock:
            for existing_chore in self.chores:
                if existing_chore.name == new_chore.name:
                    return False

            self.chores.append(new_chore)

        # TODO save chores to file
        return True

    async def postDailyUpdate(self, schedule_new_post=True, channel=None):
        if channel is None:
            channel = self.channel

        message = await self.getChoreMessage()

        await self.discord_client.get_channel(channel).send(message)

        if schedule_new_post:
            await self.schedulePostForTomorrow()

    async def getChoreMessage(self):
        async with self.chores_lock:
            chores_for_today = []
            today = date.today()
            for chore in self.chores:
                if chore.shouldPost(today):
                    chores_for_today.append(chore)

            if len(chores_for_today) == 0:
                return 'No chores for today!'

            for chore in chores_for_today:
                chore.last_post = today

            return 'The chores for today are:\n' + '\n'.join(
                chore.getMessageLine() for chore in chores_for_today)

    def getPostTimeForTomorrow(self):
        return datetime.combine(date.today() + timedelta(days=1),
                                self.post_time)

    async def schedulePostForTomorrow(self):
        await self.event_calendar.addEventWithLock(
            EC.Event(self.getPostTimeForTomorrow(), self.postDailyUpdate))
