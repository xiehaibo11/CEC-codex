"""Tool name mapping and language helpers for bot progress messages.

Shared by the Telegram and Discord message processors to surface
user-friendly, localized labels while Hyper AI runs tools.
"""


TOOL_LABELS = {
    "get_system_overview":    {"en": "Checking system status",      "zh": "正在检查系统状态"},
    "get_wallet_status":      {"en": "Querying wallet balances",    "zh": "正在查询钱包余额"},
    "get_klines":             {"en": "Fetching K-line data",        "zh": "正在获取K线数据"},
    "get_market_regime":      {"en": "Analyzing market regime",     "zh": "正在分析市场状态"},
    "get_market_flow":        {"en": "Analyzing market flow",       "zh": "正在分析资金流向"},
    "get_system_logs":        {"en": "Reading system logs",         "zh": "正在读取系统日志"},
    "get_api_reference":      {"en": "Loading API reference",       "zh": "正在加载API文档"},
    "get_contact_config":     {"en": "Loading contact info",        "zh": "正在加载联系方式"},
    "get_trading_environment":{"en": "Getting trading environment", "zh": "正在获取交易环境"},
    "get_watchlist":          {"en": "Getting watchlist",           "zh": "正在获取监控列表"},
    "update_watchlist":       {"en": "Updating watchlist",          "zh": "正在更新监控列表"},
    "diagnose_trader_issues": {"en": "Diagnosing trader issues",    "zh": "正在诊断交易员问题"},
    "list_traders":           {"en": "Listing AI traders",          "zh": "正在列出AI交易员"},
    "list_signal_pools":      {"en": "Listing signal pools",        "zh": "正在列出信号池"},
    "list_strategies":        {"en": "Listing strategies",          "zh": "正在列出策略"},
    "save_signal_pool":       {"en": "Saving signal pool",          "zh": "正在保存信号池"},
    "save_prompt":            {"en": "Saving prompt strategy",      "zh": "正在保存提示词策略"},
    "save_program":           {"en": "Saving program strategy",     "zh": "正在保存程序化策略"},
    "create_ai_trader":       {"en": "Creating AI trader",          "zh": "正在创建AI交易员"},
    "update_ai_trader":       {"en": "Updating AI trader",          "zh": "正在更新AI交易员"},
    "bind_prompt_to_trader":  {"en": "Binding prompt to trader",    "zh": "正在绑定提示词到交易员"},
    "bind_program_to_trader": {"en": "Binding program to trader",   "zh": "正在绑定程序到交易员"},
    "update_trader_strategy": {"en": "Updating trader strategy",    "zh": "正在更新交易员策略"},
    "update_program_binding": {"en": "Updating program binding",    "zh": "正在更新程序绑定"},
    "update_signal_pool":     {"en": "Updating signal pool",        "zh": "正在更新信号池"},
    "update_prompt_binding":  {"en": "Updating prompt binding",     "zh": "正在更新提示词绑定"},
    "delete_trader":          {"en": "Deleting trader",             "zh": "正在删除交易员"},
    "delete_prompt_template": {"en": "Deleting prompt template",    "zh": "正在删除提示词模板"},
    "delete_signal_definition":{"en": "Deleting signal definition", "zh": "正在删除信号定义"},
    "delete_signal_pool":     {"en": "Deleting signal pool",        "zh": "正在删除信号池"},
    "delete_trading_program": {"en": "Deleting trading program",    "zh": "正在删除交易程序"},
    "delete_prompt_binding":  {"en": "Deleting prompt binding",     "zh": "正在删除提示词绑定"},
    "delete_program_binding": {"en": "Deleting program binding",    "zh": "正在删除程序绑定"},
    "load_skill":             {"en": "Loading skill module",        "zh": "正在加载技能模块"},
    "load_skill_reference":   {"en": "Loading skill reference",     "zh": "正在加载技能参考"},
    "save_memory":            {"en": "Saving memory",               "zh": "正在保存记忆"},
    "call_prompt_ai":         {"en": "Running prompt AI analysis",  "zh": "正在运行提示词AI分析"},
    "call_program_ai":        {"en": "Running program AI analysis", "zh": "正在运行程序AI分析"},
    "call_signal_ai":         {"en": "Running signal AI analysis",  "zh": "正在运行信号AI分析"},
    "call_attribution_ai":    {"en": "Running trade attribution",   "zh": "正在运行交易归因分析"},
}


def _get_ui_language(db_session) -> str:
    """Get UI language from SystemConfig, default to 'en'."""
    from database.models import SystemConfig
    config = db_session.query(SystemConfig).filter(
        SystemConfig.key == "ui_language"
    ).first()
    return config.value if config and config.value in ("en", "zh") else "en"


def _get_tool_label(tool_name: str, lang: str) -> str:
    """Get user-friendly tool label in the specified language."""
    labels = TOOL_LABELS.get(tool_name)
    if labels:
        return labels.get(lang, labels["en"])
    # Fallback: humanize the function name
    return tool_name.replace("_", " ").title()
