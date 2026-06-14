import sys
import os
import asyncio
from datetime import datetime, timedelta
import pytz
from unittest.mock import MagicMock, AsyncMock, patch

# Add the project root to python path to import hockey_calendar
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hockey_calendar

class MockDiscordChannel:
    def __init__(self):
        self.sent_messages = []

    async def send(self, msg):
        self.sent_messages.append(msg)
        print(f"\n--- [Mock Discord Channel Message] ---\n{msg}\n--------------------------------------\n")

class MockDiscordClient:
    def __init__(self):
        self.channel = MockDiscordChannel()

    def get_channel(self, channel_id):
        return self.channel

async def test_daily_check_on_date(test_date_str, expected_matches_count, expect_message, expect_reminder=False):
    print(f"Testing dailyCheck for date: {test_date_str}")
    
    # Mock datetime to return our test date
    tz = pytz.timezone('US/Pacific')
    test_now = tz.localize(datetime.strptime(test_date_str, "%Y-%m-%d %H:%M:%S"))
    
    client = MockDiscordClient()
    event_cal = MagicMock()
    
    manager = hockey_calendar.HockeyCalendarManager(
        discord_client=client,
        event_calendar=event_cal,
        hockey_calendar_fname='data/test_hockey_calendar.pkl' # Use test pickle file path
    )
    
    # Manually bind the channel so it's not None
    manager.channel_id = 123456789
    # Set ical_link to None to test World Cup games posting independently of PWHL
    manager.ical_link = None
    
    # We patch datetime.now inside hockey_calendar
    with patch('hockey_calendar.datetime') as mock_datetime:
        # datetime.now() needs to return a timezone aware datetime
        mock_datetime.now.return_value = test_now
        mock_datetime.combine = datetime.combine
        
        # Execute the check
        next_event = await manager.dailyCheck()
        
    sent = client.channel.sent_messages
    if expect_message:
        assert len(sent) == 1, f"Expected 1 message, got {len(sent)}"
        msg = sent[0]
        assert "**FIFA World Cup Games Today!**" in msg, "Missing World Cup header"
        # Count lines that start with "- **"
        lines = [l for l in msg.splitlines() if l.startswith("- **")]
        assert len(lines) == expected_matches_count, f"Expected {expected_matches_count} matches in message, got {len(lines)}"
        
        if expect_reminder:
            assert "**Reminder:** Today is the last day of the" in msg, "Expected round-end reminder, but it was not found"
            print("PASS: Correctly sent message with matches and round-end reminder.")
        else:
            assert "**Reminder:** Today is the last day of the" not in msg, "Unexpected round-end reminder found"
            print(f"PASS: Correctly sent message containing {len(lines)} matches (no reminder).")
    else:
        assert len(sent) == 0, f"Expected 0 messages, got {len(sent)}"
        print("PASS: Correctly sent no messages (no matches scheduled).")

async def main():
    # Test date 2026-06-10 (No matches scheduled)
    await test_daily_check_on_date("2026-06-10 08:00:00", 0, False)
    
    # Test date 2026-06-11 (Opening matches: Mexico vs South Africa, South Korea vs Czech Republic - no reminder)
    await test_daily_check_on_date("2026-06-11 08:00:00", 2, True, expect_reminder=False)
    
    # Test date 2026-06-12 (Canada vs Bosnia & Herzegovina, United States vs Paraguay - no reminder)
    await test_daily_check_on_date("2026-06-12 08:00:00", 2, True, expect_reminder=False)

    # Test date 2026-06-27 (Last day of group stage matches - expect reminder)
    # Let's verify how many games are on June 27, 2026.
    # Group L games: England vs Panama, Croatia vs Ghana etc.
    # We'll expect 4 games on the last day of group stage.
    await test_daily_check_on_date("2026-06-27 08:00:00", 4, True, expect_reminder=True)

    # Clean up test pickle file if generated
    if os.path.exists('data/test_hockey_calendar.pkl'):
        os.remove('data/test_hockey_calendar.pkl')
        
    print("\nAll tests completed successfully!")

if __name__ == "__main__":
    asyncio.run(main())
