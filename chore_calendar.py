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
            daily: typing.Optional[bool] = False,
            day_of_the_week: typing.Optional[app_commands.Choice[str]] = None,
            day_of_the_month: typing.Optional[int] = None,
            offset: typing.Optional[int] = 1):
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

    def getMessageLine(self, emote):
        return '  {} --> {}'.format(emote, str(self.name))

    def __eq__(self, other):
        if not isinstance(other, Chore):
            return False
        return self.name == other.name and self.chore_frequency == other.chore_frequency


CHORE_EMOTES = {
    'a': ['🇦'],
    'b': ['🇧'],
    'c': ['🇨'],
    'd': ['🇩'],
    'e': ['🇪'],
    'f': ['🇫'],
    'g': ['🇬'],
    'h': ['🇭'],
    'i': ['🇮'],
    'j': ['🇯'],
    'k': ['🇰'],
    'l': ['🇱'],
    'm': ['🇲'],
    'n': ['🇳'],
    'o': ['🇴'],
    'p': ['🇵'],
    'q': ['🇶'],
    'r': ['🇷'],
    's': ['🇸'],
    't': ['🇹'],
    'u': ['🇺'],
    'v': ['🇻'],
    'w': ['🇼'],
    'x': ['🇽'],
    'y': ['🇾'],
    'z': ['🇿'],
    '0': ['0️⃣'],
    '1': ['1️⃣'],
    '2': ['2️⃣'],
    '3': ['3️⃣'],
    '4': ['4️⃣'],
    '5': ['5️⃣'],
    '6': ['6️⃣'],
    '7': ['7️⃣'],
    '8': ['8️⃣'],
    '9': ['9️⃣'],
}


class ChoreCalendar:

    def __init__(self, discord_client, event_calendar):
        self.discord_client = discord_client
        self.event_calendar = event_calendar

        # The saved chores
        self.chores = []
        self.chores_lock = asyncio.Lock()
        self.chores_filename = CHORES_FILENAME
        self._loadChores()

        # Details about when and where to post
        self.post_time = time(hour=8, tzinfo=pytz.timezone('US/Pacific'))
        self.channel = None
        self.chore_channel_filename = CHORE_CHANNEL_FILENAME
        self._loadChannel()

        # Outstanding chores, and the message to watch for reacts.
        # Outstanding chores is keyed by an emote, and the value is a chore.
        self.outstanding_chores = {}
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

        for chore in loaded_chores:
            # TODO Skip saving for this case?
            asyncio.run(self.addChore(chore))

    async def _saveChores(self):
        async with self.chores_lock:
            f = open(self.chores_filename, 'wb')
            pickle.dump(self.chores, f)
            f.close()

    async def addChore(self, new_chore):
        async with self.chores_lock:
            for existing_chore in self.chores:
                if existing_chore.name == new_chore.name:
                    return False

            self.chores.append(new_chore)

        await self._saveChores()
        return True

    async def postDailyUpdate(self, schedule_new_post=True, channel=None):
        if channel is None:
            channel = self.channel

        message = await self.getChoreMessage()

        self.monitor_message = await self.discord_client.get_channel(
            channel).send(message)

        if schedule_new_post:
            return self.createEventForTomorrow()
        else:
            return None

    async def getChoreMessage(self):
        async with self.chores_lock:
            chores_for_today = []
            today = date.today()
            for chore in self.chores:
                if chore.shouldPost(today):
                    chores_for_today.append(chore)

            # Go through self.outstanding_chores and remove duplicates.
            for k, chore in list(self.outstanding_chores.items()):
                if chore in chores_for_today:
                    del self.outstanding_chores[k]

            if len(self.outstanding_chores) and len(chores_for_today) == 0:
                return 'No chores for today!'

            for chore in chores_for_today:
                chore.last_post = today

            msg = '```'
            if len(self.outstanding_chores) > 0:
                msg += 'The outstanding chores for today are:\n' + '\n'.join(
                    chore.getMessageLine(emote)
                    for emote, chore in self.outstanding_chores)

            if len(self.outstanding_chores) > 0 and len(chores_for_today) > 0:
                msg += '\n' + '=' * 20 + '\n'

            if len(chores_for_today) > 0:
                # Determine the emotes for the new chores.
                chores_with_emotes = []
                for chore in chores_for_today:
                    # Try to use a character in the name.
                    emote_found = False
                    for char in chore.name:
                        c = char.lower()
                        if c in CHORE_EMOTES:
                            es = CHORE_EMOTES[c]
                            random.shuffle(es)
                            for e in es:
                                if e not in self.outstanding_chores:
                                    self.outstanding_chores[e] = chore
                                    chores_with_emotes = (e, chore)
                                    emote_found = True
                                    break

                    # Otherwise choose randomly.
                    if not emote_found:
                        all_es = [
                            e for _, es in CHORE_EMOTES.items() for e in es
                            if e not in self.outstanding_chores
                        ]
                        if len(all_es) == 0:
                            raise Exception('No emotes left!')
                        e = random.choice(all_es)
                        self.outstanding_chores[e] = chore
                        chores_with_emotes.append((e, chore))

                    # TMP Check that chore is in chores_with_emotes
                    if all(chore != ch for _, ch in chores_with_emotes):
                        raise Exception(
                            'Chore not added to chores_with_emotes')

                if len(chores_with_emotes) != len(chores_for_today):
                    raise Exception('Mismatch in length of chore arrays')

                msg += 'The new chores for today are:\n' + '\n'.join(
                    chore.getMessageLine(e) for e, chore in chores_with_emotes)
            msg += '\n' + '=' * 20 + '\n'
            msg += 'React with the corresponding emote to mark the chore as done.\n'
            msg += '```'
            return msg

    def getPostTimeForTomorrow(self):
        return datetime.combine(date.today() + timedelta(days=1),
                                self.post_time)

    def createEventForTomorrow(self):
        return EC.Event(self.getPostTimeForTomorrow(), self.postDailyUpdate)

    async def onReactionAdd(self, reaction, user):
        if reaction.message != self.monitor_message:
            return

        async with self.chores_lock:
            if reaction.emoji in self.outstanding_chores:
                completed_chore = self.outstanding_chores[reaction.emoji]
                del self.outstanding_chores[reaction.emoji]

                await self.discord_client.get_channel(self.channel).send(
                    'Marked chore as completed: {}'.format(
                        completed_chore.name))
