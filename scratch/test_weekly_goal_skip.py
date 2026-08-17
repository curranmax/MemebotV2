import os
import sys
import pickle
from datetime import datetime, timedelta
import pytz

# Add the workspace directory to the path so we can import ow_tracker
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import ow_tracker
from ow_tracker import SingleWeek, Goal, WeeklyTracker, OverwatchGame, StadiumGame, OverwatchTrackerManager

def test_single_week_skipped_display():
    print("Running test_single_week_skipped_display...")
    goal = Goal(5, comp=2, stadium=3)
    start = datetime.now(tz=pytz.timezone("US/Pacific"))
    
    # Test active (not skipped)
    week_active = SingleWeek(goal, start, skipped=False)
    table_active = week_active.getGoalTable()
    assert "SKIP" not in table_active
    assert "0005" in table_active
    
    # Test skipped
    week_skipped = SingleWeek(goal, start, skipped=True)
    table_skipped = week_skipped.getGoalTable()
    assert "SKIP" in table_skipped
    assert "0005" not in table_skipped
    print("test_single_week_skipped_display passed!")

def test_weekly_tracker_streaks():
    print("Running test_weekly_tracker_streaks...")
    tz = pytz.timezone("US/Pacific")
    goal = Goal(5)
    
    # Create weekly tracker
    tracker = WeeklyTracker(goal)
    
    # We will simulate past weeks
    # Week 1: met goal
    w1 = SingleWeek(goal, datetime.now(tz=tz) - timedelta(days=21), datetime.now(tz=tz) - timedelta(days=14), skipped=False)
    w1.games = [1, 2, 3, 4, 5]
    
    # Week 2: skipped (goal not met physically, but skipped)
    w2 = SingleWeek(goal, datetime.now(tz=tz) - timedelta(days=14), datetime.now(tz=tz) - timedelta(days=7), skipped=True)
    w2.games = [1]
    
    # Week 3: met goal
    w3 = SingleWeek(goal, datetime.now(tz=tz) - timedelta(days=7), datetime.now(tz=tz), skipped=False)
    w3.games = [1, 2, 3, 4, 5]
    
    tracker.previous_weeks = [w1, w2, w3]
    
    # Current week: not met yet, not skipped
    tracker.current_week = SingleWeek(goal, datetime.now(tz=tz), skipped=False)
    tracker.current_week.games = [1]
    
    # Active Streak should be 2: (w1 met + w3 met), w2 skipped does not break but doesn't add to length.
    # Current week is not met yet, so active streak is 2.
    assert tracker.getActiveStreak() == 2, f"Expected 2, got {tracker.getActiveStreak()}"
    
    # Longest Streak should be 2.
    assert tracker.getLongestStreak() == 2, f"Expected 2, got {tracker.getLongestStreak()}"
    
    # If current week is skipped, active streak should still be 2.
    tracker.current_week.skipped = True
    assert tracker.getActiveStreak() == 2, f"Expected 2, got {tracker.getActiveStreak()}"
    
    # If we unskip current week and meet goal, active streak should be 3.
    tracker.current_week.skipped = False
    tracker.current_week.games = [1, 2, 3, 4, 5]
    assert tracker.getActiveStreak() == 3, f"Expected 3, got {tracker.getActiveStreak()}"
    assert tracker.getLongestStreak() == 3, f"Expected 3, got {tracker.getLongestStreak()}"
    
    print("test_weekly_tracker_streaks passed!")

def test_advance_week_reset():
    print("Running test_advance_week_reset...")
    tz = pytz.timezone("US/Pacific")
    goal = Goal(5)
    tracker = WeeklyTracker(goal)
    tracker.current_week.skipped = True
    
    # Advance week
    tracker.advanceWeek()
    
    # The new current week should not be skipped
    assert tracker.current_week.skipped is False, "New week should not be skipped by default"
    # The previous week should still be skipped
    assert tracker.previous_weeks[-1].skipped is True, "Previous week should preserve skipped status"
    print("test_advance_week_reset passed!")

def test_recompute_weekly_goals_preserves_skipped():
    print("Running test_recompute_weekly_goals_preserves_skipped...")
    tz = pytz.timezone("US/Pacific")
    goal = Goal(5)
    
    # Create weekly tracker with an old skipped week and a normal week
    tracker = WeeklyTracker(goal)
    
    # Setup specific times on Tuesdays to align with recompute logic
    # Tuesday 1
    t1 = datetime(2026, 8, 4, 8, tzinfo=tz) # Tuesday
    t2 = datetime(2026, 8, 11, 8, tzinfo=tz) # Tuesday
    t3 = datetime(2026, 8, 18, 8, tzinfo=tz) # Tuesday
    
    w1 = SingleWeek(goal, t1, t2, skipped=True)
    w2 = SingleWeek(goal, t2, t3, skipped=False)
    
    tracker.previous_weeks = [w1]
    tracker.current_week = w2
    
    # Recompute
    tracker.recomputeWeeklyGoals()
    
    # Verify that the recomputed week starting at t1 is still marked as skipped,
    # and the one starting at t2 is not marked as skipped.
    recomputed_w1 = next(w for w in tracker.previous_weeks if w.start == t1)
    recomputed_w2 = tracker.current_week
    
    assert recomputed_w1.skipped is True, "Recomputed week 1 should stay skipped"
    assert recomputed_w2.skipped is False, "Recomputed week 2 should stay false"
    print("test_recompute_weekly_goals_preserves_skipped passed!")

def test_pickle_migration():
    print("Running test_pickle_migration...")
    # Simulate an old state where weeks don't have the 'skipped' field
    class OldSingleWeek:
        def __init__(self, goal, start):
            self.goal = goal
            self.start = start
            self.end = None
            self.games = []
            # no skipped field
            
    class OldWeeklyTracker:
        def __init__(self):
            self.current_week = OldSingleWeek(Goal(5), datetime.now(tz=pytz.timezone("US/Pacific")))
            self.previous_weeks = [OldSingleWeek(Goal(5), datetime.now(tz=pytz.timezone("US/Pacific")) - timedelta(days=7))]
            
    class OldOverwatchTracker:
        def __init__(self):
            self.weekly_tracker = OldWeeklyTracker()
            self.season = 3
            
    test_fname = "scratch/test_ow_tracker.pickle"
    if os.path.exists(test_fname):
        os.remove(test_fname)
        
    old_data = {"test_user": OldOverwatchTracker()}
    with open(test_fname, "wb") as f:
        pickle.dump(old_data, f)
        
    # Load with manager
    manager = OverwatchTrackerManager(ow_tracker_fname=test_fname)
    
    # Verify skipped has been initialized to False on loaded weeks
    owt = manager.overwatch_trackers["test_user"]
    assert hasattr(owt.weekly_tracker.current_week, "skipped"), "current_week should have skipped field"
    assert owt.weekly_tracker.current_week.skipped is False, "current_week.skipped should be False"
    assert hasattr(owt.weekly_tracker.previous_weeks[0], "skipped"), "previous_week should have skipped field"
    assert owt.weekly_tracker.previous_weeks[0].skipped is False, "previous_week.skipped should be False"
    
    # Clean up test file
    if os.path.exists(test_fname):
        os.remove(test_fname)
        
    print("test_pickle_migration passed!")

if __name__ == "__main__":
    test_single_week_skipped_display()
    test_weekly_tracker_streaks()
    test_advance_week_reset()
    test_recompute_weekly_goals_preserves_skipped()
    test_pickle_migration()
    print("All tests passed successfully!")
