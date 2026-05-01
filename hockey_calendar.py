# Check google calendar once per day in the morning. If there is a game that day, post when it is and include link to youbute (if available).
# Post 10 minutes before a game, check google calendar to confirm the game hasn't changed. If its happening, post reminder + link (if available).

import event_calendar as EC

import discord
from discord import app_commands
import os
import pickle
from datetime import datetime, time, timedelta
import pytz
import logging
import asyncio
from icalevents.icalevents import events
import re

class HockeyCalendarDiscordCommands(app_commands.Group):
    def __init__(self, manager):
        super().__init__(name='hockey', description='Commands for the hockey calendar.')
        self.manager = manager

    @app_commands.command(name='bind-hockey-calendar', description='Starts the hockey calendar notifications in this channel.')
    @app_commands.describe(
        ical_link='The iCal link (.ics). In Google Calendar: Calendar Settings -> Integrate Calendar -> Secret/Public address in iCal format'
    )
    async def bind_hockey_calendar(self, interaction: discord.Interaction, ical_link: str):
        self.manager.bind_hockey_calendar(interaction.channel_id, ical_link)
        await interaction.response.send_message(f'Hockey calendar notifications will be posted in this channel for calendar {ical_link}.', ephemeral=True)


class HockeyCalendarManager:
    def __init__(self, discord_client=None, event_calendar=None, hockey_calendar_fname='data/hockey_calendar.pkl'):
        if discord_client is None:
            raise Exception('No discord client provided.')
        self.discord_client = discord_client
        if event_calendar is None:
            raise Exception('No event calendar provided.')
        self.event_calendar = event_calendar

        self.hockey_calendar_fname = hockey_calendar_fname
        self.channel_id = None
        self.ical_link = None

        self.load()

    def load(self):
        # If file does not exist, then init self.overwatch_trackers to empty dict
        if not os.path.exists(self.hockey_calendar_fname):
            self.save()
            return

        f = open(self.hockey_calendar_fname, 'rb')
        self.channel_id, self.ical_link = pickle.load(f)
        logging.info('hockey_calendar.load(): channel_id = %s, ical_link = %s', self.channel_id, self.ical_link)

        if self.channel_id is not None and self.ical_link is not None:
            self.startDailyCheck()

    def save(self):
        logging.info('hockey_calendar.save(): channel_id = %s, ical_link = %s', self.channel_id, self.ical_link)
        f = open(self.hockey_calendar_fname, 'wb')
        pickle.dump((self.channel_id, self.ical_link), f)

    def getDiscordCommands(self):
        return [HockeyCalendarDiscordCommands(self)]

    def bind_hockey_calendar(self, channel_id: int, ical_link: str):
        self.channel_id = channel_id
        self.ical_link = ical_link
        self.save()

        # Start the daily check
        self.startDailyCheck()

    def startDailyCheck(self):
        self.event_calendar.addEvent(EC.Event(self.getNextDailyCheckTime(), self.dailyCheck))

    def getNextDailyCheckTime(self):
        now = datetime.now(pytz.timezone('US/Pacific'))
        pt = time(hour=8, tzinfo=pytz.timezone('US/Pacific'))
        et = datetime.combine((now + timedelta(days=1)).date(), pt, pytz.timezone("US/Pacific"))

        logging.info('getNextDailyCheckTime(): now = %s, et = %s', now.isoformat(), et.isoformat())
        return et

    async def get_pwhl_youtube_link(self, summary: str, game_date: datetime):
        loop = asyncio.get_running_loop()
        def _fetch():
            try:
                import urllib.request
                import xml.etree.ElementTree as ET
                
                rss_url = 'https://www.youtube.com/feeds/videos.xml?channel_id=UCNKUkQV2R0JKakyE1vuC1lQ'
                req = urllib.request.Request(rss_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req) as response:
                    xml_data = response.read()
                    root = ET.fromstring(xml_data)
                    ns = {'yt': 'http://www.youtube.com/xml/schemas/2015', 'atom': 'http://www.w3.org/2005/Atom'}
                    
                    date_str1 = game_date.strftime('%B %d, %Y').replace(' 0', ' ')
                    date_str2 = game_date.strftime('%b %d, %Y').replace(' 0', ' ')
                    
                    summary_words = set(w.lower() for w in re.findall(r'[a-zA-Z]+', summary) if len(w) >= 3)
                    
                    best_match = None
                    best_score = -1
                    
                    for entry in root.findall('atom:entry', ns):
                        title_elem = entry.find('atom:title', ns)
                        if title_elem is None:
                            continue
                        title = title_elem.text
                        link = entry.find('atom:link', ns).attrib['href']
                        
                        title_words = set(w.lower() for w in re.findall(r'[a-zA-Z]+', title))
                        word_overlap = 0
                        for sw in summary_words:
                            for tw in title_words:
                                if sw in tw or tw in sw:
                                    word_overlap += 1
                                    break
                                    
                        score = word_overlap
                        
                        if date_str1.lower() in title.lower() or date_str2.lower() in title.lower():
                            score += 5
                            
                        is_pwhl = 'pwhl' in title.lower()
                        
                        if (score > 0 or is_pwhl) and score > best_score:
                            if word_overlap > 0 or score >= 5:
                                best_score = score
                                best_match = link
                                
                    return best_match
            except Exception as e:
                logging.error(f'Error fetching YouTube link: {e}')
                return None
                
        return await loop.run_in_executor(None, _fetch)

    async def dailyCheck(self):
        # Stops the daily check if channel_id or ical_link is not set.
        if self.channel_id is None or self.ical_link is None:
            return

        # TODO: Consider changing to the official Google Calendar API in the future (Option 2).
        # Option 2 would involve using the `google-api-python-client` library. This is more
        # powerful and allows fetching events from strictly private calendars without generating
        # a public or secret iCal link. However, it requires setting up a Google Cloud Project,
        # enabling the Google Calendar API, creating a Service Account, and downloading the JSON
        # credentials file to use for authentication.

        try:
            now = datetime.now(pytz.timezone('US/Pacific'))
            # Get start of today and end of today in local time
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=1)

            # Log now, start_date, end_date
            logging.info('dailyCheck(): now = %s, start_date = %s, end_date = %s', now.isoformat(), start_date.isoformat(), end_date.isoformat())
            
            # icalevents is synchronous, run it in an executor to avoid blocking the bot
            loop = asyncio.get_running_loop()
            cal_events = await loop.run_in_executor(None, lambda: events(url=self.ical_link, start=start_date, end=end_date))

            if cal_events:
                # If there are any events for today, post them to the discord channel.
                msg = "**PWHL Games Today!**\n"
                for e in sorted(cal_events, key=lambda x: x.start):
                    # Log the event
                    logging.info('dailyCheck(): event = %s', e)

                    event_pt = e.start.astimezone(pytz.timezone('US/Pacific'))
                    time_str = event_pt.strftime('%I:%M %p')
                    msg += f"- **{e.summary}** at {time_str}"

                    # Add description if it exists (might contain links)
                    has_yt_link = False
                    if hasattr(e, 'description') and e.description and e.description.strip():
                        description = e.description
                        # Log the full description
                        logging.info('dailyCheck(): description = %s', description)

                        # Use a regex to find any youtube links in the description. Replace with "[link](<youtube_link>)"
                        if re.search(r'(https?://(?:www\.)?youtube\.com/watch\?v=[a-zA-Z0-9_-]+)', description):
                            has_yt_link = True
                        description = re.sub(r'(https?://(?:www\.)?youtube\.com/watch\?v=[a-zA-Z0-9_-]+)', r'[watch here](<\1>)', description)
                        msg += f" - {description.strip()}"
                    
                    if not has_yt_link:
                        # Check the "The PWHL" youtube channel for a link to this game.
                        yt_link = await self.get_pwhl_youtube_link(e.summary, event_pt)
                        logging.info('dailyCheck: get_pwhl_youtube_link(summary = %s, event_pt = %s) -> yt_link = %s', e.summary, event_pt.isoformat(), yt_link)
                        if yt_link:
                            msg += f" - [watch here](<{yt_link}>)"

                    msg += "\n"
                channel = self.discord_client.get_channel(self.channel_id)
                if channel:
                    await channel.send(msg)

        except Exception as e:
            logging.error(f'Error fetching hockey calendar events: {e}')

        return EC.Event(self.getNextDailyCheckTime(), self.dailyCheck)

        
        

