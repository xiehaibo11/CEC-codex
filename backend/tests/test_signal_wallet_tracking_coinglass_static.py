from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _module_source(path_without_ext: Path) -> str:
    """Read a module's source whether it is a single ``.py`` file or a package
    directory (the module may have been split into a package). Concatenates all
    ``.py`` files in the package so content-invariant checks still hold."""
    py_file = path_without_ext.with_suffix(".py")
    if py_file.is_file():
        return py_file.read_text()
    if path_without_ext.is_dir():
        return "\n".join(
            f.read_text() for f in sorted(path_without_ext.rglob("*.py"))
        )
    raise FileNotFoundError(f"Neither {py_file} nor package dir {path_without_ext} exists")


def test_signal_wallet_tracking_frontend_no_longer_points_to_hyper_insight():
    signal_manager = (REPO_ROOT / "frontend/app/components/signal/SignalManager.tsx").read_text()
    zh_locale = (REPO_ROOT / "frontend/app/locales/zh.json").read_text()
    en_locale = (REPO_ROOT / "frontend/app/locales/en.json").read_text()

    combined_frontend = "\n".join([signal_manager, zh_locale, en_locale])

    assert "Hyper Insight" not in combined_frontend
    assert "hyper.akooi.com" not in combined_frontend
    assert "Cookies.get('arena_token')" not in signal_manager
    assert "CoinGlass" in combined_frontend


def test_signal_wallet_tracking_backend_uses_coinglass_status_not_hyper_insight_runtime():
    signal_routes = _module_source(REPO_ROOT / "backend/api/signal_routes")
    main_source = (REPO_ROOT / "backend/main.py").read_text()

    assert "hyper_insight_wallet_service" not in signal_routes
    assert "startup_hyper_insight_wallet_runtime" not in main_source
    assert "shutdown_hyper_insight_wallet_runtime" not in main_source
    assert "coinglass" in signal_routes.lower()


def test_hyper_ai_wallet_tools_do_not_call_hyper_insight_runtime():
    hyper_ai_tools = (REPO_ROOT / "backend/services/hyper_ai_tools.py").read_text()
    system_prompt = (REPO_ROOT / "backend/config/hyper_ai_system_prompt.md").read_text()
    knowledge_base = (REPO_ROOT / "backend/config/hyper_ai_knowledge_base.md").read_text()

    wallet_tool_slice = hyper_ai_tools[
        hyper_ai_tools.index("def execute_analyze_tracked_address"):
        hyper_ai_tools.index("def execute_list_strategies")
    ] + hyper_ai_tools[
        hyper_ai_tools.index("def execute_get_tracked_wallets"):
        hyper_ai_tools.index("_STRATEGY_RADAR_UNIVERSE_CACHE")
    ]

    assert "hyper_insight_wallet_service" not in wallet_tool_slice
    assert "hyper_insight_wallet_access_token" not in wallet_tool_slice
    assert "https://hyper.akooi.com/" not in wallet_tool_slice
    assert "CoinGlass" in wallet_tool_slice
    assert "CoinGlass wallet" in system_prompt
    assert "CoinGlass wallet" in knowledge_base
