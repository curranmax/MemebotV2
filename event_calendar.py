from discord.ext import commands, tasks
import asyncio
from datetime import datetime
import heapq
import pytz


class Event:

    def __init__(self, datetime, callback):
        self.datetime = datetime

        # Takes no input, and returns an event if a new event should be added to the calendar
        self.callback = callback


class EventCalendar(commands.Cog):

    def __init__(self, discord_client):
        self.discord_client = discord_client
        self.events = []
        self.lock = asyncio.Lock()

    def start(self):
        self.checkEventCalendar.start()

    async def addEventWithLock(self, event):
        async with self.lock:
            self.addEvent(event)

    def addEvent(self, event):
        heapq.heappush(self.events, (event.datetime, event))

    def cog_unload(self):
        self.checkEventCalendar.cancel()

    @tasks.loop(seconds=60)
    async def checkEventCalendar(self):
        if not self.lock.locked():
            async with self.lock:
                now = datetime.now(tz=pytz.timezone('US/Pacific'))
                while len(self.events) > 0 and now > self.events[0][0]:
                    _, event = heapq.heappop(self.events)
                    new_event = await event.callback()
                    if new_event is not None:
                        self.addEvent(new_event)

    @checkEventCalendar.before_loop
    async def before_checkEventCalendar(self):
        await self.discord_client.wait_until_ready()