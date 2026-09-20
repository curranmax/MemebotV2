import os
import sys
import pytz
from datetime import datetime, date, timedelta

# Add workspace directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import ow_tracker
from ow_tracker import (
    parseDate, get_pacific_date, SingleWeek, Goal, WeeklyTracker,
    OverwatchTracker, OverwatchTrackerManager
)

def test_parse_date():
    print("Running test_parse_date...")
    tz = pytz.timezone("US/Pacific")
    now_pt = datetime.now(tz=tz)
    current_year = now_pt.date().year

    # Test MM/DD
    d1, dt1, err1 = parseDate("08/11")
    assert err1 is None, f"Unexpected error: {err1}"
    assert d1 == date(current_year, 8, 11)
    assert dt1.date() == date(current_year, 8, 11)
    assert dt1.tzinfo == tz

    # Test MM/DD/YYYY
    d2, dt2, err2 = parseDate("08/11/2026")
    assert err2 is None
    assert d2 == date(2026, 8, 11)
    assert dt2.year == 2026

    # Test MM/DD/YY
    d3, dt3, err3 = parseDate("08/11/26")
    assert err3 is None
    assert d3 == date(2026, 8, 11)

    # Test single digit M/D
    d4, dt4, err4 = parseDate("8/4")
    assert err4 is None
    assert d4 == date(current_year, 8, 4)

    # Test invalid formats
    _, _, err5 = parseDate("2026-08-11")
    assert err5 == 'Invalid date format!'

    _, _, err6 = parseDate("invalid")
    assert err6 == 'Invalid date format!'

    # Test invalid calendar date
    _, _, err7 = parseDate("02/30/2026")
    assert err7 == 'Invalid date!'

    _, _, err8 = parseDate("13/01/2026")
    assert err8 == 'Invalid date!'

    print("test_parse_date passed!")

def test_week_lookup_and_change_boundary():
    print("Running test_week_lookup_and_change_boundary...")
    tz = pytz.timezone("US/Pacific")
    
    # Week 1: Tuesday 2026-08-04 8:00 AM to Tuesday 2026-08-11 8:00 AM
    t1 = datetime(2026, 8, 4, 8, tzinfo=tz)
    t2 = datetime(2026, 8, 11, 8, tzinfo=tz)
    t3 = datetime(2026, 8, 18, 8, tzinfo=tz)
    
    w1 = SingleWeek(Goal(5), t1, t2)
    w2 = SingleWeek(Goal(10), t2, t3)
    w3 = SingleWeek(Goal(15), t3, None) # current week
    
    tracker = WeeklyTracker()
    tracker.previous_weeks = [w1, w2]
    tracker.current_week = w3
    
    # Midweek inside Week 1 (Wed 2026-08-05) -> should match Week 1
    found_w = tracker.getWeekForDate("08/05/2026")
    assert found_w is w1, f"Expected w1, got {found_w}"
    
    # Start of Week 1 (Tue 2026-08-04) -> should match Week 1
    found_w = tracker.getWeekForDate("08/04/2026")
    assert found_w is w1, f"Expected w1, got {found_w}"

    # End of Week 1 / Start of Week 2 (Tue 2026-08-11) -> boundary date where week changes!
    # "If the date given from the week changes. assume that the change is for the week just starting, not ending."
    # Should match Week 2 (starting on 08/11), NOT Week 1 (ending on 08/11)!
    found_w = tracker.getWeekForDate("08/11/2026")
    assert found_w is w2, f"Expected w2 (week just starting), got {found_w}"

    # Midweek inside Week 2 (Sat 2026-08-15) -> should match Week 2
    found_w = tracker.getWeekForDate("08/15/2026")
    assert found_w is w2, f"Expected w2, got {found_w}"

    # End of Week 2 / Start of Week 3 (Tue 2026-08-18) -> boundary date!
    # Should match Week 3 (current_week, starting on 08/18), NOT Week 2!
    found_w = tracker.getWeekForDate("08/18/2026")
    assert found_w is w3, f"Expected w3 (current_week), got {found_w}"

    # Date inside Week 3 (Thu 2026-08-20) -> should match Week 3
    found_w = tracker.getWeekForDate("08/20/2026")
    assert found_w is w3, f"Expected w3, got {found_w}"

    # Date before Week 1 (2026-08-01) -> should be None
    found_w = tracker.getWeekForDate("08/01/2026")
    assert found_w is None, f"Expected None, got {found_w}"

    # Date in future week after Week 3 ends (2026-08-26) -> should be None
    found_w = tracker.getWeekForDate("08/26/2026")
    assert found_w is None, f"Expected None, got {found_w}"

    print("test_week_lookup_and_change_boundary passed!")

def test_set_weekly_goal_by_date():
    print("Running test_set_weekly_goal_by_date...")
    tz = pytz.timezone("US/Pacific")
    
    t1 = datetime(2026, 8, 4, 8, tzinfo=tz)
    t2 = datetime(2026, 8, 11, 8, tzinfo=tz)
    t3 = datetime(2026, 8, 18, 8, tzinfo=tz)
    
    w1 = SingleWeek(Goal(5), t1, t2)
    w2 = SingleWeek(Goal(10), t2, t3)
    w3 = SingleWeek(Goal(15), t3, None)
    
    tracker = WeeklyTracker()
    tracker.previous_weeks = [w1, w2]
    tracker.current_week = w3
    
    # Get goal by date
    g1 = tracker.getGoal("08/05/2026")
    assert g1.total == 5
    
    g2 = tracker.getGoal("08/11/2026") # Week 2 start
    assert g2.total == 10
    
    # Set goal for previous week 1
    res = tracker.setGoal(Goal(7), target_date="08/06/2026")
    assert res is True
    assert w1.goal.total == 7
    assert w2.goal.total == 10
    assert w3.goal.total == 15
    
    # Set goal on boundary date (08/11/2026) -> should modify Week 2
    res = tracker.setGoal(Goal(12), target_date="08/11/2026")
    assert res is True
    assert w1.goal.total == 7
    assert w2.goal.total == 12
    assert w3.goal.total == 15

    # Try setting goal for non-existent date
    res = tracker.setGoal(Goal(20), target_date="07/01/2026")
    assert res is False

    print("test_set_weekly_goal_by_date passed!")

def test_manager_and_tracker_integration():
    print("Running test_manager_and_tracker_integration...")
    test_fname = "scratch/test_manager_date.pickle"
    if os.path.exists(test_fname):
        os.remove(test_fname)
        
    manager = OverwatchTrackerManager(ow_tracker_fname=test_fname)
    user_id = 12345
    
    tz = pytz.timezone("US/Pacific")
    t1 = datetime(2026, 8, 4, 8, tzinfo=tz)
    t2 = datetime(2026, 8, 11, 8, tzinfo=tz)
    t3 = datetime(2026, 8, 18, 8, tzinfo=tz)
    
    w1 = SingleWeek(Goal(5), t1, t2)
    w2 = SingleWeek(Goal(10), t2, t3)
    w3 = SingleWeek(Goal(15), t3, None)
    
    owt = manager._getOrCreateOwTrackerForUser(user_id)
    owt.weekly_tracker.previous_weeks = [w1, w2]
    owt.weekly_tracker.current_week = w3
    manager.saveTrackersToFile()
    
    # Test setting weekly goal for previous week via manager
    manager.setWeeklyGoal(user_id, new_weekly_goal=Goal(8), skip=True, target_date="08/06/2026")
    
    # Verify in-memory and reloaded from disk
    assert w1.goal.total == 8
    assert w1.skipped is True
    assert w2.goal.total == 10
    
    manager2 = OverwatchTrackerManager(ow_tracker_fname=test_fname)
    owt2 = manager2._getOrCreateOwTrackerForUser(user_id)
    assert owt2.weekly_tracker.previous_weeks[0].goal.total == 8
    assert owt2.weekly_tracker.previous_weeks[0].skipped is True
    
    if os.path.exists(test_fname):
        os.remove(test_fname)
        
    print("test_manager_and_tracker_integration passed!")

if __name__ == "__main__":
    test_parse_date()
    test_week_lookup_and_change_boundary()
    test_set_weekly_goal_by_date()
    test_manager_and_tracker_integration()
    print("All date tests passed successfully!")
