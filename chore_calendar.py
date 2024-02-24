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
import random

DAILY = 'Daily'
WEEKLY = 'Weekly'
MONTHLY = 'Monthly'

ALL_FREQUENCIES = [DAILY, WEEKLY, MONTHLY]

CHORE_CHANNEL_FILENAME = 'data/chore_channel.pickle'
CHORES_FILENAME = 'data/chores.pickle'


# TODO split this off into its own bot.
class ChoreCalendarDiscordCommands(app_commands.Group):

    def __init__(self, chore_calendar, *args, **kwargs):
        super(ChoreCalendarDiscordCommands,
              self).__init__(name='chore-calendar', *args, **kwargs)

        self.chore_calendar = chore_calendar

    # add-chore-one-time
    # Debug/print command
    # delete-chore

    @app_commands.command(name='add-chore-recurring',
                          description='Adds a new recurring chore')
    @app_commands.describe(
        name='The name of the chore',
        emote='The emote for the chore',
        daily='Whether or not the chore should be posted daily',
        day_of_the_week='The day of the week the chore should be posted',
        day_of_the_month='The day of the month the chore should be posted',
        offset=
        'How frequently the chore should be done. Ex. a value of 2 means the chore will be done once every 2 days/weeks/months',
    )
    @app_commands.choices(day_of_the_week=[
        app_commands.Choice(name='Monday', value='Monday'),
        app_commands.Choice(name='Tuesday', value='Tuesday'),
        app_commands.Choice(name='Wednesday', value='Wednesday'),
        app_commands.Choice(name='Thursday', value='Thursday'),
        app_commands.Choice(name='Friday', value='Friday'),
        app_commands.Choice(name='Saturday', value='Saturday'),
        app_commands.Choice(name='Sunday', value='Sunday'),
    ])
    async def add_chore_recurring(
            self,
            interaction: discord.Interaction,
            name: str,
            emote: str,
            daily: typing.Optional[bool] = False,
            day_of_the_week: typing.Optional[app_commands.Choice[str]] = None,
            day_of_the_month: typing.Optional[int] = None,
            offset: typing.Optional[int] = 1):
        # TODO Check that emote is valid

        chore_frequency = None
        if daily:
            chore_frequency = DailyFrequency(offset)
        if day_of_the_week != None:
            if chore_frequency != None:
                await interaction.response.send_message(
                    'Invalid settings supplied! Must specify exactly one of "daily", "day_of_week", "day_of_month"!',
                    ephemeral=True)
                return
            chore_frequency = WeeklyFrequency(day_of_the_week.value, offset)
        if day_of_the_month != None:
            if chore_frequency != None:
                await interaction.response.send_message(
                    'Invalid settings supplied! Must specify exactly one of "daily", "day_of_week", "day_of_month"!',
                    ephemeral=True)
                return
            chore_frequency = MonthlyFrequency(day_of_the_month, offset)

        if chore_frequency == None:
            await interaction.response.send_message(
                'Invalid settings supplied! Must specify exactly one of "daily", "day_of_week", "day_of_month"!',
                ephemeral=True)
            return

        result = await self.chore_calendar.addChore(
            Chore(name, emote, chore_frequency))
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

    def __init__(self, frequency, offset):
        self.frequency = frequency

        # A value of 1 means that the chore triggers every day/week/month.
        # A value of 2 means that the chore triggers every other day/week/month.
        # A value of 3 means that the chore triggers every third day/week/month.
        # etc.
        self.offset = offset


class DailyFrequency(ChoreFrequency):

    def __init__(self, offset):
        super(DailyFrequency, self).__init__(DAILY, offset)

    def __eq__(self, other):
        if not isinstance(other, DailyFrequency):
            return False
        return self.offset == other.offset


class WeeklyFrequency(ChoreFrequency):

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

    def __init__(self, name, emote, chore_frequency):
        self.name = name
        self.emote = emote

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
        await self.addEmotes(self.monitor_message, ordered_emotes)

        if schedule_new_post:
            return self.createEventForTomorrow()
        else:
            return None

    async def getChoreMessage(self):
        async with self.chores_lock:
            chores_for_today = []
            today = date.today()
            for _, chore in self.chores.items():
                if chore.shouldPost(today):
                    chores_for_today.append(chore)

                    # Remove the chore from oustanding Chore if triggers again.
                    if chore.emote in self.outstanding_chores:
                        del self.outstanding_chores[chore.emote]

            if len(self.outstanding_chores) + len(chores_for_today) == 0:
                return 'No chores for today!'

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
        return datetime.combine(date.today() + timedelta(days=1),
                                self.post_time)

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

                await self.discord_client.get_channel(self.channel).send(
                    'Marked chore as completed: {}'.format(
                        completed_chore.name))
            else:
                await self.discord_client.get_channel(
                    self.channel
                ).send('Reaction didn\'t match any existing chore.')

    def getEmote(self, emote_string):
        return self.discord_client.getEmote(emote_string)
