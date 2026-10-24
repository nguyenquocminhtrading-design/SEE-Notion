#!/usr/bin/env python3
"""Quick test to check template parsing functionality."""

from datetime import UTC, datetime, timedelta

# Import the template parser functions directly
from app.services.template_parser import parse_smart_deadline_and_status


def test_parse_smart_deadline_and_status():
    """Test the parse_smart_deadline_and_status function."""
    today = datetime.now(UTC).date()
    print(f"Today is: {today.isoformat()}")
    
    # Test 1: Single date "hôm nay"
    print("\nTest 1: 'hom nay'")
    start, deadline, status = parse_smart_deadline_and_status("hom nay", today)
    print(f"  Start: {start}, Deadline: {deadline}, Status: {status}")
    assert deadline is not None, "Deadline should not be None for 'hom nay'"
    
    # Test 2: Date range "24/10 - 30/10"
    print("\nTest 2: '24/10 - 30/10'")
    start, deadline, status = parse_smart_deadline_and_status("24/10 - 30/10", today)
    print(f"  Start: {start}, Deadline: {deadline}, Status: {status}")
    assert start is not None, "Start should not be None for range"
    assert deadline is not None, "Deadline should not be None for range"
    
    # Test 3: Date range with full year
    print("\nTest 3: '24/10/2026 - 30/10/2026'")
    start, deadline, status = parse_smart_deadline_and_status("24/10/2026 - 30/10/2026", today)
    print(f"  Start: {start}, Deadline: {deadline}, Status: {status}")
    assert start is not None, "Start should not be None for full year range"
    assert deadline is not None, "Deadline should not be None for full year range"
    
    # Test 4: Single date
    print("\nTest 4: '25/12/2026'")
    start, deadline, status = parse_smart_deadline_and_status("25/12/2026", today)
    print(f"  Start: {start}, Deadline: {deadline}, Status: {status}")
    assert deadline is not None, "Deadline should not be None for single date"
    
    # Test 5: "2 tuan"
    print("\nTest 5: '2 tuan'")
    start, deadline, status = parse_smart_deadline_and_status("2 tuan", today)
    print(f"  Start: {start}, Deadline: {deadline}, Status: {status}")
    assert deadline is not None, "Deadline should not be None for '2 tuan'"
    
    # Test 6: "Done"
    print("\nTest 6: 'Done'")
    start, deadline, status = parse_smart_deadline_and_status("Done", today)
    print(f"  Start: {start}, Deadline: {deadline}, Status: {status}")
    assert status == "Done", "Status should be 'Done'"
    assert deadline == today.isoformat(), "Deadline should be today for 'Done'"
    
    # Test 7: Empty string
    print("\nTest 7: Empty string")
    start, deadline, status = parse_smart_deadline_and_status("", today)
    print(f"  Start: {start}, Deadline: {deadline}, Status: {status}")
    assert start is None, "Start should be None for empty string"
    assert deadline is None, "Deadline should be None for empty string"
    assert status == "Not started", "Status should be 'Not started' for empty string"
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED! [OK]")
    print("=" * 60)
    return True


if __name__ == "__main__":
    try:
        test_parse_smart_deadline_and_status()
    except Exception as e:
        print(f"\n[FAIL] TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        exit(1)