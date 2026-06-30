from pathlib import Path


def test_backtest_tool_uses_task_api_and_pause_control():
    source = (
        Path(__file__).resolve().parents[2]
        / "frontend/app/components/backtest/BacktestTool.tsx"
    ).read_text()

    assert "createEventContractBacktestTask" in source
    assert "getEventContractBacktestTask" in source
    assert "pauseEventContractBacktestTask" in source
    assert "BACKTEST_TASK_STORAGE_KEY" in source
    assert "pauseBacktest" in source


def test_backtest_results_panel_renders_task_progress_and_ai_statuses():
    source = (
        Path(__file__).resolve().parents[2]
        / "frontend/app/components/backtest/BacktestResultsPanel.tsx"
    ).read_text()

    assert "taskStatus" in source
    assert "ai_reviewer_statuses" in source
    assert "progress_pct" in source
