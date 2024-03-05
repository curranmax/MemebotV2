import event_calendar as EC

import asyncio
import discord
from discord import app_commands
from datetime import date, datetime, time, timedelta
import pytz
import calendar
import os.path
import pickle
import typing
import re

ONE_TIME = 'One-Time'
DAILY = 'Daily'
WEEKLY = 'Weekly'
MONTHLY = 'Monthly'

ALL_FREQUENCIES = [ONE_TIME, DAILY, WEEKLY, MONTHLY]

CHORE_CHANNEL_FILENAME = 'data/chore_channel.pickle'
CHORES_FILENAME = 'data/chores.pickle'


# TODO split this off into its own bot.
class ChoreCalendarDiscordCommands(app_commands.Group):

    DATE_REGEX = re.compile(
        r'^(?P<month>\d{1,2})\/(?P<day>\d{1,2})(?:\/(?P<year>\d{2}|\d{4}))?$')

    def __init__(self, chore_calendar, *args, **kwargs):
        super(ChoreCalendarDiscordCommands,
              self).__init__(name='chore-calendar', *args, **kwargs)

        self.chore_calendar = chore_calendar

    # Debug/print command
    # delete-chore

    @app_commands.command(name='add-chore', description='Adds a new chore')
    @app_commands.describe(
        name='The name of the chore.',
        emote='The emote for the chore.',
        first_date=
        'The date for the chore to start. Format is MM/DD/YYYY. Year is optional, and if not given, the next occurence of that date is used. Cannot specify a chore to start today or earlier.',
        frequency='How often the chore repeates, if at all.',
        offset=
        'How frequently the chore should be done. Ex. a value of 2 means the chore will be done once every 2 days/weeks/months',
    )
    @app_commands.choices(frequency=[
        app_commands.Choice(name=v, value=v) for v in ALL_FREQUENCIES
    ])
    async def add_chore(self,
                        interaction: discord.Interaction,
                        name: str,
                        emote: str,
                        first_date: str,
                        frequency: app_commands.Choice[str],
                        offset: typing.Optional[int] = 1):

        # If the emote is a custom emote, check that the bot can use it.
        if emote.startswith('<:'):
            # Get the emote ID.
            emote_id = int(emote[2:-1].split(':')[1])

            # Create a Discord emote object.
            # TODO Move this to a helper function instead of getting emojis indirectly.
            emote_obj = discord.utils.get(
                self.chore_calendar.discord_client.emojis, id=emote_id)

            if emote_obj is None:
                await interaction.response.send_message(
                    'Invalid emote, the bot does not have access to it!',
                    ephemeral=True)
                return

        # Get the date from first_date.
        date_match = ChoreCalendarDiscordCommands.DATE_REGEX.match(first_date)
        if date_match is None:
            await interaction.response.send_message(
                'Invalid date format, must be either MM/DD or MM/DD/YYYY!',
                ephemeral=True)
            return

        month = int(date_match.group('month'))
        day = int(date_match.group('day'))
        year = date_match.group('year')

        start_date = None
        today = datetime.now(pytz.timezone('US/Pacific')).date()
        if year is not None:
            year = int(year)
            if year < 100:
                year += 2000
            try:
                start_date = date(year, month, day)
            except ValueError:
                await interaction.response.send_message('Invalid date!',
                                                        ephemeral=True)
                return
        else:
            year = today.year

            try:
                start_date = date(year, month, day)
            except ValueError:
                await interaction.response.send_message('Invalid date!',
                                                        ephemeral=True)
                return

            if start_date <= today:
                start_date.replace(year=year + 1)

        if start_date <= today:
            await interaction.response.send_message(
                'Date must be in the future!', ephemeral=True)
            return

        # Determine the frequency.
        chore_frequency = None
        if frequency.value == ONE_TIME:
            chore_frequency = OneTimeFrequency()
        if frequency.value == DAILY:
            chore_frequency = DailyFrequency(offset)
        if frequency.value == WEEKLY:
            # Monday is 0, and Sunday is 6
            chore_frequency = WeeklyFrequency(start_date.weekday(), offset)
        if frequency.value == MONTHLY:
            chore_frequency = MonthlyFrequency(start_date.day, offset)

        if chore_frequency is None:
            await interaction.response.send_message('Invalid chore frequency!',
                                                    ephemeral=True)
            return

        result = await self.chore_calendar.addChore(
            Chore(name, emote, start_date, chore_frequency))
        if result:
            await interaction.response.send_message('Chore added!',
                                                    ephemeral=True)
        else:
            await interaction.response.send_message('Error adding chore!',
                                                    ephemeral=True)

    # TODO add a remove-chore command.

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

    def __init__(self, frequency, offset):
        self.frequency = frequency

        # A value of 1 means that the chore triggers every day/week/month.
        # A value of 2 means that the chore triggers every other day/week/month.
        # A value of 3 means that the chore triggers every third day/week/month.
        # etc.
        self.offset = offset


class OneTimeFrequency(ChoreFrequency):

    def __init__(self):
        super(OneTimeFrequency, self).__init__(ONE_TIME, 1)

    def __eq__(self, other):
        if not isinstance(other, OneTimeFrequency):
            return False
        return True


class DailyFrequency(ChoreFrequency):

    def __init__(self, offset):
        super(DailyFrequency, self).__init__(DAILY, offset)

    def __eq__(self, other):
        if not isinstance(other, DailyFrequency):
            return False
        return self.offset == other.offset


class WeeklyFrequency(ChoreFrequency):

    # day_of_the_week: Monday is zero, and Sunday is 6.
    def __init__(self, day_of_the_week, offset):
        super(WeeklyFrequency, self).__init__(WEEKLY, offset)

        self.day_of_the_week = day_of_the_week

    def __eq__(self, other):
        if not isinstance(other, WeeklyFrequency):
            return False
        return self.day_of_the_week == other.day_of_the_week and self.offset == other.offset


class MonthlyFrequency(ChoreFrequency):

    def __init__(self, day_of_the_month, offset):
        super(MonthlyFrequency, self).__init__(MONTHLY, offset)

        self.day_of_the_month = day_of_the_month

    def __eq__(self, other):
        if not isinstance(other, MonthlyFrequency):
            return False
        return self.day_of_the_month == other.day_of_the_month and self.offset == other.offset


# One time event


class Chore:

    def __init__(self, name, emote, start_date, chore_frequency):
        self.name = name
        self.emote = emote

        self.chore_frequency = chore_frequency

        self.start_date = start_date
        self.last_post = None

    def shouldPost(self, date):
        if self.chore_frequency.frequency == ONE_TIME:
            # Handle one-time chores.
            return date == self.start_date

        if self.chore_frequency.frequency == DAILY:
            if self.last_post is None:
                # First post should be on start_date
                return date >= self.start_date
            else:
                # After that it should happen every K days.
                return (date -
                        self.last_post).days >= self.chore_frequency.offset

        if self.chore_frequency.frequency == WEEKLY:
            # Needs to be on the correct day of the week.
            if self.chore_frequency.day_of_the_week != date.weekday():
                return False

            if self.last_post is None:
                # First post should be on start_date
                return date >= self.start_date
            else:
                # After that it should happen every K weeks.
                return (date -
                        self.last_post).days >= self.chore_frequency.offset * 7

        if self.chore_frequency.frequency == MONTHLY:
            # Needs to be on the correct day of the week.
            clamped_day_of_the_month = min(
                self.chore_frequency.day_of_the_month,
                calendar.monthrange(date.year, date.month)[1])
            if clamped_day_of_the_month != date.day:
                return False

            if self.last_post is None:
                # First post should be on start_date
                return date >= self.start_date
            else:
                month_difference = (date.year - self.last_post.year
                                    ) * 12 + date.month - self.last_post.month
                return month_difference >= self.chore_frequency.offset

    def getMessageLine(self):
        return '\t{} ---> {}'.format(str(self.emote), str(self.name))

    def __eq__(self, other):
        if not isinstance(other, Chore):
            return False
        return self.name == other.name and self.chore_frequency == other.chore_frequency


class ChoreCalendar:

    def __init__(self, discord_client, event_calendar):
        self.discord_client = discord_client
        self.event_calendar = event_calendar

        # The saved chores
        self.chores = {}  # Key is Chore.emote, and value is Chore
        self.chores_lock = asyncio.Lock()
        self.chores_filename = CHORES_FILENAME
        self._loadChores()

        # Details about when and where to post
        self.post_time = time(hour=8, tzinfo=pytz.timezone('US/Pacific'))
        self.channel = None
        self.chore_channel_filename = CHORE_CHANNEL_FILENAME
        self._loadChannel()

        # Outstanding chores, and the message to watch for reacts.
        self.outstanding_chores = {}  # Key is Chore.emote, and value is Chore
        self.monitor_message = None

        self.event_calendar.addEvent(
            EC.Event(self.getPostTimeForTomorrow(), self.postDailyUpdate))

    def getDiscordCommands(self):
        return [ChoreCalendarDiscordCommands(self)]

    def _loadChannel(self):
        if not os.path.exists(self.chore_channel_filename):
            self._saveChannel()
            return

        f = open(self.chore_channel_filename, 'rb')
        self.channel = pickle.load(f)
        f.close()

    def _saveChannel(self):
        f = open(self.chore_channel_filename, 'wb')
        pickle.dump(self.channel, f)
        f.close()

    def setChannel(self, new_channel):
        self.channel = new_channel
        self._saveChannel()

    def _loadChores(self):
        if not os.path.exists(self.chores_filename):
            asyncio.run(self._saveChores())
            return

        f = open(self.chores_filename, 'rb')
        loaded_chores = pickle.load(f)
        f.close()

        # Update the chores in case there are any compatibility issues (i.e. add any new fields to old data).

        for _, chore in loaded_chores.items():
            # TODO Skip saving for this case?
            asyncio.run(self.addChore(chore, skip_save=True))

    async def _saveChores(self):
        async with self.chores_lock:
            f = open(self.chores_filename, 'wb')
            pickle.dump(self.chores, f)
            f.close()

    async def addChore(self, new_chore, skip_save=False):
        async with self.chores_lock:
            if new_chore.emote in self.chores:
                return False

            self.chores[new_chore.emote] = new_chore

        if not skip_save:
            await self._saveChores()
        return True

    async def postDailyUpdate(self, schedule_new_post=True, channel=None):
        if channel is None:
            channel = self.channel

        message, ordered_emotes = await self.getChoreMessage()

        self.monitor_message = await self.discord_client.get_channel(
            channel).send(message)
        if len(ordered_emotes) > 0:
            await self.addEmotes(self.monitor_message, ordered_emotes)

        if schedule_new_post:
            return self.createEventForTomorrow()
        else:
            return None

    async def getChoreMessage(self):
        async with self.chores_lock:
            chores_for_today = []
            today = datetime.now(pytz.timezone('US/Pacific')).date()
            for _, chore in self.chores.items():
                if chore.shouldPost(today):
                    chores_for_today.append(chore)

                    # Remove the chore from oustanding Chore if triggers again.
                    if chore.emote in self.outstanding_chores:
                        del self.outstanding_chores[chore.emote]

            if len(self.outstanding_chores) + len(chores_for_today) == 0:
                return 'No chores for today!', []

            for chore in chores_for_today:
                chore.last_post = today

            msg = ''
            ordered_emotes = []
            if len(self.outstanding_chores) > 0:
                msg += '**Outstanding Chores**:\n' + '\n'.join(
                    chore.getMessageLine()
                    for _, chore in self.outstanding_chores.items())
                for e, _ in self.outstanding_chores.items():
                    ordered_emotes.append(e)

            if len(self.outstanding_chores) > 0 and len(chores_for_today) > 0:
                msg += '\n\n'

            if len(chores_for_today) > 0:
                msg += '**New Chores**:\n' + '\n'.join(
                    chore.getMessageLine() for chore in chores_for_today)
                for chore in chores_for_today:
                    ordered_emotes.append(chore.emote)

                # Add chores to outstanding_chores.
                for chore in chores_for_today:
                    self.outstanding_chores[chore.emote] = chore

            msg += '\n\n'
            msg += '**React with the corresponding emote to mark the chore as done.**'
            return msg, ordered_emotes

    async def addEmotes(self, message, ordered_emotes):
        # Note that bot.py already filters out reactions from itself.
        for emote in ordered_emotes:
            await message.add_reaction(emote)

    def getPostTimeForTomorrow(self):
        return datetime.combine(
            datetime.now(pytz.timezone('US/Pacific')).date() +
            timedelta(days=1), self.post_time)

    def createEventForTomorrow(self):
        return EC.Event(self.getPostTimeForTomorrow(), self.postDailyUpdate)

    async def onReactionAdd(self, reaction, user):
        # Note that bot.py already filters out reactions from itself.
        if reaction.message != self.monitor_message:
            return

        async with self.chores_lock:
            str_reaction = str(reaction.emoji)
            if str_reaction in self.outstanding_chores:
                completed_chore = self.outstanding_chores[str_reaction]
                del self.outstanding_chores[str_reaction]

                # If it is a one-time chore, delete it.
                if completed_chore.chore_frequency.frequency == ONE_TIME:
                    del self.chores[str_reaction]

                await self.discord_client.get_channel(self.channel).send(
                    'Marked chore as completed: {}'.format(
                        completed_chore.name))
            else:
                await self.discord_client.get_channel(
                    self.channel
                ).send('Reaction didn\'t match any existing chore.')

    def getEmote(self, emote_string):
        return self.getEmote(emote_string)
