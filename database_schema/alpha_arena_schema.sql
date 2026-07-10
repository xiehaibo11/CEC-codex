--
-- PostgreSQL database dump
--

\restrict ZsmQBpngwAVgz8a0VYGu4Cqh72oZAyPPVhIuKlzgIc6eFJXQ1kGAclf6TtHfjN1

-- Dumped from database version 16.14 (Debian 16.14-1.pgdg13+1)
-- Dumped by pg_dump version 16.14 (Debian 16.14-1.pgdg13+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: account_asset_snapshots; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.account_asset_snapshots (
    id integer NOT NULL,
    account_id integer NOT NULL,
    total_assets numeric(18,6) NOT NULL,
    cash numeric(18,6) NOT NULL,
    positions_value numeric(18,6) NOT NULL,
    trigger_symbol character varying(20),
    trigger_market character varying(10),
    event_time timestamp without time zone NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: account_asset_snapshots_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.account_asset_snapshots_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: account_asset_snapshots_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.account_asset_snapshots_id_seq OWNED BY public.account_asset_snapshots.id;


--
-- Name: account_program_bindings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.account_program_bindings (
    id integer NOT NULL,
    account_id integer NOT NULL,
    program_id integer NOT NULL,
    signal_pool_ids text,
    trigger_interval integer NOT NULL,
    scheduled_trigger_enabled boolean NOT NULL,
    is_active boolean NOT NULL,
    last_trigger_at timestamp without time zone,
    params_override text,
    exchange character varying(20) NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    deleted_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: account_program_bindings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.account_program_bindings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: account_program_bindings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.account_program_bindings_id_seq OWNED BY public.account_program_bindings.id;


--
-- Name: account_prompt_bindings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.account_prompt_bindings (
    id integer NOT NULL,
    account_id integer NOT NULL,
    prompt_template_id integer NOT NULL,
    updated_by character varying(100),
    is_deleted boolean DEFAULT false NOT NULL,
    deleted_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: account_prompt_bindings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.account_prompt_bindings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: account_prompt_bindings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.account_prompt_bindings_id_seq OWNED BY public.account_prompt_bindings.id;


--
-- Name: account_strategy_configs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.account_strategy_configs (
    id integer NOT NULL,
    account_id integer NOT NULL,
    price_threshold double precision NOT NULL,
    trigger_interval integer NOT NULL,
    signal_pool_id integer,
    signal_pool_ids text,
    enabled character varying(10) NOT NULL,
    scheduled_trigger_enabled boolean NOT NULL,
    exchange character varying(20) NOT NULL,
    last_trigger_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: account_strategy_configs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.account_strategy_configs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: account_strategy_configs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.account_strategy_configs_id_seq OWNED BY public.account_strategy_configs.id;


--
-- Name: accounts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.accounts (
    id integer NOT NULL,
    user_id integer NOT NULL,
    version character varying(100) NOT NULL,
    name character varying(100) NOT NULL,
    account_type character varying(20) NOT NULL,
    is_active character varying(10) NOT NULL,
    auto_trading_enabled character varying(10) NOT NULL,
    model character varying(100),
    base_url character varying(500),
    api_key character varying(500),
    initial_capital numeric(18,2) NOT NULL,
    current_cash numeric(18,2) NOT NULL,
    frozen_cash numeric(18,2) NOT NULL,
    hyperliquid_enabled character varying(10) NOT NULL,
    hyperliquid_environment character varying(20),
    hyperliquid_testnet_private_key character varying(500),
    hyperliquid_mainnet_private_key character varying(500),
    max_leverage integer,
    default_leverage integer,
    show_on_dashboard boolean NOT NULL,
    avatar_preset_id integer,
    is_deleted boolean DEFAULT false NOT NULL,
    deleted_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: accounts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.accounts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: accounts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.accounts_id_seq OWNED BY public.accounts.id;


--
-- Name: ai_attribution_conversations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_attribution_conversations (
    id integer NOT NULL,
    user_id integer NOT NULL,
    title character varying(200) NOT NULL,
    compression_points text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: ai_attribution_conversations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ai_attribution_conversations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ai_attribution_conversations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ai_attribution_conversations_id_seq OWNED BY public.ai_attribution_conversations.id;


--
-- Name: ai_attribution_messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_attribution_messages (
    id integer NOT NULL,
    conversation_id integer NOT NULL,
    role character varying(20) NOT NULL,
    content text NOT NULL,
    diagnosis_result text,
    reasoning_snapshot text,
    tool_calls_log text,
    is_complete boolean,
    interrupt_reason text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: ai_attribution_messages_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ai_attribution_messages_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ai_attribution_messages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ai_attribution_messages_id_seq OWNED BY public.ai_attribution_messages.id;


--
-- Name: ai_decision_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_decision_logs (
    id integer NOT NULL,
    account_id integer NOT NULL,
    decision_time timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    reason character varying(1000) NOT NULL,
    operation character varying(10) NOT NULL,
    symbol character varying(20),
    prev_portion numeric(10,6) NOT NULL,
    target_portion numeric(10,6) NOT NULL,
    total_balance numeric(18,2) NOT NULL,
    executed character varying(10) NOT NULL,
    order_id integer,
    prompt_snapshot text,
    reasoning_snapshot text,
    decision_snapshot text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    hyperliquid_environment character varying(20),
    wallet_address character varying(100),
    prompt_template_id integer,
    signal_trigger_id integer,
    hyperliquid_order_id character varying(100),
    tp_order_id character varying(100),
    sl_order_id character varying(100),
    realized_pnl numeric(18,6),
    pnl_updated_at timestamp without time zone,
    decision_source_type character varying(20),
    exchange character varying(20)
);


--
-- Name: ai_decision_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ai_decision_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ai_decision_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ai_decision_logs_id_seq OWNED BY public.ai_decision_logs.id;


--
-- Name: ai_program_conversations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_program_conversations (
    id integer NOT NULL,
    user_id integer NOT NULL,
    program_id integer,
    title character varying(200) NOT NULL,
    compression_points text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: ai_program_conversations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ai_program_conversations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ai_program_conversations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ai_program_conversations_id_seq OWNED BY public.ai_program_conversations.id;


--
-- Name: ai_program_messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_program_messages (
    id integer NOT NULL,
    conversation_id integer NOT NULL,
    role character varying(20) NOT NULL,
    content text NOT NULL,
    code_suggestion text,
    reasoning_snapshot text,
    tool_calls_log text,
    is_complete boolean,
    interrupt_reason text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: ai_program_messages_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ai_program_messages_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ai_program_messages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ai_program_messages_id_seq OWNED BY public.ai_program_messages.id;


--
-- Name: ai_prompt_conversations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_prompt_conversations (
    id integer NOT NULL,
    user_id integer NOT NULL,
    prompt_id integer,
    title character varying(200) NOT NULL,
    compression_points text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: ai_prompt_conversations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ai_prompt_conversations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ai_prompt_conversations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ai_prompt_conversations_id_seq OWNED BY public.ai_prompt_conversations.id;


--
-- Name: ai_prompt_messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_prompt_messages (
    id integer NOT NULL,
    conversation_id integer NOT NULL,
    role character varying(20) NOT NULL,
    content text NOT NULL,
    prompt_result text,
    reasoning_snapshot text,
    tool_calls_log text,
    is_complete boolean,
    interrupt_reason text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT check_ai_prompt_message_role CHECK (((role)::text = ANY ((ARRAY['user'::character varying, 'assistant'::character varying])::text[])))
);


--
-- Name: ai_prompt_messages_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ai_prompt_messages_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ai_prompt_messages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ai_prompt_messages_id_seq OWNED BY public.ai_prompt_messages.id;


--
-- Name: ai_signal_conversations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_signal_conversations (
    id integer NOT NULL,
    user_id integer NOT NULL,
    title character varying(200) NOT NULL,
    compression_points text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: ai_signal_conversations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ai_signal_conversations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ai_signal_conversations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ai_signal_conversations_id_seq OWNED BY public.ai_signal_conversations.id;


--
-- Name: ai_signal_messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_signal_messages (
    id integer NOT NULL,
    conversation_id integer NOT NULL,
    role character varying(20) NOT NULL,
    content text NOT NULL,
    signal_configs text,
    reasoning_snapshot text,
    tool_calls_log text,
    is_complete boolean,
    interrupt_reason text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: ai_signal_messages_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ai_signal_messages_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ai_signal_messages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ai_signal_messages_id_seq OWNED BY public.ai_signal_messages.id;


--
-- Name: backtest_results; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.backtest_results (
    id integer NOT NULL,
    backtest_type character varying(20) NOT NULL,
    binding_id integer,
    prompt_id integer,
    user_id integer,
    config text,
    start_time timestamp without time zone,
    end_time timestamp without time zone,
    initial_balance double precision,
    final_equity double precision,
    total_pnl double precision,
    total_pnl_percent double precision,
    max_drawdown double precision,
    max_drawdown_percent double precision,
    total_triggers integer,
    total_trades integer,
    winning_trades integer,
    losing_trades integer,
    win_rate double precision,
    profit_factor double precision,
    sharpe_ratio double precision,
    equity_curve text,
    execution_time_ms integer,
    status character varying(20),
    error_message text,
    exchange character varying(20),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    completed_at timestamp without time zone
);


--
-- Name: backtest_results_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.backtest_results_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: backtest_results_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.backtest_results_id_seq OWNED BY public.backtest_results.id;


--
-- Name: backtest_trigger_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.backtest_trigger_logs (
    id integer NOT NULL,
    backtest_id integer NOT NULL,
    trigger_index integer NOT NULL,
    trigger_type character varying(20),
    trigger_time timestamp without time zone,
    symbol character varying(20),
    decision_type character varying(20),
    decision_action character varying(20),
    decision_symbol character varying(20),
    decision_side character varying(10),
    decision_size double precision,
    decision_reason text,
    entry_price double precision,
    exit_price double precision,
    pnl double precision,
    fee double precision,
    unrealized_pnl double precision,
    realized_pnl double precision,
    equity_before double precision,
    equity_after double precision,
    decision_input text,
    decision_output text,
    data_queries text,
    execution_logs text,
    execution_error text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: backtest_trigger_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.backtest_trigger_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: backtest_trigger_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.backtest_trigger_logs_id_seq OWNED BY public.backtest_trigger_logs.id;


--
-- Name: binance_account_snapshots; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.binance_account_snapshots (
    id integer NOT NULL,
    account_id integer NOT NULL,
    environment character varying(20) NOT NULL,
    snapshot_time timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    total_wallet_balance numeric(18,6) NOT NULL,
    available_balance numeric(18,6) NOT NULL,
    total_unrealized_profit numeric(18,6) NOT NULL,
    total_margin_balance numeric(18,6) NOT NULL,
    total_initial_margin numeric(18,6),
    total_maint_margin numeric(18,6),
    trigger_event character varying(50),
    snapshot_data text
);


--
-- Name: binance_account_snapshots_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.binance_account_snapshots_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: binance_account_snapshots_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.binance_account_snapshots_id_seq OWNED BY public.binance_account_snapshots.id;


--
-- Name: binance_backfill_tasks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.binance_backfill_tasks (
    id integer NOT NULL,
    symbols character varying(200) NOT NULL,
    status character varying(20) NOT NULL,
    progress integer NOT NULL,
    error_message text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: binance_backfill_tasks_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.binance_backfill_tasks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: binance_backfill_tasks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.binance_backfill_tasks_id_seq OWNED BY public.binance_backfill_tasks.id;


--
-- Name: binance_wallets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.binance_wallets (
    id integer NOT NULL,
    account_id integer NOT NULL,
    environment character varying(20) NOT NULL,
    api_key_encrypted character varying(500) NOT NULL,
    secret_key_encrypted character varying(500) NOT NULL,
    max_leverage integer NOT NULL,
    default_leverage integer NOT NULL,
    is_active character varying(10) NOT NULL,
    rebate_working boolean,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: binance_wallets_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.binance_wallets_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: binance_wallets_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.binance_wallets_id_seq OWNED BY public.binance_wallets.id;


--
-- Name: bot_chat_bindings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bot_chat_bindings (
    id integer NOT NULL,
    platform character varying(20) NOT NULL,
    chat_id character varying(100) NOT NULL,
    username character varying(100),
    display_name character varying(200),
    is_active boolean,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    last_message_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: bot_chat_bindings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.bot_chat_bindings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: bot_chat_bindings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.bot_chat_bindings_id_seq OWNED BY public.bot_chat_bindings.id;


--
-- Name: bot_configs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bot_configs (
    id integer NOT NULL,
    platform character varying(20) NOT NULL,
    bot_token_encrypted text,
    bot_username character varying(100),
    bot_app_id character varying(50),
    status character varying(20) NOT NULL,
    error_message text,
    webhook_url text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: bot_configs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.bot_configs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: bot_configs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.bot_configs_id_seq OWNED BY public.bot_configs.id;


--
-- Name: coinglass_user_keys; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.coinglass_user_keys (
    id integer NOT NULL,
    user_id integer NOT NULL,
    api_key_encrypted text NOT NULL,
    key_masked character varying(32),
    plan_level character varying(50),
    expire_time bigint,
    expired boolean,
    last_validated_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: coinglass_user_keys_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.coinglass_user_keys_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: coinglass_user_keys_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.coinglass_user_keys_id_seq OWNED BY public.coinglass_user_keys.id;


--
-- Name: crypto_klines; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.crypto_klines (
    id integer NOT NULL,
    exchange character varying(20) NOT NULL,
    symbol character varying(20) NOT NULL,
    market character varying(10) NOT NULL,
    period character varying(10) NOT NULL,
    "timestamp" integer NOT NULL,
    datetime_str character varying(50) NOT NULL,
    environment character varying(20) NOT NULL,
    open_price numeric(18,6),
    high_price numeric(18,6),
    low_price numeric(18,6),
    close_price numeric(18,6),
    volume numeric(18,2),
    amount numeric(18,2),
    change numeric(18,6),
    percent numeric(10,4),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: crypto_klines_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.crypto_klines_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: crypto_klines_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.crypto_klines_id_seq OWNED BY public.crypto_klines.id;


--
-- Name: crypto_price_ticks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.crypto_price_ticks (
    id integer NOT NULL,
    symbol character varying(20) NOT NULL,
    market character varying(10) NOT NULL,
    price numeric(18,8) NOT NULL,
    event_time timestamp without time zone NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: crypto_price_ticks_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.crypto_price_ticks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: crypto_price_ticks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.crypto_price_ticks_id_seq OWNED BY public.crypto_price_ticks.id;


--
-- Name: crypto_prices; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.crypto_prices (
    id integer NOT NULL,
    symbol character varying(20) NOT NULL,
    market character varying(10) NOT NULL,
    price numeric(18,6) NOT NULL,
    price_date date NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: crypto_prices_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.crypto_prices_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: crypto_prices_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.crypto_prices_id_seq OWNED BY public.crypto_prices.id;


--
-- Name: custom_factors; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.custom_factors (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    expression text NOT NULL,
    description text,
    category character varying(30) NOT NULL,
    source character varying(20) NOT NULL,
    is_active boolean NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: custom_factors_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.custom_factors_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: custom_factors_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.custom_factors_id_seq OWNED BY public.custom_factors.id;


--
-- Name: event_contract_backtest_runs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.event_contract_backtest_runs (
    id integer NOT NULL,
    symbol character varying(20) NOT NULL,
    exchange character varying(20) NOT NULL,
    environment character varying(20) NOT NULL,
    period character varying(10) NOT NULL,
    start_time timestamp without time zone NOT NULL,
    end_time timestamp without time zone NOT NULL,
    config text,
    summary text,
    equity_curve text,
    status character varying(20) NOT NULL,
    error_message text,
    total_trades integer NOT NULL,
    win_rate double precision NOT NULL,
    final_equity double precision,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: event_contract_backtest_runs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.event_contract_backtest_runs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: event_contract_backtest_runs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.event_contract_backtest_runs_id_seq OWNED BY public.event_contract_backtest_runs.id;


--
-- Name: event_contract_backtest_tasks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.event_contract_backtest_tasks (
    id integer NOT NULL,
    user_id integer,
    run_id integer,
    name character varying(200),
    status character varying(30) DEFAULT 'pending'::character varying NOT NULL,
    symbol character varying(20) NOT NULL,
    exchange character varying(20) DEFAULT 'binance'::character varying NOT NULL,
    environment character varying(20) DEFAULT 'mainnet'::character varying NOT NULL,
    period character varying(10) DEFAULT '1m'::character varying NOT NULL,
    config text,
    progress_pct double precision DEFAULT 0 NOT NULL,
    phase character varying(60),
    processed_decision_bars integer DEFAULT 0 NOT NULL,
    total_decision_bars integer DEFAULT 0 NOT NULL,
    completed_ai_reviews integer DEFAULT 0 NOT NULL,
    expected_ai_reviews integer DEFAULT 0 NOT NULL,
    ai_reviewer_statuses text,
    latest_message text,
    error_message text,
    started_at timestamp without time zone,
    finished_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: event_contract_backtest_tasks_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.event_contract_backtest_tasks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: event_contract_backtest_tasks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.event_contract_backtest_tasks_id_seq OWNED BY public.event_contract_backtest_tasks.id;


--
-- Name: event_contract_paper_bets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.event_contract_paper_bets (
    id integer NOT NULL,
    trader_id integer NOT NULL,
    direction character varying(10) NOT NULL,
    status character varying(20) NOT NULL,
    decision_time timestamp without time zone NOT NULL,
    entry_time timestamp without time zone,
    entry_price double precision,
    expiry_time timestamp without time zone,
    expiry_price double precision,
    result character varying(10),
    pnl double precision,
    stake double precision NOT NULL,
    payout_ratio double precision NOT NULL,
    market_state character varying(50),
    signal_strength double precision,
    reason text,
    analysis_snapshot text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: event_contract_paper_bets_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.event_contract_paper_bets_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: event_contract_paper_bets_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.event_contract_paper_bets_id_seq OWNED BY public.event_contract_paper_bets.id;


--
-- Name: event_contract_paper_traders; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.event_contract_paper_traders (
    id integer NOT NULL,
    name character varying(200) NOT NULL,
    enabled boolean NOT NULL,
    symbol character varying(20) NOT NULL,
    exchange character varying(20) NOT NULL,
    environment character varying(20) NOT NULL,
    config text,
    stake_amount double precision NOT NULL,
    initial_balance double precision NOT NULL,
    current_balance double precision NOT NULL,
    strategy_fingerprint character varying(32),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: event_contract_paper_traders_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.event_contract_paper_traders_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: event_contract_paper_traders_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.event_contract_paper_traders_id_seq OWNED BY public.event_contract_paper_traders.id;


--
-- Name: event_contract_trade_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.event_contract_trade_logs (
    id integer NOT NULL,
    run_id integer NOT NULL,
    trade_index integer NOT NULL,
    symbol character varying(20) NOT NULL,
    direction character varying(10) NOT NULL,
    entry_time timestamp without time zone NOT NULL,
    entry_price double precision NOT NULL,
    expiry_time timestamp without time zone NOT NULL,
    expiry_price double precision NOT NULL,
    result character varying(10) NOT NULL,
    profit_loss double precision NOT NULL,
    signal_strength double precision,
    ai_consensus_rate double precision,
    long_votes integer,
    short_votes integer,
    hold_votes integer,
    market_state character varying(50),
    trap_risk double precision,
    fake_breakout_risk double precision,
    reason text,
    factor_snapshot text,
    ai_decision_snapshot text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    consensus_source character varying(30),
    ai_participated boolean DEFAULT false,
    ai_model character varying(120),
    ai_account_name character varying(120),
    signal_time timestamp without time zone,
    entry_delay_lag_seconds integer DEFAULT 0,
    expiry_lag_seconds integer DEFAULT 0,
    signal_type character varying(50),
    event_signal text
);


--
-- Name: event_contract_trade_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.event_contract_trade_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: event_contract_trade_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.event_contract_trade_logs_id_seq OWNED BY public.event_contract_trade_logs.id;


--
-- Name: event_contract_validation_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.event_contract_validation_log (
    id integer NOT NULL,
    strategy_fingerprint character varying(32) NOT NULL,
    source_run_id integer,
    holdout_run_id integer,
    task_id integer,
    window_start timestamp without time zone,
    window_end timestamp without time zone,
    decided integer,
    wins integer,
    status character varying(20) NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: event_contract_validation_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.event_contract_validation_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: event_contract_validation_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.event_contract_validation_log_id_seq OWNED BY public.event_contract_validation_log.id;


--
-- Name: factor_effectiveness; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.factor_effectiveness (
    id integer NOT NULL,
    exchange character varying(20) NOT NULL,
    factor_name character varying(80) NOT NULL,
    factor_category character varying(30) NOT NULL,
    symbol character varying(20) NOT NULL,
    period character varying(10) NOT NULL,
    forward_period character varying(10) NOT NULL,
    calc_date date NOT NULL,
    lookback_days integer NOT NULL,
    ic_mean double precision,
    ic_std double precision,
    icir double precision,
    win_rate double precision,
    decay_half_life integer,
    sample_count integer,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: factor_effectiveness_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.factor_effectiveness_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: factor_effectiveness_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.factor_effectiveness_id_seq OWNED BY public.factor_effectiveness.id;


--
-- Name: factor_values; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.factor_values (
    id integer NOT NULL,
    exchange character varying(20) NOT NULL,
    symbol character varying(20) NOT NULL,
    period character varying(10) NOT NULL,
    factor_name character varying(80) NOT NULL,
    factor_category character varying(30) NOT NULL,
    "timestamp" integer NOT NULL,
    value double precision,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: factor_values_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.factor_values_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: factor_values_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.factor_values_id_seq OWNED BY public.factor_values.id;


--
-- Name: global_sampling_configs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.global_sampling_configs (
    id integer NOT NULL,
    sampling_interval integer NOT NULL,
    sampling_depth integer NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: global_sampling_configs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.global_sampling_configs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: global_sampling_configs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.global_sampling_configs_id_seq OWNED BY public.global_sampling_configs.id;


--
-- Name: hibt_backfill_tasks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hibt_backfill_tasks (
    id integer NOT NULL,
    symbols character varying(200) NOT NULL,
    status character varying(20) NOT NULL,
    progress integer NOT NULL,
    error_message text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: hibt_backfill_tasks_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.hibt_backfill_tasks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: hibt_backfill_tasks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.hibt_backfill_tasks_id_seq OWNED BY public.hibt_backfill_tasks.id;


--
-- Name: hibt_wallets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hibt_wallets (
    id integer NOT NULL,
    account_id integer NOT NULL,
    environment character varying(20) NOT NULL,
    access_key_encrypted character varying(500) NOT NULL,
    secret_key_encrypted character varying(500) NOT NULL,
    max_leverage integer NOT NULL,
    default_leverage integer NOT NULL,
    is_active character varying(10) NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: hibt_wallets_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.hibt_wallets_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: hibt_wallets_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.hibt_wallets_id_seq OWNED BY public.hibt_wallets.id;


--
-- Name: hyper_ai_conversations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hyper_ai_conversations (
    id integer NOT NULL,
    title character varying(200) NOT NULL,
    is_onboarding boolean,
    summary text,
    compression_points text,
    message_count integer,
    total_tokens integer,
    is_bot_conversation boolean,
    bot_platform character varying(20),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    compressed_at timestamp without time zone
);


--
-- Name: hyper_ai_conversations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.hyper_ai_conversations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: hyper_ai_conversations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.hyper_ai_conversations_id_seq OWNED BY public.hyper_ai_conversations.id;


--
-- Name: hyper_ai_memory; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hyper_ai_memory (
    id integer NOT NULL,
    category character varying(50) NOT NULL,
    content text NOT NULL,
    source character varying(50),
    importance double precision,
    is_active boolean,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: hyper_ai_memory_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.hyper_ai_memory_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: hyper_ai_memory_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.hyper_ai_memory_id_seq OWNED BY public.hyper_ai_memory.id;


--
-- Name: hyper_ai_messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hyper_ai_messages (
    id integer NOT NULL,
    conversation_id integer NOT NULL,
    role character varying(20) NOT NULL,
    content text NOT NULL,
    reasoning_snapshot text,
    tool_calls_log text,
    subagent_calls_log text,
    is_complete boolean,
    interrupt_reason text,
    token_count integer,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: hyper_ai_messages_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.hyper_ai_messages_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: hyper_ai_messages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.hyper_ai_messages_id_seq OWNED BY public.hyper_ai_messages.id;


--
-- Name: hyper_ai_profile; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hyper_ai_profile (
    id integer NOT NULL,
    nickname character varying(100),
    trading_style character varying(50),
    risk_preference character varying(50),
    experience_level character varying(50),
    preferred_symbols text,
    preferred_timeframe character varying(50),
    capital_scale character varying(50),
    onboarding_completed boolean,
    llm_provider character varying(50),
    llm_base_url character varying(500),
    llm_api_key_encrypted text,
    llm_model character varying(100),
    enabled_skills text,
    tool_configs text,
    suggested_questions text,
    suggested_questions_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: hyper_ai_profile_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.hyper_ai_profile_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: hyper_ai_profile_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.hyper_ai_profile_id_seq OWNED BY public.hyper_ai_profile.id;


--
-- Name: hyperliquid_account_snapshots; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hyperliquid_account_snapshots (
    id integer NOT NULL,
    account_id integer NOT NULL,
    environment character varying(20) NOT NULL,
    wallet_address character varying(100),
    snapshot_time timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    total_equity numeric(18,6) NOT NULL,
    available_balance numeric(18,6) NOT NULL,
    used_margin numeric(18,6) NOT NULL,
    maintenance_margin numeric(18,6) NOT NULL,
    trigger_event character varying(50),
    snapshot_data text
);


--
-- Name: hyperliquid_account_snapshots_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.hyperliquid_account_snapshots_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: hyperliquid_account_snapshots_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.hyperliquid_account_snapshots_id_seq OWNED BY public.hyperliquid_account_snapshots.id;


--
-- Name: hyperliquid_backfill_tasks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hyperliquid_backfill_tasks (
    id integer NOT NULL,
    symbols character varying(200) NOT NULL,
    status character varying(20) NOT NULL,
    progress integer NOT NULL,
    error_message text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: hyperliquid_backfill_tasks_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.hyperliquid_backfill_tasks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: hyperliquid_backfill_tasks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.hyperliquid_backfill_tasks_id_seq OWNED BY public.hyperliquid_backfill_tasks.id;


--
-- Name: hyperliquid_exchange_actions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hyperliquid_exchange_actions (
    id integer NOT NULL,
    account_id integer NOT NULL,
    environment character varying(20) NOT NULL,
    wallet_address character varying(100) NOT NULL,
    action_type character varying(50) NOT NULL,
    status character varying(20) NOT NULL,
    symbol character varying(20),
    side character varying(10),
    leverage integer,
    size numeric(24,12),
    price numeric(18,6),
    notional numeric(26,10),
    request_weight integer NOT NULL,
    request_payload text,
    response_payload text,
    error_message text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: hyperliquid_exchange_actions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.hyperliquid_exchange_actions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: hyperliquid_exchange_actions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.hyperliquid_exchange_actions_id_seq OWNED BY public.hyperliquid_exchange_actions.id;


--
-- Name: hyperliquid_positions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hyperliquid_positions (
    id integer NOT NULL,
    account_id integer NOT NULL,
    environment character varying(20) NOT NULL,
    wallet_address character varying(100),
    snapshot_time timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    symbol character varying(20) NOT NULL,
    position_size numeric(18,8) NOT NULL,
    entry_price numeric(18,6) NOT NULL,
    current_price numeric(18,6) NOT NULL,
    position_value numeric(18,6) NOT NULL,
    unrealized_pnl numeric(18,6) NOT NULL,
    margin_used numeric(18,6) NOT NULL,
    liquidation_price numeric(18,6),
    leverage integer NOT NULL,
    order_id integer
);


--
-- Name: hyperliquid_positions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.hyperliquid_positions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: hyperliquid_positions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.hyperliquid_positions_id_seq OWNED BY public.hyperliquid_positions.id;


--
-- Name: hyperliquid_wallets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hyperliquid_wallets (
    id integer NOT NULL,
    account_id integer NOT NULL,
    environment character varying(20) NOT NULL,
    private_key_encrypted character varying(500) NOT NULL,
    wallet_address character varying(100) NOT NULL,
    max_leverage integer NOT NULL,
    default_leverage integer NOT NULL,
    key_type character varying(20) NOT NULL,
    master_wallet_address character varying(100),
    agent_valid_until timestamp without time zone,
    is_active character varying(10) NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: hyperliquid_wallets_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.hyperliquid_wallets_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: hyperliquid_wallets_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.hyperliquid_wallets_id_seq OWNED BY public.hyperliquid_wallets.id;


--
-- Name: kline_ai_analysis_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.kline_ai_analysis_logs (
    id integer NOT NULL,
    user_id integer NOT NULL,
    account_id integer NOT NULL,
    symbol character varying(20) NOT NULL,
    period character varying(10) NOT NULL,
    user_message text,
    model_used character varying(100) NOT NULL,
    prompt_snapshot text,
    analysis_result text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: kline_ai_analysis_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.kline_ai_analysis_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: kline_ai_analysis_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.kline_ai_analysis_logs_id_seq OWNED BY public.kline_ai_analysis_logs.id;


--
-- Name: kline_collection_tasks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.kline_collection_tasks (
    id integer NOT NULL,
    exchange character varying(20) NOT NULL,
    symbol character varying(20) NOT NULL,
    start_time timestamp without time zone NOT NULL,
    end_time timestamp without time zone NOT NULL,
    period character varying(10) NOT NULL,
    status character varying(20) NOT NULL,
    progress integer NOT NULL,
    total_records integer,
    collected_records integer,
    error_message text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: kline_collection_tasks_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.kline_collection_tasks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: kline_collection_tasks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.kline_collection_tasks_id_seq OWNED BY public.kline_collection_tasks.id;


--
-- Name: kline_coverage_stats; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.kline_coverage_stats AS
 SELECT exchange,
    symbol,
    period,
    min("timestamp") AS earliest_time,
    max("timestamp") AS latest_time,
    count(*) AS total_records,
    (max("timestamp") - min("timestamp")) AS time_span_seconds,
    round(((((count(*))::numeric * 60.0) / (NULLIF((max("timestamp") - min("timestamp")), 0))::numeric) * (100)::numeric), 2) AS coverage_percentage
   FROM public.crypto_klines
  WHERE (((period)::text = '1m'::text) AND ("timestamp" IS NOT NULL))
  GROUP BY exchange, symbol, period
 HAVING (count(*) > 1);


--
-- Name: market_asset_metrics; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.market_asset_metrics (
    id integer NOT NULL,
    exchange character varying(20) NOT NULL,
    symbol character varying(20) NOT NULL,
    "timestamp" bigint NOT NULL,
    open_interest numeric(24,8),
    funding_rate numeric(18,8),
    mark_price numeric(18,6),
    oracle_price numeric(18,6),
    mid_price numeric(18,6),
    premium numeric(18,8),
    day_notional_volume numeric(24,6),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: market_asset_metrics_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.market_asset_metrics_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: market_asset_metrics_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.market_asset_metrics_id_seq OWNED BY public.market_asset_metrics.id;


--
-- Name: market_orderbook_snapshots; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.market_orderbook_snapshots (
    id integer NOT NULL,
    exchange character varying(20) NOT NULL,
    symbol character varying(20) NOT NULL,
    "timestamp" bigint NOT NULL,
    best_bid numeric(18,6),
    best_ask numeric(18,6),
    spread numeric(18,6),
    bid_depth_5 numeric(24,8) NOT NULL,
    ask_depth_5 numeric(24,8) NOT NULL,
    bid_depth_10 numeric(24,8) NOT NULL,
    ask_depth_10 numeric(24,8) NOT NULL,
    bid_orders_count integer NOT NULL,
    ask_orders_count integer NOT NULL,
    raw_levels text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: market_orderbook_snapshots_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.market_orderbook_snapshots_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: market_orderbook_snapshots_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.market_orderbook_snapshots_id_seq OWNED BY public.market_orderbook_snapshots.id;


--
-- Name: market_regime_configs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.market_regime_configs (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    is_default boolean,
    rolling_window integer,
    breakout_cvd_z double precision,
    breakout_oi_z double precision,
    breakout_price_atr double precision,
    breakout_taker_high double precision,
    breakout_taker_low double precision,
    absorption_cvd_z double precision,
    absorption_price_atr double precision,
    trap_cvd_z double precision,
    trap_oi_z double precision,
    exhaustion_cvd_z double precision,
    exhaustion_rsi_high double precision,
    exhaustion_rsi_low double precision,
    stop_hunt_range_atr double precision,
    stop_hunt_close_atr double precision,
    noise_cvd_z double precision,
    breakout_body_ratio double precision,
    continuation_cvd_divisor double precision,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: market_regime_configs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.market_regime_configs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: market_regime_configs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.market_regime_configs_id_seq OWNED BY public.market_regime_configs.id;


--
-- Name: market_sentiment_metrics; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.market_sentiment_metrics (
    id integer NOT NULL,
    exchange character varying(20) NOT NULL,
    symbol character varying(20) NOT NULL,
    "timestamp" bigint NOT NULL,
    long_ratio numeric(10,6),
    short_ratio numeric(10,6),
    long_short_ratio numeric(10,6),
    data_type character varying(30) NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: market_sentiment_metrics_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.market_sentiment_metrics_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: market_sentiment_metrics_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.market_sentiment_metrics_id_seq OWNED BY public.market_sentiment_metrics.id;


--
-- Name: market_trades_aggregated; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.market_trades_aggregated (
    id integer NOT NULL,
    exchange character varying(20) NOT NULL,
    symbol character varying(20) NOT NULL,
    "timestamp" bigint NOT NULL,
    taker_buy_volume numeric(24,8) NOT NULL,
    taker_sell_volume numeric(24,8) NOT NULL,
    taker_buy_count integer NOT NULL,
    taker_sell_count integer NOT NULL,
    taker_buy_notional numeric(24,6) NOT NULL,
    taker_sell_notional numeric(24,6) NOT NULL,
    vwap numeric(18,6),
    high_price numeric(18,6),
    low_price numeric(18,6),
    large_buy_notional numeric(24,6) DEFAULT 0 NOT NULL,
    large_sell_notional numeric(24,6) DEFAULT 0 NOT NULL,
    large_buy_count integer DEFAULT 0 NOT NULL,
    large_sell_count integer DEFAULT 0 NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: market_trades_aggregated_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.market_trades_aggregated_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: market_trades_aggregated_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.market_trades_aggregated_id_seq OWNED BY public.market_trades_aggregated.id;


--
-- Name: news_articles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.news_articles (
    id integer NOT NULL,
    source_domain character varying(255) NOT NULL,
    source_url text NOT NULL,
    title character varying(500) NOT NULL,
    summary text,
    published_at timestamp without time zone,
    symbols text,
    sentiment character varying(20),
    sentiment_source character varying(20),
    relevance_score double precision,
    ai_summary text,
    image_url text,
    raw_data text,
    classified boolean NOT NULL,
    fetched_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: news_articles_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.news_articles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: news_articles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.news_articles_id_seq OWNED BY public.news_articles.id;


--
-- Name: orders; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.orders (
    id integer NOT NULL,
    version character varying(100) NOT NULL,
    account_id integer NOT NULL,
    order_no character varying(32) NOT NULL,
    symbol character varying(20) NOT NULL,
    name character varying(100) NOT NULL,
    market character varying(10) NOT NULL,
    side character varying(10) NOT NULL,
    order_type character varying(20) NOT NULL,
    price numeric(18,6),
    quantity numeric(18,8) NOT NULL,
    filled_quantity numeric(18,8) NOT NULL,
    status character varying(20) NOT NULL,
    hyperliquid_environment character varying(20),
    leverage integer,
    margin_mode character varying(20),
    reduce_only character varying(10),
    hyperliquid_order_id character varying(50),
    liquidation_price numeric(18,6),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: orders_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.orders_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: orders_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.orders_id_seq OWNED BY public.orders.id;


--
-- Name: perp_funding; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.perp_funding (
    id integer NOT NULL,
    exchange character varying(20) NOT NULL,
    symbol character varying(20) NOT NULL,
    "timestamp" integer NOT NULL,
    funding_rate numeric(18,8) NOT NULL,
    mark_price numeric(18,6),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: perp_funding_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.perp_funding_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: perp_funding_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.perp_funding_id_seq OWNED BY public.perp_funding.id;


--
-- Name: positions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.positions (
    id integer NOT NULL,
    version character varying(100) NOT NULL,
    account_id integer NOT NULL,
    symbol character varying(20) NOT NULL,
    name character varying(100) NOT NULL,
    market character varying(10) NOT NULL,
    quantity numeric(18,8) NOT NULL,
    available_quantity numeric(18,8) NOT NULL,
    avg_cost numeric(18,6) NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: positions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.positions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: positions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.positions_id_seq OWNED BY public.positions.id;


--
-- Name: price_samples; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.price_samples (
    id integer NOT NULL,
    exchange character varying(20) NOT NULL,
    symbol character varying(20) NOT NULL,
    price numeric(18,8) NOT NULL,
    sample_time timestamp without time zone NOT NULL,
    account_id integer,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: price_samples_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.price_samples_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: price_samples_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.price_samples_id_seq OWNED BY public.price_samples.id;


--
-- Name: program_execution_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.program_execution_logs (
    id integer NOT NULL,
    binding_id integer,
    account_id integer NOT NULL,
    program_id integer,
    program_name character varying(200),
    trigger_type character varying(20) NOT NULL,
    trigger_symbol character varying(20),
    signal_pool_id integer,
    wallet_address character varying(100),
    success boolean NOT NULL,
    decision_action character varying(20),
    decision_symbol character varying(20),
    decision_size_usd double precision,
    decision_leverage integer,
    decision_reason text,
    decision_json text,
    error_message text,
    execution_time_ms double precision,
    market_context text,
    params_snapshot text,
    hyperliquid_order_id character varying(100),
    tp_order_id character varying(100),
    sl_order_id character varying(100),
    environment character varying(20),
    realized_pnl numeric(18,6),
    pnl_updated_at timestamp without time zone,
    exchange character varying(20),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: program_execution_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.program_execution_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: program_execution_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.program_execution_logs_id_seq OWNED BY public.program_execution_logs.id;


--
-- Name: prompt_backtest_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.prompt_backtest_items (
    id integer NOT NULL,
    task_id integer NOT NULL,
    original_decision_log_id integer NOT NULL,
    status character varying(20) NOT NULL,
    error_message text,
    original_operation character varying(20),
    original_symbol character varying(20),
    original_target_portion numeric(10,6),
    original_reasoning text,
    original_decision_json text,
    original_realized_pnl numeric(18,6),
    original_decision_time timestamp without time zone,
    original_prompt_template_name character varying(200),
    modified_prompt text,
    new_operation character varying(20),
    new_symbol character varying(20),
    new_target_portion numeric(10,6),
    new_reasoning text,
    new_decision_json text,
    decision_changed boolean,
    change_type character varying(50),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: prompt_backtest_items_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.prompt_backtest_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: prompt_backtest_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.prompt_backtest_items_id_seq OWNED BY public.prompt_backtest_items.id;


--
-- Name: prompt_backtest_tasks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.prompt_backtest_tasks (
    id integer NOT NULL,
    account_id integer NOT NULL,
    wallet_address character varying(100),
    environment character varying(20),
    name character varying(200),
    status character varying(20) NOT NULL,
    total_count integer NOT NULL,
    completed_count integer NOT NULL,
    failed_count integer NOT NULL,
    replace_rules text,
    started_at timestamp without time zone,
    finished_at timestamp without time zone,
    error_message text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: prompt_backtest_tasks_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.prompt_backtest_tasks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: prompt_backtest_tasks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.prompt_backtest_tasks_id_seq OWNED BY public.prompt_backtest_tasks.id;


--
-- Name: prompt_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.prompt_templates (
    id integer NOT NULL,
    key character varying(100) NOT NULL,
    name character varying(200) NOT NULL,
    description character varying(500),
    template_text text NOT NULL,
    system_template_text text NOT NULL,
    is_system character varying(10) NOT NULL,
    is_deleted character varying(10) NOT NULL,
    deleted_at timestamp without time zone,
    created_by character varying(100) NOT NULL,
    updated_by character varying(100),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: prompt_templates_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.prompt_templates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: prompt_templates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.prompt_templates_id_seq OWNED BY public.prompt_templates.id;


--
-- Name: signal_definitions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.signal_definitions (
    id integer NOT NULL,
    signal_name character varying(100) NOT NULL,
    description text,
    trigger_condition text NOT NULL,
    enabled boolean,
    exchange character varying(20) NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    deleted_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: signal_definitions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.signal_definitions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: signal_definitions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.signal_definitions_id_seq OWNED BY public.signal_definitions.id;


--
-- Name: signal_pools; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.signal_pools (
    id integer NOT NULL,
    pool_name character varying(100) NOT NULL,
    signal_ids text NOT NULL,
    symbols text NOT NULL,
    logic character varying(10),
    enabled boolean,
    exchange character varying(20) NOT NULL,
    source_type character varying(30) NOT NULL,
    source_config text NOT NULL,
    is_deleted boolean DEFAULT false NOT NULL,
    deleted_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: signal_pools_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.signal_pools_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: signal_pools_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.signal_pools_id_seq OWNED BY public.signal_pools.id;


--
-- Name: signal_trigger_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.signal_trigger_logs (
    id integer NOT NULL,
    signal_id integer,
    pool_id integer,
    symbol character varying(20) NOT NULL,
    trigger_value text,
    triggered_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    market_regime text
);


--
-- Name: signal_trigger_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.signal_trigger_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: signal_trigger_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.signal_trigger_logs_id_seq OWNED BY public.signal_trigger_logs.id;


--
-- Name: system_configs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.system_configs (
    id integer NOT NULL,
    key character varying(100) NOT NULL,
    value text,
    description character varying(500),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: system_configs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.system_configs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: system_configs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.system_configs_id_seq OWNED BY public.system_configs.id;


--
-- Name: trader_trigger_config; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.trader_trigger_config (
    trader_id character varying(36) NOT NULL,
    scheduled_enabled boolean,
    scheduled_interval integer,
    signal_pool_id integer,
    signal_pool_ids text,
    last_trigger_time timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: trades; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.trades (
    id integer NOT NULL,
    order_id integer NOT NULL,
    account_id integer NOT NULL,
    symbol character varying(20) NOT NULL,
    name character varying(100) NOT NULL,
    market character varying(10) NOT NULL,
    side character varying(10) NOT NULL,
    price numeric(18,6) NOT NULL,
    quantity numeric(18,8) NOT NULL,
    commission numeric(18,6) NOT NULL,
    trade_time timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    hyperliquid_environment character varying(20)
);


--
-- Name: trades_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.trades_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: trades_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.trades_id_seq OWNED BY public.trades.id;


--
-- Name: trading_configs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.trading_configs (
    id integer NOT NULL,
    version character varying(100) NOT NULL,
    market character varying(10) NOT NULL,
    min_commission double precision NOT NULL,
    commission_rate double precision NOT NULL,
    exchange_rate double precision NOT NULL,
    min_order_quantity integer NOT NULL,
    lot_size integer NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: trading_configs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.trading_configs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: trading_configs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.trading_configs_id_seq OWNED BY public.trading_configs.id;


--
-- Name: trading_programs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.trading_programs (
    id integer NOT NULL,
    user_id integer NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    code text NOT NULL,
    params text,
    icon character varying(50),
    last_backtest_result text,
    last_backtest_at timestamp without time zone,
    is_deleted boolean DEFAULT false NOT NULL,
    deleted_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: trading_programs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.trading_programs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: trading_programs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.trading_programs_id_seq OWNED BY public.trading_programs.id;


--
-- Name: user_auth_sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_auth_sessions (
    id integer NOT NULL,
    user_id integer NOT NULL,
    session_token character varying(64) NOT NULL,
    expires_at timestamp without time zone NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: user_auth_sessions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_auth_sessions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_auth_sessions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_auth_sessions_id_seq OWNED BY public.user_auth_sessions.id;


--
-- Name: user_exchange_config; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_exchange_config (
    id integer NOT NULL,
    user_id integer NOT NULL,
    selected_exchange character varying(20) NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: user_exchange_config_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_exchange_config_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_exchange_config_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_exchange_config_id_seq OWNED BY public.user_exchange_config.id;


--
-- Name: user_subscriptions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_subscriptions (
    id integer NOT NULL,
    user_id integer NOT NULL,
    subscription_type character varying(20) NOT NULL,
    expires_at timestamp without time zone,
    max_sampling_depth integer NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: user_subscriptions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_subscriptions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_subscriptions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_subscriptions_id_seq OWNED BY public.user_subscriptions.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id integer NOT NULL,
    username character varying(50) NOT NULL,
    email character varying(100),
    password_hash character varying(255),
    is_active character varying(10) NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: account_asset_snapshots id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_asset_snapshots ALTER COLUMN id SET DEFAULT nextval('public.account_asset_snapshots_id_seq'::regclass);


--
-- Name: account_program_bindings id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_program_bindings ALTER COLUMN id SET DEFAULT nextval('public.account_program_bindings_id_seq'::regclass);


--
-- Name: account_prompt_bindings id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_prompt_bindings ALTER COLUMN id SET DEFAULT nextval('public.account_prompt_bindings_id_seq'::regclass);


--
-- Name: account_strategy_configs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_strategy_configs ALTER COLUMN id SET DEFAULT nextval('public.account_strategy_configs_id_seq'::regclass);


--
-- Name: accounts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts ALTER COLUMN id SET DEFAULT nextval('public.accounts_id_seq'::regclass);


--
-- Name: ai_attribution_conversations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_attribution_conversations ALTER COLUMN id SET DEFAULT nextval('public.ai_attribution_conversations_id_seq'::regclass);


--
-- Name: ai_attribution_messages id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_attribution_messages ALTER COLUMN id SET DEFAULT nextval('public.ai_attribution_messages_id_seq'::regclass);


--
-- Name: ai_decision_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_decision_logs ALTER COLUMN id SET DEFAULT nextval('public.ai_decision_logs_id_seq'::regclass);


--
-- Name: ai_program_conversations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_program_conversations ALTER COLUMN id SET DEFAULT nextval('public.ai_program_conversations_id_seq'::regclass);


--
-- Name: ai_program_messages id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_program_messages ALTER COLUMN id SET DEFAULT nextval('public.ai_program_messages_id_seq'::regclass);


--
-- Name: ai_prompt_conversations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_prompt_conversations ALTER COLUMN id SET DEFAULT nextval('public.ai_prompt_conversations_id_seq'::regclass);


--
-- Name: ai_prompt_messages id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_prompt_messages ALTER COLUMN id SET DEFAULT nextval('public.ai_prompt_messages_id_seq'::regclass);


--
-- Name: ai_signal_conversations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_signal_conversations ALTER COLUMN id SET DEFAULT nextval('public.ai_signal_conversations_id_seq'::regclass);


--
-- Name: ai_signal_messages id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_signal_messages ALTER COLUMN id SET DEFAULT nextval('public.ai_signal_messages_id_seq'::regclass);


--
-- Name: backtest_results id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.backtest_results ALTER COLUMN id SET DEFAULT nextval('public.backtest_results_id_seq'::regclass);


--
-- Name: backtest_trigger_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.backtest_trigger_logs ALTER COLUMN id SET DEFAULT nextval('public.backtest_trigger_logs_id_seq'::regclass);


--
-- Name: binance_account_snapshots id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.binance_account_snapshots ALTER COLUMN id SET DEFAULT nextval('public.binance_account_snapshots_id_seq'::regclass);


--
-- Name: binance_backfill_tasks id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.binance_backfill_tasks ALTER COLUMN id SET DEFAULT nextval('public.binance_backfill_tasks_id_seq'::regclass);


--
-- Name: binance_wallets id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.binance_wallets ALTER COLUMN id SET DEFAULT nextval('public.binance_wallets_id_seq'::regclass);


--
-- Name: bot_chat_bindings id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bot_chat_bindings ALTER COLUMN id SET DEFAULT nextval('public.bot_chat_bindings_id_seq'::regclass);


--
-- Name: bot_configs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bot_configs ALTER COLUMN id SET DEFAULT nextval('public.bot_configs_id_seq'::regclass);


--
-- Name: coinglass_user_keys id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.coinglass_user_keys ALTER COLUMN id SET DEFAULT nextval('public.coinglass_user_keys_id_seq'::regclass);


--
-- Name: crypto_klines id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.crypto_klines ALTER COLUMN id SET DEFAULT nextval('public.crypto_klines_id_seq'::regclass);


--
-- Name: crypto_price_ticks id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.crypto_price_ticks ALTER COLUMN id SET DEFAULT nextval('public.crypto_price_ticks_id_seq'::regclass);


--
-- Name: crypto_prices id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.crypto_prices ALTER COLUMN id SET DEFAULT nextval('public.crypto_prices_id_seq'::regclass);


--
-- Name: custom_factors id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.custom_factors ALTER COLUMN id SET DEFAULT nextval('public.custom_factors_id_seq'::regclass);


--
-- Name: event_contract_backtest_runs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_contract_backtest_runs ALTER COLUMN id SET DEFAULT nextval('public.event_contract_backtest_runs_id_seq'::regclass);


--
-- Name: event_contract_backtest_tasks id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_contract_backtest_tasks ALTER COLUMN id SET DEFAULT nextval('public.event_contract_backtest_tasks_id_seq'::regclass);


--
-- Name: event_contract_paper_bets id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_contract_paper_bets ALTER COLUMN id SET DEFAULT nextval('public.event_contract_paper_bets_id_seq'::regclass);


--
-- Name: event_contract_paper_traders id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_contract_paper_traders ALTER COLUMN id SET DEFAULT nextval('public.event_contract_paper_traders_id_seq'::regclass);


--
-- Name: event_contract_trade_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_contract_trade_logs ALTER COLUMN id SET DEFAULT nextval('public.event_contract_trade_logs_id_seq'::regclass);


--
-- Name: event_contract_validation_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_contract_validation_log ALTER COLUMN id SET DEFAULT nextval('public.event_contract_validation_log_id_seq'::regclass);


--
-- Name: factor_effectiveness id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.factor_effectiveness ALTER COLUMN id SET DEFAULT nextval('public.factor_effectiveness_id_seq'::regclass);


--
-- Name: factor_values id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.factor_values ALTER COLUMN id SET DEFAULT nextval('public.factor_values_id_seq'::regclass);


--
-- Name: global_sampling_configs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.global_sampling_configs ALTER COLUMN id SET DEFAULT nextval('public.global_sampling_configs_id_seq'::regclass);


--
-- Name: hibt_backfill_tasks id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hibt_backfill_tasks ALTER COLUMN id SET DEFAULT nextval('public.hibt_backfill_tasks_id_seq'::regclass);


--
-- Name: hibt_wallets id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hibt_wallets ALTER COLUMN id SET DEFAULT nextval('public.hibt_wallets_id_seq'::regclass);


--
-- Name: hyper_ai_conversations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hyper_ai_conversations ALTER COLUMN id SET DEFAULT nextval('public.hyper_ai_conversations_id_seq'::regclass);


--
-- Name: hyper_ai_memory id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hyper_ai_memory ALTER COLUMN id SET DEFAULT nextval('public.hyper_ai_memory_id_seq'::regclass);


--
-- Name: hyper_ai_messages id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hyper_ai_messages ALTER COLUMN id SET DEFAULT nextval('public.hyper_ai_messages_id_seq'::regclass);


--
-- Name: hyper_ai_profile id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hyper_ai_profile ALTER COLUMN id SET DEFAULT nextval('public.hyper_ai_profile_id_seq'::regclass);


--
-- Name: hyperliquid_account_snapshots id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hyperliquid_account_snapshots ALTER COLUMN id SET DEFAULT nextval('public.hyperliquid_account_snapshots_id_seq'::regclass);


--
-- Name: hyperliquid_backfill_tasks id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hyperliquid_backfill_tasks ALTER COLUMN id SET DEFAULT nextval('public.hyperliquid_backfill_tasks_id_seq'::regclass);


--
-- Name: hyperliquid_exchange_actions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hyperliquid_exchange_actions ALTER COLUMN id SET DEFAULT nextval('public.hyperliquid_exchange_actions_id_seq'::regclass);


--
-- Name: hyperliquid_positions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hyperliquid_positions ALTER COLUMN id SET DEFAULT nextval('public.hyperliquid_positions_id_seq'::regclass);


--
-- Name: hyperliquid_wallets id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hyperliquid_wallets ALTER COLUMN id SET DEFAULT nextval('public.hyperliquid_wallets_id_seq'::regclass);


--
-- Name: kline_ai_analysis_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kline_ai_analysis_logs ALTER COLUMN id SET DEFAULT nextval('public.kline_ai_analysis_logs_id_seq'::regclass);


--
-- Name: kline_collection_tasks id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kline_collection_tasks ALTER COLUMN id SET DEFAULT nextval('public.kline_collection_tasks_id_seq'::regclass);


--
-- Name: market_asset_metrics id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.market_asset_metrics ALTER COLUMN id SET DEFAULT nextval('public.market_asset_metrics_id_seq'::regclass);


--
-- Name: market_orderbook_snapshots id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.market_orderbook_snapshots ALTER COLUMN id SET DEFAULT nextval('public.market_orderbook_snapshots_id_seq'::regclass);


--
-- Name: market_regime_configs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.market_regime_configs ALTER COLUMN id SET DEFAULT nextval('public.market_regime_configs_id_seq'::regclass);


--
-- Name: market_sentiment_metrics id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.market_sentiment_metrics ALTER COLUMN id SET DEFAULT nextval('public.market_sentiment_metrics_id_seq'::regclass);


--
-- Name: market_trades_aggregated id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.market_trades_aggregated ALTER COLUMN id SET DEFAULT nextval('public.market_trades_aggregated_id_seq'::regclass);


--
-- Name: news_articles id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.news_articles ALTER COLUMN id SET DEFAULT nextval('public.news_articles_id_seq'::regclass);


--
-- Name: orders id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orders ALTER COLUMN id SET DEFAULT nextval('public.orders_id_seq'::regclass);


--
-- Name: perp_funding id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.perp_funding ALTER COLUMN id SET DEFAULT nextval('public.perp_funding_id_seq'::regclass);


--
-- Name: positions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.positions ALTER COLUMN id SET DEFAULT nextval('public.positions_id_seq'::regclass);


--
-- Name: price_samples id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.price_samples ALTER COLUMN id SET DEFAULT nextval('public.price_samples_id_seq'::regclass);


--
-- Name: program_execution_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.program_execution_logs ALTER COLUMN id SET DEFAULT nextval('public.program_execution_logs_id_seq'::regclass);


--
-- Name: prompt_backtest_items id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prompt_backtest_items ALTER COLUMN id SET DEFAULT nextval('public.prompt_backtest_items_id_seq'::regclass);


--
-- Name: prompt_backtest_tasks id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prompt_backtest_tasks ALTER COLUMN id SET DEFAULT nextval('public.prompt_backtest_tasks_id_seq'::regclass);


--
-- Name: prompt_templates id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prompt_templates ALTER COLUMN id SET DEFAULT nextval('public.prompt_templates_id_seq'::regclass);


--
-- Name: signal_definitions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signal_definitions ALTER COLUMN id SET DEFAULT nextval('public.signal_definitions_id_seq'::regclass);


--
-- Name: signal_pools id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signal_pools ALTER COLUMN id SET DEFAULT nextval('public.signal_pools_id_seq'::regclass);


--
-- Name: signal_trigger_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signal_trigger_logs ALTER COLUMN id SET DEFAULT nextval('public.signal_trigger_logs_id_seq'::regclass);


--
-- Name: system_configs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.system_configs ALTER COLUMN id SET DEFAULT nextval('public.system_configs_id_seq'::regclass);


--
-- Name: trades id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trades ALTER COLUMN id SET DEFAULT nextval('public.trades_id_seq'::regclass);


--
-- Name: trading_configs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trading_configs ALTER COLUMN id SET DEFAULT nextval('public.trading_configs_id_seq'::regclass);


--
-- Name: trading_programs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trading_programs ALTER COLUMN id SET DEFAULT nextval('public.trading_programs_id_seq'::regclass);


--
-- Name: user_auth_sessions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_auth_sessions ALTER COLUMN id SET DEFAULT nextval('public.user_auth_sessions_id_seq'::regclass);


--
-- Name: user_exchange_config id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_exchange_config ALTER COLUMN id SET DEFAULT nextval('public.user_exchange_config_id_seq'::regclass);


--
-- Name: user_subscriptions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_subscriptions ALTER COLUMN id SET DEFAULT nextval('public.user_subscriptions_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: account_asset_snapshots account_asset_snapshots_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_asset_snapshots
    ADD CONSTRAINT account_asset_snapshots_pkey PRIMARY KEY (id);


--
-- Name: account_program_bindings account_program_bindings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_program_bindings
    ADD CONSTRAINT account_program_bindings_pkey PRIMARY KEY (id);


--
-- Name: account_prompt_bindings account_prompt_bindings_account_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_prompt_bindings
    ADD CONSTRAINT account_prompt_bindings_account_id_key UNIQUE (account_id);


--
-- Name: account_prompt_bindings account_prompt_bindings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_prompt_bindings
    ADD CONSTRAINT account_prompt_bindings_pkey PRIMARY KEY (id);


--
-- Name: account_strategy_configs account_strategy_configs_account_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_strategy_configs
    ADD CONSTRAINT account_strategy_configs_account_id_key UNIQUE (account_id);


--
-- Name: account_strategy_configs account_strategy_configs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_strategy_configs
    ADD CONSTRAINT account_strategy_configs_pkey PRIMARY KEY (id);


--
-- Name: accounts accounts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts
    ADD CONSTRAINT accounts_pkey PRIMARY KEY (id);


--
-- Name: ai_attribution_conversations ai_attribution_conversations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_attribution_conversations
    ADD CONSTRAINT ai_attribution_conversations_pkey PRIMARY KEY (id);


--
-- Name: ai_attribution_messages ai_attribution_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_attribution_messages
    ADD CONSTRAINT ai_attribution_messages_pkey PRIMARY KEY (id);


--
-- Name: ai_decision_logs ai_decision_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_decision_logs
    ADD CONSTRAINT ai_decision_logs_pkey PRIMARY KEY (id);


--
-- Name: ai_program_conversations ai_program_conversations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_program_conversations
    ADD CONSTRAINT ai_program_conversations_pkey PRIMARY KEY (id);


--
-- Name: ai_program_messages ai_program_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_program_messages
    ADD CONSTRAINT ai_program_messages_pkey PRIMARY KEY (id);


--
-- Name: ai_prompt_conversations ai_prompt_conversations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_prompt_conversations
    ADD CONSTRAINT ai_prompt_conversations_pkey PRIMARY KEY (id);


--
-- Name: ai_prompt_messages ai_prompt_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_prompt_messages
    ADD CONSTRAINT ai_prompt_messages_pkey PRIMARY KEY (id);


--
-- Name: ai_signal_conversations ai_signal_conversations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_signal_conversations
    ADD CONSTRAINT ai_signal_conversations_pkey PRIMARY KEY (id);


--
-- Name: ai_signal_messages ai_signal_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_signal_messages
    ADD CONSTRAINT ai_signal_messages_pkey PRIMARY KEY (id);


--
-- Name: backtest_results backtest_results_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.backtest_results
    ADD CONSTRAINT backtest_results_pkey PRIMARY KEY (id);


--
-- Name: backtest_trigger_logs backtest_trigger_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.backtest_trigger_logs
    ADD CONSTRAINT backtest_trigger_logs_pkey PRIMARY KEY (id);


--
-- Name: binance_account_snapshots binance_account_snapshots_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.binance_account_snapshots
    ADD CONSTRAINT binance_account_snapshots_pkey PRIMARY KEY (id);


--
-- Name: binance_backfill_tasks binance_backfill_tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.binance_backfill_tasks
    ADD CONSTRAINT binance_backfill_tasks_pkey PRIMARY KEY (id);


--
-- Name: binance_wallets binance_wallets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.binance_wallets
    ADD CONSTRAINT binance_wallets_pkey PRIMARY KEY (id);


--
-- Name: bot_chat_bindings bot_chat_bindings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bot_chat_bindings
    ADD CONSTRAINT bot_chat_bindings_pkey PRIMARY KEY (id);


--
-- Name: bot_configs bot_configs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bot_configs
    ADD CONSTRAINT bot_configs_pkey PRIMARY KEY (id);


--
-- Name: bot_configs bot_configs_platform_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bot_configs
    ADD CONSTRAINT bot_configs_platform_key UNIQUE (platform);


--
-- Name: coinglass_user_keys coinglass_user_keys_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.coinglass_user_keys
    ADD CONSTRAINT coinglass_user_keys_pkey PRIMARY KEY (id);


--
-- Name: crypto_klines crypto_klines_exchange_symbol_market_period_timestamp_envir_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.crypto_klines
    ADD CONSTRAINT crypto_klines_exchange_symbol_market_period_timestamp_envir_key UNIQUE (exchange, symbol, market, period, "timestamp", environment);


--
-- Name: crypto_klines crypto_klines_exchange_symbol_market_period_timestamp_environme; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.crypto_klines
    ADD CONSTRAINT crypto_klines_exchange_symbol_market_period_timestamp_environme UNIQUE (exchange, symbol, market, period, "timestamp", environment);


--
-- Name: crypto_klines crypto_klines_exchange_symbol_market_period_timestamp_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.crypto_klines
    ADD CONSTRAINT crypto_klines_exchange_symbol_market_period_timestamp_key UNIQUE (exchange, symbol, market, period, "timestamp");


--
-- Name: crypto_klines crypto_klines_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.crypto_klines
    ADD CONSTRAINT crypto_klines_pkey PRIMARY KEY (id);


--
-- Name: crypto_price_ticks crypto_price_ticks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.crypto_price_ticks
    ADD CONSTRAINT crypto_price_ticks_pkey PRIMARY KEY (id);


--
-- Name: crypto_prices crypto_prices_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.crypto_prices
    ADD CONSTRAINT crypto_prices_pkey PRIMARY KEY (id);


--
-- Name: crypto_prices crypto_prices_symbol_market_price_date_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.crypto_prices
    ADD CONSTRAINT crypto_prices_symbol_market_price_date_key UNIQUE (symbol, market, price_date);


--
-- Name: custom_factors custom_factors_name_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.custom_factors
    ADD CONSTRAINT custom_factors_name_unique UNIQUE (name);


--
-- Name: custom_factors custom_factors_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.custom_factors
    ADD CONSTRAINT custom_factors_pkey PRIMARY KEY (id);


--
-- Name: event_contract_backtest_runs event_contract_backtest_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_contract_backtest_runs
    ADD CONSTRAINT event_contract_backtest_runs_pkey PRIMARY KEY (id);


--
-- Name: event_contract_backtest_tasks event_contract_backtest_tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_contract_backtest_tasks
    ADD CONSTRAINT event_contract_backtest_tasks_pkey PRIMARY KEY (id);


--
-- Name: event_contract_paper_bets event_contract_paper_bets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_contract_paper_bets
    ADD CONSTRAINT event_contract_paper_bets_pkey PRIMARY KEY (id);


--
-- Name: event_contract_paper_traders event_contract_paper_traders_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_contract_paper_traders
    ADD CONSTRAINT event_contract_paper_traders_pkey PRIMARY KEY (id);


--
-- Name: event_contract_trade_logs event_contract_trade_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_contract_trade_logs
    ADD CONSTRAINT event_contract_trade_logs_pkey PRIMARY KEY (id);


--
-- Name: event_contract_validation_log event_contract_validation_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_contract_validation_log
    ADD CONSTRAINT event_contract_validation_log_pkey PRIMARY KEY (id);


--
-- Name: factor_effectiveness factor_effectiveness_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.factor_effectiveness
    ADD CONSTRAINT factor_effectiveness_pkey PRIMARY KEY (id);


--
-- Name: factor_effectiveness factor_effectiveness_unique_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.factor_effectiveness
    ADD CONSTRAINT factor_effectiveness_unique_key UNIQUE (exchange, factor_name, symbol, period, forward_period, calc_date);


--
-- Name: factor_values factor_values_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.factor_values
    ADD CONSTRAINT factor_values_pkey PRIMARY KEY (id);


--
-- Name: factor_values factor_values_unique_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.factor_values
    ADD CONSTRAINT factor_values_unique_key UNIQUE (exchange, symbol, period, factor_name, "timestamp");


--
-- Name: global_sampling_configs global_sampling_configs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.global_sampling_configs
    ADD CONSTRAINT global_sampling_configs_pkey PRIMARY KEY (id);


--
-- Name: hibt_backfill_tasks hibt_backfill_tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hibt_backfill_tasks
    ADD CONSTRAINT hibt_backfill_tasks_pkey PRIMARY KEY (id);


--
-- Name: hibt_wallets hibt_wallets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hibt_wallets
    ADD CONSTRAINT hibt_wallets_pkey PRIMARY KEY (id);


--
-- Name: hyper_ai_conversations hyper_ai_conversations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hyper_ai_conversations
    ADD CONSTRAINT hyper_ai_conversations_pkey PRIMARY KEY (id);


--
-- Name: hyper_ai_memory hyper_ai_memory_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hyper_ai_memory
    ADD CONSTRAINT hyper_ai_memory_pkey PRIMARY KEY (id);


--
-- Name: hyper_ai_messages hyper_ai_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hyper_ai_messages
    ADD CONSTRAINT hyper_ai_messages_pkey PRIMARY KEY (id);


--
-- Name: hyper_ai_profile hyper_ai_profile_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hyper_ai_profile
    ADD CONSTRAINT hyper_ai_profile_pkey PRIMARY KEY (id);


--
-- Name: hyperliquid_account_snapshots hyperliquid_account_snapshots_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hyperliquid_account_snapshots
    ADD CONSTRAINT hyperliquid_account_snapshots_pkey PRIMARY KEY (id);


--
-- Name: hyperliquid_backfill_tasks hyperliquid_backfill_tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hyperliquid_backfill_tasks
    ADD CONSTRAINT hyperliquid_backfill_tasks_pkey PRIMARY KEY (id);


--
-- Name: hyperliquid_exchange_actions hyperliquid_exchange_actions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hyperliquid_exchange_actions
    ADD CONSTRAINT hyperliquid_exchange_actions_pkey PRIMARY KEY (id);


--
-- Name: hyperliquid_positions hyperliquid_positions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hyperliquid_positions
    ADD CONSTRAINT hyperliquid_positions_pkey PRIMARY KEY (id);


--
-- Name: hyperliquid_wallets hyperliquid_wallets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hyperliquid_wallets
    ADD CONSTRAINT hyperliquid_wallets_pkey PRIMARY KEY (id);


--
-- Name: kline_ai_analysis_logs kline_ai_analysis_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kline_ai_analysis_logs
    ADD CONSTRAINT kline_ai_analysis_logs_pkey PRIMARY KEY (id);


--
-- Name: kline_collection_tasks kline_collection_tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kline_collection_tasks
    ADD CONSTRAINT kline_collection_tasks_pkey PRIMARY KEY (id);


--
-- Name: market_asset_metrics market_asset_metrics_exchange_symbol_timestamp_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.market_asset_metrics
    ADD CONSTRAINT market_asset_metrics_exchange_symbol_timestamp_key UNIQUE (exchange, symbol, "timestamp");


--
-- Name: market_asset_metrics market_asset_metrics_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.market_asset_metrics
    ADD CONSTRAINT market_asset_metrics_pkey PRIMARY KEY (id);


--
-- Name: market_orderbook_snapshots market_orderbook_snapshots_exchange_symbol_timestamp_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.market_orderbook_snapshots
    ADD CONSTRAINT market_orderbook_snapshots_exchange_symbol_timestamp_key UNIQUE (exchange, symbol, "timestamp");


--
-- Name: market_orderbook_snapshots market_orderbook_snapshots_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.market_orderbook_snapshots
    ADD CONSTRAINT market_orderbook_snapshots_pkey PRIMARY KEY (id);


--
-- Name: market_regime_configs market_regime_configs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.market_regime_configs
    ADD CONSTRAINT market_regime_configs_pkey PRIMARY KEY (id);


--
-- Name: market_sentiment_metrics market_sentiment_metrics_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.market_sentiment_metrics
    ADD CONSTRAINT market_sentiment_metrics_pkey PRIMARY KEY (id);


--
-- Name: market_sentiment_metrics market_sentiment_metrics_unique_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.market_sentiment_metrics
    ADD CONSTRAINT market_sentiment_metrics_unique_key UNIQUE (exchange, symbol, "timestamp", data_type);


--
-- Name: market_trades_aggregated market_trades_aggregated_exchange_symbol_timestamp_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.market_trades_aggregated
    ADD CONSTRAINT market_trades_aggregated_exchange_symbol_timestamp_key UNIQUE (exchange, symbol, "timestamp");


--
-- Name: market_trades_aggregated market_trades_aggregated_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.market_trades_aggregated
    ADD CONSTRAINT market_trades_aggregated_pkey PRIMARY KEY (id);


--
-- Name: news_articles news_articles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.news_articles
    ADD CONSTRAINT news_articles_pkey PRIMARY KEY (id);


--
-- Name: news_articles news_articles_source_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.news_articles
    ADD CONSTRAINT news_articles_source_unique UNIQUE (source_domain, source_url);


--
-- Name: orders orders_order_no_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_order_no_key UNIQUE (order_no);


--
-- Name: orders orders_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_pkey PRIMARY KEY (id);


--
-- Name: perp_funding perp_funding_exchange_symbol_timestamp_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.perp_funding
    ADD CONSTRAINT perp_funding_exchange_symbol_timestamp_key UNIQUE (exchange, symbol, "timestamp");


--
-- Name: perp_funding perp_funding_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.perp_funding
    ADD CONSTRAINT perp_funding_pkey PRIMARY KEY (id);


--
-- Name: positions positions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.positions
    ADD CONSTRAINT positions_pkey PRIMARY KEY (id);


--
-- Name: price_samples price_samples_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.price_samples
    ADD CONSTRAINT price_samples_pkey PRIMARY KEY (id);


--
-- Name: program_execution_logs program_execution_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.program_execution_logs
    ADD CONSTRAINT program_execution_logs_pkey PRIMARY KEY (id);


--
-- Name: prompt_backtest_items prompt_backtest_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prompt_backtest_items
    ADD CONSTRAINT prompt_backtest_items_pkey PRIMARY KEY (id);


--
-- Name: prompt_backtest_tasks prompt_backtest_tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prompt_backtest_tasks
    ADD CONSTRAINT prompt_backtest_tasks_pkey PRIMARY KEY (id);


--
-- Name: prompt_templates prompt_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prompt_templates
    ADD CONSTRAINT prompt_templates_pkey PRIMARY KEY (id);


--
-- Name: signal_definitions signal_definitions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signal_definitions
    ADD CONSTRAINT signal_definitions_pkey PRIMARY KEY (id);


--
-- Name: signal_pools signal_pools_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signal_pools
    ADD CONSTRAINT signal_pools_pkey PRIMARY KEY (id);


--
-- Name: signal_trigger_logs signal_trigger_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signal_trigger_logs
    ADD CONSTRAINT signal_trigger_logs_pkey PRIMARY KEY (id);


--
-- Name: system_configs system_configs_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.system_configs
    ADD CONSTRAINT system_configs_key_key UNIQUE (key);


--
-- Name: system_configs system_configs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.system_configs
    ADD CONSTRAINT system_configs_pkey PRIMARY KEY (id);


--
-- Name: trader_trigger_config trader_trigger_config_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trader_trigger_config
    ADD CONSTRAINT trader_trigger_config_pkey PRIMARY KEY (trader_id);


--
-- Name: trades trades_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trades
    ADD CONSTRAINT trades_pkey PRIMARY KEY (id);


--
-- Name: trading_configs trading_configs_market_version_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trading_configs
    ADD CONSTRAINT trading_configs_market_version_key UNIQUE (market, version);


--
-- Name: trading_configs trading_configs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trading_configs
    ADD CONSTRAINT trading_configs_pkey PRIMARY KEY (id);


--
-- Name: trading_programs trading_programs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trading_programs
    ADD CONSTRAINT trading_programs_pkey PRIMARY KEY (id);


--
-- Name: binance_wallets uq_binance_wallets_account_environment; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.binance_wallets
    ADD CONSTRAINT uq_binance_wallets_account_environment UNIQUE (account_id, environment);


--
-- Name: crypto_klines uq_crypto_klines_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.crypto_klines
    ADD CONSTRAINT uq_crypto_klines_unique UNIQUE (exchange, symbol, "timestamp", period);


--
-- Name: hibt_wallets uq_hibt_wallets_account_environment; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hibt_wallets
    ADD CONSTRAINT uq_hibt_wallets_account_environment UNIQUE (account_id, environment);


--
-- Name: hyperliquid_wallets uq_hyperliquid_wallets_account_environment; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hyperliquid_wallets
    ADD CONSTRAINT uq_hyperliquid_wallets_account_environment UNIQUE (account_id, environment);


--
-- Name: user_auth_sessions user_auth_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_auth_sessions
    ADD CONSTRAINT user_auth_sessions_pkey PRIMARY KEY (id);


--
-- Name: user_exchange_config user_exchange_config_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_exchange_config
    ADD CONSTRAINT user_exchange_config_pkey PRIMARY KEY (id);


--
-- Name: user_exchange_config user_exchange_config_user_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_exchange_config
    ADD CONSTRAINT user_exchange_config_user_id_key UNIQUE (user_id);


--
-- Name: user_subscriptions user_subscriptions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_subscriptions
    ADD CONSTRAINT user_subscriptions_pkey PRIMARY KEY (id);


--
-- Name: user_subscriptions user_subscriptions_user_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_subscriptions
    ADD CONSTRAINT user_subscriptions_user_id_key UNIQUE (user_id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: users users_username_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_username_key UNIQUE (username);


--
-- Name: idx_ai_attribution_conversations_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_attribution_conversations_user_id ON public.ai_attribution_conversations USING btree (user_id);


--
-- Name: idx_ai_attribution_messages_conversation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_attribution_messages_conversation_id ON public.ai_attribution_messages USING btree (conversation_id);


--
-- Name: idx_ai_prompt_conversations_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_prompt_conversations_created_at ON public.ai_prompt_conversations USING btree (created_at DESC);


--
-- Name: idx_ai_prompt_conversations_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_prompt_conversations_user_id ON public.ai_prompt_conversations USING btree (user_id);


--
-- Name: idx_ai_prompt_messages_conversation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_prompt_messages_conversation_id ON public.ai_prompt_messages USING btree (conversation_id);


--
-- Name: idx_ai_prompt_messages_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_prompt_messages_created_at ON public.ai_prompt_messages USING btree (created_at);


--
-- Name: idx_ai_signal_conversations_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_signal_conversations_user_id ON public.ai_signal_conversations USING btree (user_id);


--
-- Name: idx_ai_signal_messages_conversation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_signal_messages_conversation_id ON public.ai_signal_messages USING btree (conversation_id);


--
-- Name: idx_backtest_items_decision; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_backtest_items_decision ON public.prompt_backtest_items USING btree (original_decision_log_id);


--
-- Name: idx_backtest_items_task; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_backtest_items_task ON public.prompt_backtest_items USING btree (task_id);


--
-- Name: idx_backtest_tasks_account; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_backtest_tasks_account ON public.prompt_backtest_tasks USING btree (account_id);


--
-- Name: idx_backtest_tasks_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_backtest_tasks_created ON public.prompt_backtest_tasks USING btree (created_at);


--
-- Name: idx_backtest_tasks_wallet; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_backtest_tasks_wallet ON public.prompt_backtest_tasks USING btree (wallet_address);


--
-- Name: idx_crypto_klines_environment; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_crypto_klines_environment ON public.crypto_klines USING btree (environment);


--
-- Name: idx_crypto_klines_exchange; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_crypto_klines_exchange ON public.crypto_klines USING btree (exchange);


--
-- Name: idx_crypto_klines_exchange_symbol_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_crypto_klines_exchange_symbol_time ON public.crypto_klines USING btree (exchange, symbol, "timestamp" DESC);


--
-- Name: idx_crypto_klines_symbol_period_env; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_crypto_klines_symbol_period_env ON public.crypto_klines USING btree (symbol, period, environment);


--
-- Name: idx_crypto_klines_timestamp_range; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_crypto_klines_timestamp_range ON public.crypto_klines USING btree ("timestamp" DESC) WHERE (exchange IS NOT NULL);


--
-- Name: idx_event_contract_paper_bets_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_event_contract_paper_bets_created_at ON public.event_contract_paper_bets USING btree (created_at);


--
-- Name: idx_event_contract_paper_bets_decision_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_event_contract_paper_bets_decision_time ON public.event_contract_paper_bets USING btree (decision_time);


--
-- Name: idx_event_contract_paper_bets_expiry_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_event_contract_paper_bets_expiry_time ON public.event_contract_paper_bets USING btree (expiry_time);


--
-- Name: idx_event_contract_paper_bets_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_event_contract_paper_bets_status ON public.event_contract_paper_bets USING btree (status);


--
-- Name: idx_event_contract_paper_bets_trader_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_event_contract_paper_bets_trader_id ON public.event_contract_paper_bets USING btree (trader_id);


--
-- Name: idx_event_contract_paper_traders_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_event_contract_paper_traders_created_at ON public.event_contract_paper_traders USING btree (created_at);


--
-- Name: idx_event_contract_paper_traders_environment; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_event_contract_paper_traders_environment ON public.event_contract_paper_traders USING btree (environment);


--
-- Name: idx_event_contract_paper_traders_exchange; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_event_contract_paper_traders_exchange ON public.event_contract_paper_traders USING btree (exchange);


--
-- Name: idx_event_contract_paper_traders_fingerprint; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_event_contract_paper_traders_fingerprint ON public.event_contract_paper_traders USING btree (strategy_fingerprint);


--
-- Name: idx_event_contract_paper_traders_symbol; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_event_contract_paper_traders_symbol ON public.event_contract_paper_traders USING btree (symbol);


--
-- Name: idx_event_contract_runs_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_event_contract_runs_created ON public.event_contract_backtest_runs USING btree (created_at);


--
-- Name: idx_event_contract_runs_exchange; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_event_contract_runs_exchange ON public.event_contract_backtest_runs USING btree (exchange);


--
-- Name: idx_event_contract_runs_symbol; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_event_contract_runs_symbol ON public.event_contract_backtest_runs USING btree (symbol);


--
-- Name: idx_event_contract_tasks_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_event_contract_tasks_created ON public.event_contract_backtest_tasks USING btree (created_at);


--
-- Name: idx_event_contract_tasks_run; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_event_contract_tasks_run ON public.event_contract_backtest_tasks USING btree (run_id);


--
-- Name: idx_event_contract_tasks_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_event_contract_tasks_status ON public.event_contract_backtest_tasks USING btree (status);


--
-- Name: idx_event_contract_tasks_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_event_contract_tasks_user ON public.event_contract_backtest_tasks USING btree (user_id);


--
-- Name: idx_event_contract_trades_entry; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_event_contract_trades_entry ON public.event_contract_trade_logs USING btree (entry_time);


--
-- Name: idx_event_contract_trades_result; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_event_contract_trades_result ON public.event_contract_trade_logs USING btree (result);


--
-- Name: idx_event_contract_trades_run; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_event_contract_trades_run ON public.event_contract_trade_logs USING btree (run_id);


--
-- Name: idx_event_contract_validation_log_fingerprint; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_event_contract_validation_log_fingerprint ON public.event_contract_validation_log USING btree (strategy_fingerprint);


--
-- Name: idx_event_contract_validation_log_holdout_run_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_event_contract_validation_log_holdout_run_id ON public.event_contract_validation_log USING btree (holdout_run_id);


--
-- Name: idx_event_contract_validation_log_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_event_contract_validation_log_status ON public.event_contract_validation_log USING btree (status);


--
-- Name: idx_event_contract_validation_log_task_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_event_contract_validation_log_task_id ON public.event_contract_validation_log USING btree (task_id);


--
-- Name: idx_event_contract_validation_log_window_end; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_event_contract_validation_log_window_end ON public.event_contract_validation_log USING btree (window_end);


--
-- Name: idx_hyper_ai_memory_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_hyper_ai_memory_category ON public.hyper_ai_memory USING btree (category);


--
-- Name: idx_hyper_ai_memory_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_hyper_ai_memory_created_at ON public.hyper_ai_memory USING btree (created_at);


--
-- Name: idx_hyper_ai_messages_conversation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_hyper_ai_messages_conversation_id ON public.hyper_ai_messages USING btree (conversation_id);


--
-- Name: idx_hyper_ai_messages_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_hyper_ai_messages_created_at ON public.hyper_ai_messages USING btree (created_at);


--
-- Name: idx_hyperliquid_wallets_account_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_hyperliquid_wallets_account_id ON public.hyperliquid_wallets USING btree (account_id);


--
-- Name: idx_kline_tasks_exchange_symbol; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_kline_tasks_exchange_symbol ON public.kline_collection_tasks USING btree (exchange, symbol);


--
-- Name: idx_kline_tasks_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_kline_tasks_status ON public.kline_collection_tasks USING btree (status, created_at DESC);


--
-- Name: idx_signal_definitions_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_signal_definitions_created_at ON public.signal_definitions USING btree (created_at DESC);


--
-- Name: idx_signal_definitions_enabled; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_signal_definitions_enabled ON public.signal_definitions USING btree (enabled);


--
-- Name: idx_signal_pools_enabled; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_signal_pools_enabled ON public.signal_pools USING btree (enabled);


--
-- Name: idx_signal_trigger_logs_pool_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_signal_trigger_logs_pool_id ON public.signal_trigger_logs USING btree (pool_id);


--
-- Name: idx_signal_trigger_logs_signal_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_signal_trigger_logs_signal_id ON public.signal_trigger_logs USING btree (signal_id);


--
-- Name: idx_signal_trigger_logs_symbol; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_signal_trigger_logs_symbol ON public.signal_trigger_logs USING btree (symbol);


--
-- Name: idx_signal_trigger_logs_triggered_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_signal_trigger_logs_triggered_at ON public.signal_trigger_logs USING btree (triggered_at DESC);


--
-- Name: idx_trader_trigger_config_signal_pool_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_trader_trigger_config_signal_pool_id ON public.trader_trigger_config USING btree (signal_pool_id);


--
-- Name: idx_user_exchange_config_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_exchange_config_user_id ON public.user_exchange_config USING btree (user_id);


--
-- Name: ix_account_asset_snapshots_account_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_account_asset_snapshots_account_id ON public.account_asset_snapshots USING btree (account_id);


--
-- Name: ix_account_asset_snapshots_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_account_asset_snapshots_created_at ON public.account_asset_snapshots USING btree (created_at);


--
-- Name: ix_account_asset_snapshots_event_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_account_asset_snapshots_event_time ON public.account_asset_snapshots USING btree (event_time);


--
-- Name: ix_account_asset_snapshots_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_account_asset_snapshots_id ON public.account_asset_snapshots USING btree (id);


--
-- Name: ix_account_program_bindings_account_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_account_program_bindings_account_id ON public.account_program_bindings USING btree (account_id);


--
-- Name: ix_account_program_bindings_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_account_program_bindings_id ON public.account_program_bindings USING btree (id);


--
-- Name: ix_account_program_bindings_program_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_account_program_bindings_program_id ON public.account_program_bindings USING btree (program_id);


--
-- Name: ix_account_prompt_bindings_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_account_prompt_bindings_id ON public.account_prompt_bindings USING btree (id);


--
-- Name: ix_account_strategy_configs_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_account_strategy_configs_id ON public.account_strategy_configs USING btree (id);


--
-- Name: ix_accounts_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_accounts_id ON public.accounts USING btree (id);


--
-- Name: ix_ai_attribution_conversations_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_attribution_conversations_created_at ON public.ai_attribution_conversations USING btree (created_at);


--
-- Name: ix_ai_attribution_conversations_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_attribution_conversations_id ON public.ai_attribution_conversations USING btree (id);


--
-- Name: ix_ai_attribution_conversations_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_attribution_conversations_user_id ON public.ai_attribution_conversations USING btree (user_id);


--
-- Name: ix_ai_attribution_messages_conversation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_attribution_messages_conversation_id ON public.ai_attribution_messages USING btree (conversation_id);


--
-- Name: ix_ai_attribution_messages_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_attribution_messages_created_at ON public.ai_attribution_messages USING btree (created_at);


--
-- Name: ix_ai_attribution_messages_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_attribution_messages_id ON public.ai_attribution_messages USING btree (id);


--
-- Name: ix_ai_decision_logs_decision_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_decision_logs_decision_time ON public.ai_decision_logs USING btree (decision_time);


--
-- Name: ix_ai_decision_logs_hyperliquid_order_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_decision_logs_hyperliquid_order_id ON public.ai_decision_logs USING btree (hyperliquid_order_id);


--
-- Name: ix_ai_decision_logs_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_decision_logs_id ON public.ai_decision_logs USING btree (id);


--
-- Name: ix_ai_decision_logs_prompt_template_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_decision_logs_prompt_template_id ON public.ai_decision_logs USING btree (prompt_template_id);


--
-- Name: ix_ai_decision_logs_signal_trigger_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_decision_logs_signal_trigger_id ON public.ai_decision_logs USING btree (signal_trigger_id);


--
-- Name: ix_ai_decision_logs_wallet_address; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_decision_logs_wallet_address ON public.ai_decision_logs USING btree (wallet_address);


--
-- Name: ix_ai_program_conversations_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_program_conversations_created_at ON public.ai_program_conversations USING btree (created_at);


--
-- Name: ix_ai_program_conversations_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_program_conversations_id ON public.ai_program_conversations USING btree (id);


--
-- Name: ix_ai_program_conversations_program_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_program_conversations_program_id ON public.ai_program_conversations USING btree (program_id);


--
-- Name: ix_ai_program_conversations_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_program_conversations_user_id ON public.ai_program_conversations USING btree (user_id);


--
-- Name: ix_ai_program_messages_conversation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_program_messages_conversation_id ON public.ai_program_messages USING btree (conversation_id);


--
-- Name: ix_ai_program_messages_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_program_messages_created_at ON public.ai_program_messages USING btree (created_at);


--
-- Name: ix_ai_program_messages_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_program_messages_id ON public.ai_program_messages USING btree (id);


--
-- Name: ix_ai_prompt_conversations_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_prompt_conversations_created_at ON public.ai_prompt_conversations USING btree (created_at);


--
-- Name: ix_ai_prompt_conversations_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_prompt_conversations_id ON public.ai_prompt_conversations USING btree (id);


--
-- Name: ix_ai_prompt_conversations_prompt_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_prompt_conversations_prompt_id ON public.ai_prompt_conversations USING btree (prompt_id);


--
-- Name: ix_ai_prompt_conversations_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_prompt_conversations_user_id ON public.ai_prompt_conversations USING btree (user_id);


--
-- Name: ix_ai_prompt_messages_conversation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_prompt_messages_conversation_id ON public.ai_prompt_messages USING btree (conversation_id);


--
-- Name: ix_ai_prompt_messages_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_prompt_messages_created_at ON public.ai_prompt_messages USING btree (created_at);


--
-- Name: ix_ai_prompt_messages_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_prompt_messages_id ON public.ai_prompt_messages USING btree (id);


--
-- Name: ix_ai_signal_conversations_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_signal_conversations_created_at ON public.ai_signal_conversations USING btree (created_at);


--
-- Name: ix_ai_signal_conversations_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_signal_conversations_id ON public.ai_signal_conversations USING btree (id);


--
-- Name: ix_ai_signal_conversations_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_signal_conversations_user_id ON public.ai_signal_conversations USING btree (user_id);


--
-- Name: ix_ai_signal_messages_conversation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_signal_messages_conversation_id ON public.ai_signal_messages USING btree (conversation_id);


--
-- Name: ix_ai_signal_messages_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_signal_messages_created_at ON public.ai_signal_messages USING btree (created_at);


--
-- Name: ix_ai_signal_messages_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_signal_messages_id ON public.ai_signal_messages USING btree (id);


--
-- Name: ix_backtest_results_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_backtest_results_id ON public.backtest_results USING btree (id);


--
-- Name: ix_backtest_trigger_logs_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_backtest_trigger_logs_id ON public.backtest_trigger_logs USING btree (id);


--
-- Name: ix_binance_account_snapshots_account_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_binance_account_snapshots_account_id ON public.binance_account_snapshots USING btree (account_id);


--
-- Name: ix_binance_account_snapshots_environment; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_binance_account_snapshots_environment ON public.binance_account_snapshots USING btree (environment);


--
-- Name: ix_binance_account_snapshots_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_binance_account_snapshots_id ON public.binance_account_snapshots USING btree (id);


--
-- Name: ix_binance_backfill_tasks_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_binance_backfill_tasks_id ON public.binance_backfill_tasks USING btree (id);


--
-- Name: ix_binance_backfill_tasks_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_binance_backfill_tasks_status ON public.binance_backfill_tasks USING btree (status);


--
-- Name: ix_binance_wallets_account_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_binance_wallets_account_id ON public.binance_wallets USING btree (account_id);


--
-- Name: ix_binance_wallets_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_binance_wallets_id ON public.binance_wallets USING btree (id);


--
-- Name: ix_bot_chat_bindings_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_bot_chat_bindings_id ON public.bot_chat_bindings USING btree (id);


--
-- Name: ix_bot_configs_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_bot_configs_id ON public.bot_configs USING btree (id);


--
-- Name: ix_coinglass_user_keys_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_coinglass_user_keys_id ON public.coinglass_user_keys USING btree (id);


--
-- Name: ix_coinglass_user_keys_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_coinglass_user_keys_user_id ON public.coinglass_user_keys USING btree (user_id);


--
-- Name: ix_crypto_klines_environment; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_crypto_klines_environment ON public.crypto_klines USING btree (environment);


--
-- Name: ix_crypto_klines_exchange; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_crypto_klines_exchange ON public.crypto_klines USING btree (exchange);


--
-- Name: ix_crypto_klines_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_crypto_klines_id ON public.crypto_klines USING btree (id);


--
-- Name: ix_crypto_klines_symbol; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_crypto_klines_symbol ON public.crypto_klines USING btree (symbol);


--
-- Name: ix_crypto_klines_timestamp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_crypto_klines_timestamp ON public.crypto_klines USING btree ("timestamp");


--
-- Name: ix_crypto_price_ticks_event_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_crypto_price_ticks_event_time ON public.crypto_price_ticks USING btree (event_time);


--
-- Name: ix_crypto_price_ticks_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_crypto_price_ticks_id ON public.crypto_price_ticks USING btree (id);


--
-- Name: ix_crypto_price_ticks_symbol; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_crypto_price_ticks_symbol ON public.crypto_price_ticks USING btree (symbol);


--
-- Name: ix_crypto_prices_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_crypto_prices_id ON public.crypto_prices USING btree (id);


--
-- Name: ix_crypto_prices_price_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_crypto_prices_price_date ON public.crypto_prices USING btree (price_date);


--
-- Name: ix_crypto_prices_symbol; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_crypto_prices_symbol ON public.crypto_prices USING btree (symbol);


--
-- Name: ix_custom_factors_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_custom_factors_id ON public.custom_factors USING btree (id);


--
-- Name: ix_event_contract_backtest_runs_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_event_contract_backtest_runs_created_at ON public.event_contract_backtest_runs USING btree (created_at);


--
-- Name: ix_event_contract_backtest_runs_end_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_event_contract_backtest_runs_end_time ON public.event_contract_backtest_runs USING btree (end_time);


--
-- Name: ix_event_contract_backtest_runs_environment; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_event_contract_backtest_runs_environment ON public.event_contract_backtest_runs USING btree (environment);


--
-- Name: ix_event_contract_backtest_runs_exchange; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_event_contract_backtest_runs_exchange ON public.event_contract_backtest_runs USING btree (exchange);


--
-- Name: ix_event_contract_backtest_runs_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_event_contract_backtest_runs_id ON public.event_contract_backtest_runs USING btree (id);


--
-- Name: ix_event_contract_backtest_runs_start_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_event_contract_backtest_runs_start_time ON public.event_contract_backtest_runs USING btree (start_time);


--
-- Name: ix_event_contract_backtest_runs_symbol; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_event_contract_backtest_runs_symbol ON public.event_contract_backtest_runs USING btree (symbol);


--
-- Name: ix_event_contract_paper_bets_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_event_contract_paper_bets_created_at ON public.event_contract_paper_bets USING btree (created_at);


--
-- Name: ix_event_contract_paper_bets_decision_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_event_contract_paper_bets_decision_time ON public.event_contract_paper_bets USING btree (decision_time);


--
-- Name: ix_event_contract_paper_bets_expiry_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_event_contract_paper_bets_expiry_time ON public.event_contract_paper_bets USING btree (expiry_time);


--
-- Name: ix_event_contract_paper_bets_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_event_contract_paper_bets_id ON public.event_contract_paper_bets USING btree (id);


--
-- Name: ix_event_contract_paper_bets_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_event_contract_paper_bets_status ON public.event_contract_paper_bets USING btree (status);


--
-- Name: ix_event_contract_paper_bets_trader_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_event_contract_paper_bets_trader_id ON public.event_contract_paper_bets USING btree (trader_id);


--
-- Name: ix_event_contract_paper_traders_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_event_contract_paper_traders_created_at ON public.event_contract_paper_traders USING btree (created_at);


--
-- Name: ix_event_contract_paper_traders_environment; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_event_contract_paper_traders_environment ON public.event_contract_paper_traders USING btree (environment);


--
-- Name: ix_event_contract_paper_traders_exchange; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_event_contract_paper_traders_exchange ON public.event_contract_paper_traders USING btree (exchange);


--
-- Name: ix_event_contract_paper_traders_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_event_contract_paper_traders_id ON public.event_contract_paper_traders USING btree (id);


--
-- Name: ix_event_contract_paper_traders_name; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_event_contract_paper_traders_name ON public.event_contract_paper_traders USING btree (name);


--
-- Name: ix_event_contract_paper_traders_strategy_fingerprint; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_event_contract_paper_traders_strategy_fingerprint ON public.event_contract_paper_traders USING btree (strategy_fingerprint);


--
-- Name: ix_event_contract_paper_traders_symbol; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_event_contract_paper_traders_symbol ON public.event_contract_paper_traders USING btree (symbol);


--
-- Name: ix_event_contract_trade_logs_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_event_contract_trade_logs_created_at ON public.event_contract_trade_logs USING btree (created_at);


--
-- Name: ix_event_contract_trade_logs_entry_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_event_contract_trade_logs_entry_time ON public.event_contract_trade_logs USING btree (entry_time);


--
-- Name: ix_event_contract_trade_logs_expiry_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_event_contract_trade_logs_expiry_time ON public.event_contract_trade_logs USING btree (expiry_time);


--
-- Name: ix_event_contract_trade_logs_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_event_contract_trade_logs_id ON public.event_contract_trade_logs USING btree (id);


--
-- Name: ix_event_contract_trade_logs_result; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_event_contract_trade_logs_result ON public.event_contract_trade_logs USING btree (result);


--
-- Name: ix_event_contract_trade_logs_run_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_event_contract_trade_logs_run_id ON public.event_contract_trade_logs USING btree (run_id);


--
-- Name: ix_event_contract_trade_logs_symbol; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_event_contract_trade_logs_symbol ON public.event_contract_trade_logs USING btree (symbol);


--
-- Name: ix_event_contract_validation_log_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_event_contract_validation_log_created_at ON public.event_contract_validation_log USING btree (created_at);


--
-- Name: ix_event_contract_validation_log_holdout_run_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_event_contract_validation_log_holdout_run_id ON public.event_contract_validation_log USING btree (holdout_run_id);


--
-- Name: ix_event_contract_validation_log_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_event_contract_validation_log_id ON public.event_contract_validation_log USING btree (id);


--
-- Name: ix_event_contract_validation_log_strategy_fingerprint; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_event_contract_validation_log_strategy_fingerprint ON public.event_contract_validation_log USING btree (strategy_fingerprint);


--
-- Name: ix_factor_effectiveness_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_factor_effectiveness_id ON public.factor_effectiveness USING btree (id);


--
-- Name: ix_factor_values_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_factor_values_id ON public.factor_values USING btree (id);


--
-- Name: ix_global_sampling_configs_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_global_sampling_configs_id ON public.global_sampling_configs USING btree (id);


--
-- Name: ix_hibt_backfill_tasks_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hibt_backfill_tasks_id ON public.hibt_backfill_tasks USING btree (id);


--
-- Name: ix_hibt_backfill_tasks_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hibt_backfill_tasks_status ON public.hibt_backfill_tasks USING btree (status);


--
-- Name: ix_hibt_wallets_account_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hibt_wallets_account_id ON public.hibt_wallets USING btree (account_id);


--
-- Name: ix_hibt_wallets_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hibt_wallets_id ON public.hibt_wallets USING btree (id);


--
-- Name: ix_hyper_ai_conversations_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hyper_ai_conversations_created_at ON public.hyper_ai_conversations USING btree (created_at);


--
-- Name: ix_hyper_ai_conversations_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hyper_ai_conversations_id ON public.hyper_ai_conversations USING btree (id);


--
-- Name: ix_hyper_ai_memory_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hyper_ai_memory_category ON public.hyper_ai_memory USING btree (category);


--
-- Name: ix_hyper_ai_memory_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hyper_ai_memory_created_at ON public.hyper_ai_memory USING btree (created_at);


--
-- Name: ix_hyper_ai_memory_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hyper_ai_memory_id ON public.hyper_ai_memory USING btree (id);


--
-- Name: ix_hyper_ai_messages_conversation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hyper_ai_messages_conversation_id ON public.hyper_ai_messages USING btree (conversation_id);


--
-- Name: ix_hyper_ai_messages_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hyper_ai_messages_created_at ON public.hyper_ai_messages USING btree (created_at);


--
-- Name: ix_hyper_ai_messages_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hyper_ai_messages_id ON public.hyper_ai_messages USING btree (id);


--
-- Name: ix_hyper_ai_profile_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hyper_ai_profile_id ON public.hyper_ai_profile USING btree (id);


--
-- Name: ix_hyperliquid_account_snapshots_environment; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hyperliquid_account_snapshots_environment ON public.hyperliquid_account_snapshots USING btree (environment);


--
-- Name: ix_hyperliquid_account_snapshots_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hyperliquid_account_snapshots_id ON public.hyperliquid_account_snapshots USING btree (id);


--
-- Name: ix_hyperliquid_account_snapshots_snapshot_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hyperliquid_account_snapshots_snapshot_time ON public.hyperliquid_account_snapshots USING btree (snapshot_time);


--
-- Name: ix_hyperliquid_account_snapshots_wallet_address; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hyperliquid_account_snapshots_wallet_address ON public.hyperliquid_account_snapshots USING btree (wallet_address);


--
-- Name: ix_hyperliquid_backfill_tasks_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hyperliquid_backfill_tasks_id ON public.hyperliquid_backfill_tasks USING btree (id);


--
-- Name: ix_hyperliquid_backfill_tasks_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hyperliquid_backfill_tasks_status ON public.hyperliquid_backfill_tasks USING btree (status);


--
-- Name: ix_hyperliquid_exchange_actions_account_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hyperliquid_exchange_actions_account_id ON public.hyperliquid_exchange_actions USING btree (account_id);


--
-- Name: ix_hyperliquid_exchange_actions_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hyperliquid_exchange_actions_created_at ON public.hyperliquid_exchange_actions USING btree (created_at);


--
-- Name: ix_hyperliquid_exchange_actions_environment; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hyperliquid_exchange_actions_environment ON public.hyperliquid_exchange_actions USING btree (environment);


--
-- Name: ix_hyperliquid_exchange_actions_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hyperliquid_exchange_actions_id ON public.hyperliquid_exchange_actions USING btree (id);


--
-- Name: ix_hyperliquid_exchange_actions_wallet_address; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hyperliquid_exchange_actions_wallet_address ON public.hyperliquid_exchange_actions USING btree (wallet_address);


--
-- Name: ix_hyperliquid_positions_environment; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hyperliquid_positions_environment ON public.hyperliquid_positions USING btree (environment);


--
-- Name: ix_hyperliquid_positions_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hyperliquid_positions_id ON public.hyperliquid_positions USING btree (id);


--
-- Name: ix_hyperliquid_positions_snapshot_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hyperliquid_positions_snapshot_time ON public.hyperliquid_positions USING btree (snapshot_time);


--
-- Name: ix_hyperliquid_positions_wallet_address; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hyperliquid_positions_wallet_address ON public.hyperliquid_positions USING btree (wallet_address);


--
-- Name: ix_hyperliquid_wallets_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hyperliquid_wallets_id ON public.hyperliquid_wallets USING btree (id);


--
-- Name: ix_hyperliquid_wallets_wallet_address; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hyperliquid_wallets_wallet_address ON public.hyperliquid_wallets USING btree (wallet_address);


--
-- Name: ix_kline_ai_analysis_logs_account_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_kline_ai_analysis_logs_account_id ON public.kline_ai_analysis_logs USING btree (account_id);


--
-- Name: ix_kline_ai_analysis_logs_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_kline_ai_analysis_logs_created_at ON public.kline_ai_analysis_logs USING btree (created_at);


--
-- Name: ix_kline_ai_analysis_logs_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_kline_ai_analysis_logs_id ON public.kline_ai_analysis_logs USING btree (id);


--
-- Name: ix_kline_ai_analysis_logs_symbol; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_kline_ai_analysis_logs_symbol ON public.kline_ai_analysis_logs USING btree (symbol);


--
-- Name: ix_kline_ai_analysis_logs_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_kline_ai_analysis_logs_user_id ON public.kline_ai_analysis_logs USING btree (user_id);


--
-- Name: ix_kline_collection_tasks_exchange; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_kline_collection_tasks_exchange ON public.kline_collection_tasks USING btree (exchange);


--
-- Name: ix_kline_collection_tasks_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_kline_collection_tasks_id ON public.kline_collection_tasks USING btree (id);


--
-- Name: ix_kline_collection_tasks_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_kline_collection_tasks_status ON public.kline_collection_tasks USING btree (status);


--
-- Name: ix_kline_collection_tasks_symbol; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_kline_collection_tasks_symbol ON public.kline_collection_tasks USING btree (symbol);


--
-- Name: ix_market_asset_metrics_exchange; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_market_asset_metrics_exchange ON public.market_asset_metrics USING btree (exchange);


--
-- Name: ix_market_asset_metrics_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_market_asset_metrics_id ON public.market_asset_metrics USING btree (id);


--
-- Name: ix_market_asset_metrics_symbol; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_market_asset_metrics_symbol ON public.market_asset_metrics USING btree (symbol);


--
-- Name: ix_market_asset_metrics_timestamp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_market_asset_metrics_timestamp ON public.market_asset_metrics USING btree ("timestamp");


--
-- Name: ix_market_orderbook_snapshots_exchange; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_market_orderbook_snapshots_exchange ON public.market_orderbook_snapshots USING btree (exchange);


--
-- Name: ix_market_orderbook_snapshots_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_market_orderbook_snapshots_id ON public.market_orderbook_snapshots USING btree (id);


--
-- Name: ix_market_orderbook_snapshots_symbol; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_market_orderbook_snapshots_symbol ON public.market_orderbook_snapshots USING btree (symbol);


--
-- Name: ix_market_orderbook_snapshots_timestamp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_market_orderbook_snapshots_timestamp ON public.market_orderbook_snapshots USING btree ("timestamp");


--
-- Name: ix_market_regime_configs_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_market_regime_configs_id ON public.market_regime_configs USING btree (id);


--
-- Name: ix_market_sentiment_metrics_exchange; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_market_sentiment_metrics_exchange ON public.market_sentiment_metrics USING btree (exchange);


--
-- Name: ix_market_sentiment_metrics_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_market_sentiment_metrics_id ON public.market_sentiment_metrics USING btree (id);


--
-- Name: ix_market_sentiment_metrics_symbol; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_market_sentiment_metrics_symbol ON public.market_sentiment_metrics USING btree (symbol);


--
-- Name: ix_market_sentiment_metrics_timestamp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_market_sentiment_metrics_timestamp ON public.market_sentiment_metrics USING btree ("timestamp");


--
-- Name: ix_market_trades_aggregated_exchange; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_market_trades_aggregated_exchange ON public.market_trades_aggregated USING btree (exchange);


--
-- Name: ix_market_trades_aggregated_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_market_trades_aggregated_id ON public.market_trades_aggregated USING btree (id);


--
-- Name: ix_market_trades_aggregated_symbol; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_market_trades_aggregated_symbol ON public.market_trades_aggregated USING btree (symbol);


--
-- Name: ix_market_trades_aggregated_timestamp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_market_trades_aggregated_timestamp ON public.market_trades_aggregated USING btree ("timestamp");


--
-- Name: ix_news_articles_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_news_articles_id ON public.news_articles USING btree (id);


--
-- Name: ix_news_articles_published_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_news_articles_published_at ON public.news_articles USING btree (published_at);


--
-- Name: ix_news_articles_source_domain; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_news_articles_source_domain ON public.news_articles USING btree (source_domain);


--
-- Name: ix_orders_account_id_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_orders_account_id_status ON public.orders USING btree (account_id, status);


--
-- Name: ix_orders_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_orders_id ON public.orders USING btree (id);


--
-- Name: ix_perp_funding_exchange; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_perp_funding_exchange ON public.perp_funding USING btree (exchange);


--
-- Name: ix_perp_funding_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_perp_funding_id ON public.perp_funding USING btree (id);


--
-- Name: ix_perp_funding_symbol; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_perp_funding_symbol ON public.perp_funding USING btree (symbol);


--
-- Name: ix_perp_funding_timestamp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_perp_funding_timestamp ON public.perp_funding USING btree ("timestamp");


--
-- Name: ix_positions_account_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_positions_account_id ON public.positions USING btree (account_id);


--
-- Name: ix_positions_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_positions_id ON public.positions USING btree (id);


--
-- Name: ix_price_samples_exchange; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_price_samples_exchange ON public.price_samples USING btree (exchange);


--
-- Name: ix_price_samples_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_price_samples_id ON public.price_samples USING btree (id);


--
-- Name: ix_price_samples_sample_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_price_samples_sample_time ON public.price_samples USING btree (sample_time);


--
-- Name: ix_price_samples_symbol; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_price_samples_symbol ON public.price_samples USING btree (symbol);


--
-- Name: ix_program_execution_logs_account_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_program_execution_logs_account_id ON public.program_execution_logs USING btree (account_id);


--
-- Name: ix_program_execution_logs_binding_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_program_execution_logs_binding_id ON public.program_execution_logs USING btree (binding_id);


--
-- Name: ix_program_execution_logs_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_program_execution_logs_created_at ON public.program_execution_logs USING btree (created_at);


--
-- Name: ix_program_execution_logs_environment; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_program_execution_logs_environment ON public.program_execution_logs USING btree (environment);


--
-- Name: ix_program_execution_logs_hyperliquid_order_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_program_execution_logs_hyperliquid_order_id ON public.program_execution_logs USING btree (hyperliquid_order_id);


--
-- Name: ix_program_execution_logs_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_program_execution_logs_id ON public.program_execution_logs USING btree (id);


--
-- Name: ix_program_execution_logs_program_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_program_execution_logs_program_id ON public.program_execution_logs USING btree (program_id);


--
-- Name: ix_prompt_backtest_items_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_prompt_backtest_items_id ON public.prompt_backtest_items USING btree (id);


--
-- Name: ix_prompt_backtest_items_task_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_prompt_backtest_items_task_id ON public.prompt_backtest_items USING btree (task_id);


--
-- Name: ix_prompt_backtest_tasks_account_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_prompt_backtest_tasks_account_id ON public.prompt_backtest_tasks USING btree (account_id);


--
-- Name: ix_prompt_backtest_tasks_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_prompt_backtest_tasks_created_at ON public.prompt_backtest_tasks USING btree (created_at);


--
-- Name: ix_prompt_backtest_tasks_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_prompt_backtest_tasks_id ON public.prompt_backtest_tasks USING btree (id);


--
-- Name: ix_prompt_backtest_tasks_wallet_address; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_prompt_backtest_tasks_wallet_address ON public.prompt_backtest_tasks USING btree (wallet_address);


--
-- Name: ix_prompt_templates_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_prompt_templates_id ON public.prompt_templates USING btree (id);


--
-- Name: ix_prompt_templates_key; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_prompt_templates_key ON public.prompt_templates USING btree (key);


--
-- Name: ix_signal_definitions_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_signal_definitions_id ON public.signal_definitions USING btree (id);


--
-- Name: ix_signal_pools_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_signal_pools_id ON public.signal_pools USING btree (id);


--
-- Name: ix_signal_trigger_logs_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_signal_trigger_logs_id ON public.signal_trigger_logs USING btree (id);


--
-- Name: ix_system_configs_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_system_configs_id ON public.system_configs USING btree (id);


--
-- Name: ix_trades_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_trades_id ON public.trades USING btree (id);


--
-- Name: ix_trading_configs_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_trading_configs_id ON public.trading_configs USING btree (id);


--
-- Name: ix_trading_programs_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_trading_programs_id ON public.trading_programs USING btree (id);


--
-- Name: ix_trading_programs_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_trading_programs_user_id ON public.trading_programs USING btree (user_id);


--
-- Name: ix_user_auth_sessions_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_auth_sessions_id ON public.user_auth_sessions USING btree (id);


--
-- Name: ix_user_auth_sessions_session_token; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_user_auth_sessions_session_token ON public.user_auth_sessions USING btree (session_token);


--
-- Name: ix_user_exchange_config_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_exchange_config_id ON public.user_exchange_config USING btree (id);


--
-- Name: ix_user_subscriptions_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_subscriptions_id ON public.user_subscriptions USING btree (id);


--
-- Name: ix_users_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_id ON public.users USING btree (id);


--
-- Name: account_asset_snapshots account_asset_snapshots_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_asset_snapshots
    ADD CONSTRAINT account_asset_snapshots_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id);


--
-- Name: account_program_bindings account_program_bindings_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_program_bindings
    ADD CONSTRAINT account_program_bindings_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id);


--
-- Name: account_program_bindings account_program_bindings_program_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_program_bindings
    ADD CONSTRAINT account_program_bindings_program_id_fkey FOREIGN KEY (program_id) REFERENCES public.trading_programs(id);


--
-- Name: account_prompt_bindings account_prompt_bindings_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_prompt_bindings
    ADD CONSTRAINT account_prompt_bindings_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id);


--
-- Name: account_prompt_bindings account_prompt_bindings_prompt_template_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_prompt_bindings
    ADD CONSTRAINT account_prompt_bindings_prompt_template_id_fkey FOREIGN KEY (prompt_template_id) REFERENCES public.prompt_templates(id);


--
-- Name: account_strategy_configs account_strategy_configs_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_strategy_configs
    ADD CONSTRAINT account_strategy_configs_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id);


--
-- Name: accounts accounts_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts
    ADD CONSTRAINT accounts_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: ai_attribution_conversations ai_attribution_conversations_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_attribution_conversations
    ADD CONSTRAINT ai_attribution_conversations_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: ai_attribution_messages ai_attribution_messages_conversation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_attribution_messages
    ADD CONSTRAINT ai_attribution_messages_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.ai_attribution_conversations(id);


--
-- Name: ai_decision_logs ai_decision_logs_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_decision_logs
    ADD CONSTRAINT ai_decision_logs_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id);


--
-- Name: ai_decision_logs ai_decision_logs_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_decision_logs
    ADD CONSTRAINT ai_decision_logs_order_id_fkey FOREIGN KEY (order_id) REFERENCES public.orders(id);


--
-- Name: ai_program_conversations ai_program_conversations_program_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_program_conversations
    ADD CONSTRAINT ai_program_conversations_program_id_fkey FOREIGN KEY (program_id) REFERENCES public.trading_programs(id);


--
-- Name: ai_program_conversations ai_program_conversations_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_program_conversations
    ADD CONSTRAINT ai_program_conversations_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: ai_program_messages ai_program_messages_conversation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_program_messages
    ADD CONSTRAINT ai_program_messages_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.ai_program_conversations(id);


--
-- Name: ai_prompt_conversations ai_prompt_conversations_prompt_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_prompt_conversations
    ADD CONSTRAINT ai_prompt_conversations_prompt_id_fkey FOREIGN KEY (prompt_id) REFERENCES public.prompt_templates(id);


--
-- Name: ai_prompt_conversations ai_prompt_conversations_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_prompt_conversations
    ADD CONSTRAINT ai_prompt_conversations_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: ai_prompt_messages ai_prompt_messages_conversation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_prompt_messages
    ADD CONSTRAINT ai_prompt_messages_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.ai_prompt_conversations(id);


--
-- Name: ai_signal_conversations ai_signal_conversations_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_signal_conversations
    ADD CONSTRAINT ai_signal_conversations_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: ai_signal_messages ai_signal_messages_conversation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_signal_messages
    ADD CONSTRAINT ai_signal_messages_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.ai_signal_conversations(id);


--
-- Name: backtest_results backtest_results_binding_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.backtest_results
    ADD CONSTRAINT backtest_results_binding_id_fkey FOREIGN KEY (binding_id) REFERENCES public.account_program_bindings(id);


--
-- Name: backtest_results backtest_results_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.backtest_results
    ADD CONSTRAINT backtest_results_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: backtest_trigger_logs backtest_trigger_logs_backtest_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.backtest_trigger_logs
    ADD CONSTRAINT backtest_trigger_logs_backtest_id_fkey FOREIGN KEY (backtest_id) REFERENCES public.backtest_results(id) ON DELETE CASCADE;


--
-- Name: binance_account_snapshots binance_account_snapshots_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.binance_account_snapshots
    ADD CONSTRAINT binance_account_snapshots_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id);


--
-- Name: binance_wallets binance_wallets_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.binance_wallets
    ADD CONSTRAINT binance_wallets_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id);


--
-- Name: coinglass_user_keys coinglass_user_keys_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.coinglass_user_keys
    ADD CONSTRAINT coinglass_user_keys_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: event_contract_backtest_tasks event_contract_backtest_tasks_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_contract_backtest_tasks
    ADD CONSTRAINT event_contract_backtest_tasks_run_id_fkey FOREIGN KEY (run_id) REFERENCES public.event_contract_backtest_runs(id) ON DELETE SET NULL;


--
-- Name: event_contract_backtest_tasks event_contract_backtest_tasks_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_contract_backtest_tasks
    ADD CONSTRAINT event_contract_backtest_tasks_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: event_contract_paper_bets event_contract_paper_bets_trader_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_contract_paper_bets
    ADD CONSTRAINT event_contract_paper_bets_trader_id_fkey FOREIGN KEY (trader_id) REFERENCES public.event_contract_paper_traders(id) ON DELETE CASCADE;


--
-- Name: event_contract_trade_logs event_contract_trade_logs_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_contract_trade_logs
    ADD CONSTRAINT event_contract_trade_logs_run_id_fkey FOREIGN KEY (run_id) REFERENCES public.event_contract_backtest_runs(id) ON DELETE CASCADE;


--
-- Name: hibt_wallets hibt_wallets_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hibt_wallets
    ADD CONSTRAINT hibt_wallets_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id);


--
-- Name: hyper_ai_messages hyper_ai_messages_conversation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hyper_ai_messages
    ADD CONSTRAINT hyper_ai_messages_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.hyper_ai_conversations(id);


--
-- Name: hyperliquid_account_snapshots hyperliquid_account_snapshots_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hyperliquid_account_snapshots
    ADD CONSTRAINT hyperliquid_account_snapshots_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id);


--
-- Name: hyperliquid_exchange_actions hyperliquid_exchange_actions_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hyperliquid_exchange_actions
    ADD CONSTRAINT hyperliquid_exchange_actions_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id);


--
-- Name: hyperliquid_positions hyperliquid_positions_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hyperliquid_positions
    ADD CONSTRAINT hyperliquid_positions_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id);


--
-- Name: hyperliquid_positions hyperliquid_positions_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hyperliquid_positions
    ADD CONSTRAINT hyperliquid_positions_order_id_fkey FOREIGN KEY (order_id) REFERENCES public.orders(id);


--
-- Name: hyperliquid_wallets hyperliquid_wallets_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hyperliquid_wallets
    ADD CONSTRAINT hyperliquid_wallets_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id);


--
-- Name: kline_ai_analysis_logs kline_ai_analysis_logs_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kline_ai_analysis_logs
    ADD CONSTRAINT kline_ai_analysis_logs_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id);


--
-- Name: kline_ai_analysis_logs kline_ai_analysis_logs_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.kline_ai_analysis_logs
    ADD CONSTRAINT kline_ai_analysis_logs_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: orders orders_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id);


--
-- Name: positions positions_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.positions
    ADD CONSTRAINT positions_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id);


--
-- Name: price_samples price_samples_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.price_samples
    ADD CONSTRAINT price_samples_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id);


--
-- Name: program_execution_logs program_execution_logs_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.program_execution_logs
    ADD CONSTRAINT program_execution_logs_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id);


--
-- Name: program_execution_logs program_execution_logs_binding_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.program_execution_logs
    ADD CONSTRAINT program_execution_logs_binding_id_fkey FOREIGN KEY (binding_id) REFERENCES public.account_program_bindings(id) ON DELETE SET NULL;


--
-- Name: program_execution_logs program_execution_logs_program_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.program_execution_logs
    ADD CONSTRAINT program_execution_logs_program_id_fkey FOREIGN KEY (program_id) REFERENCES public.trading_programs(id) ON DELETE SET NULL;


--
-- Name: prompt_backtest_items prompt_backtest_items_original_decision_log_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prompt_backtest_items
    ADD CONSTRAINT prompt_backtest_items_original_decision_log_id_fkey FOREIGN KEY (original_decision_log_id) REFERENCES public.ai_decision_logs(id);


--
-- Name: prompt_backtest_items prompt_backtest_items_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prompt_backtest_items
    ADD CONSTRAINT prompt_backtest_items_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.prompt_backtest_tasks(id);


--
-- Name: prompt_backtest_tasks prompt_backtest_tasks_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prompt_backtest_tasks
    ADD CONSTRAINT prompt_backtest_tasks_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id);


--
-- Name: trades trades_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trades
    ADD CONSTRAINT trades_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id);


--
-- Name: trades trades_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trades
    ADD CONSTRAINT trades_order_id_fkey FOREIGN KEY (order_id) REFERENCES public.orders(id);


--
-- Name: trading_programs trading_programs_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trading_programs
    ADD CONSTRAINT trading_programs_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: user_auth_sessions user_auth_sessions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_auth_sessions
    ADD CONSTRAINT user_auth_sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: user_exchange_config user_exchange_config_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_exchange_config
    ADD CONSTRAINT user_exchange_config_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: user_subscriptions user_subscriptions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_subscriptions
    ADD CONSTRAINT user_subscriptions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- PostgreSQL database dump complete
--

\unrestrict ZsmQBpngwAVgz8a0VYGu4Cqh72oZAyPPVhIuKlzgIc6eFJXQ1kGAclf6TtHfjN1

