import sys
from unittest.mock import MagicMock

# Mock discord and other external modules to avoid import errors
sys.modules['discord'] = MagicMock()
sys.modules['discord.app_commands'] = MagicMock()
sys.modules['discord.ext'] = MagicMock()
sys.modules['discord.ext.commands'] = MagicMock()
sys.modules['discord.ext.tasks'] = MagicMock()
sys.modules['event_calendar'] = MagicMock()
sys.modules['edit_distance'] = MagicMock()

import json
sys.path.append('.')
import ow_tracker

data = {
    "MAPS": ow_tracker.MAPS,
    "HEROES": ow_tracker.HEROES,
    "STADIUM_HEROES": ow_tracker.STADIUM_HEROES
}

with open('data/overwatch_data.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=4, ensure_ascii=False)

print("Export successful!")
