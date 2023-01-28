import event_calendar as EC

import discord
from discord import app_commands
from datetime import date, datetime, time, timedelta
import pytz

DEFAULT_CHANNEL_ID = 706014936085561395  # 929267488464707584


class ChoreCalendarDiscordCommands(app_commands.Group):

    def __init__(self, chore_calendar, *args, **kwargs):
        super(ChoreCalendarDiscordCommands,
              self).__init__(name='chore-calendar', *args, **kwargs)

        self.chore_calendar = chore_calendar

    # Add a chore (with a name/description, emote, when should it happen (weekly/monthly, day of the week/day of the month))
    # Maybe separate monthly/weekly commands
    # Change the time the daily post occurs
    # Debug/print command

    @app_commands.command(name='debug', description='Triggers the daily post')
    async def debug(self, interaction: discord.Interaction):
        await self.chore_calendar.postDailyUpdate(False)

        await interaction.response.send_message('Done', ephemeral=True)


class Chore:
    def __init__(self, description, emote):
        pass

class ChoreCalendar:

    def __init__(self, discord_client, event_calendar):
        self.discord_client = discord_client
        self.event_calendar = event_calendar

        self.chores = []

        self.post_time = time(hour=8, tzinfo=pytz.timezone('US/Pacific'))

        self.event_calendar.addEvent(
            EC.Event(self.getPostTimeForTomorrow(), self.postDailyUpdate))

    def getDiscordCommands(self):
        return [ChoreCalendarDiscordCommands(self)]

    def addChore(self, chore):
        self.chores.append(chore)

    async def postDailyUpdate(self, schedule_new_post=True):
        await self.discord_client.get_channel(DEFAULT_CHANNEL_ID).send('Test')

        if schedule_new_post:
            await self.schedulePostFromTomorrow()

    def getPostTimeForTomorrow(self):
        return datetime.combine(date.today() + timedelta(days=1),
                                self.post_time)

    async def schedulePostFromTomorrow(self):
        await self.event_calendar.addEventWithLock(
            EC.Event(self.getPostTimeForTomorrow(), self.postDailyUpdate))
