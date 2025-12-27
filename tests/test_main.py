"""Tests for main module."""

from nutrition_tracker.main import main


def test_main_runs_without_error(capsys) -> None:
    """Test that main function executes successfully."""
    main()
    captured = capsys.readouterr()
    assert "Nutrition Tracker" in captured.out
