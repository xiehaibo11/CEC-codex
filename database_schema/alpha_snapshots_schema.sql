--
-- PostgreSQL database dump
--

\restrict EKaX0s9c77yrYrngqPRyd6BJzit8okuCjUdi30IvgQ21LNXVVkFMhSAA6lmPb39

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
-- Name: hyperliquid_account_snapshots; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hyperliquid_account_snapshots (
    id integer NOT NULL,
    account_id integer NOT NULL,
    environment character varying(20) NOT NULL,
    wallet_address character varying(100),
    total_equity numeric(18,6) NOT NULL,
    available_balance numeric(18,6) NOT NULL,
    used_margin numeric(18,6) NOT NULL,
    maintenance_margin numeric(18,6),
    trigger_event character varying(50) NOT NULL,
    snapshot_data text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
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
-- Name: hyperliquid_trades; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hyperliquid_trades (
    id integer NOT NULL,
    account_id integer NOT NULL,
    environment character varying(20) NOT NULL,
    wallet_address character varying(100),
    symbol character varying(20) NOT NULL,
    side character varying(10) NOT NULL,
    quantity numeric(18,8) NOT NULL,
    price numeric(18,6) NOT NULL,
    leverage integer NOT NULL,
    order_id character varying(100),
    order_status character varying(20) NOT NULL,
    trade_value numeric(18,6) NOT NULL,
    fee numeric(18,6),
    trade_time timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: hyperliquid_trades_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.hyperliquid_trades_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: hyperliquid_trades_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.hyperliquid_trades_id_seq OWNED BY public.hyperliquid_trades.id;


--
-- Name: hyperliquid_account_snapshots id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hyperliquid_account_snapshots ALTER COLUMN id SET DEFAULT nextval('public.hyperliquid_account_snapshots_id_seq'::regclass);


--
-- Name: hyperliquid_trades id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hyperliquid_trades ALTER COLUMN id SET DEFAULT nextval('public.hyperliquid_trades_id_seq'::regclass);


--
-- Name: hyperliquid_account_snapshots hyperliquid_account_snapshots_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hyperliquid_account_snapshots
    ADD CONSTRAINT hyperliquid_account_snapshots_pkey PRIMARY KEY (id);


--
-- Name: hyperliquid_trades hyperliquid_trades_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hyperliquid_trades
    ADD CONSTRAINT hyperliquid_trades_pkey PRIMARY KEY (id);


--
-- Name: ix_hyperliquid_account_snapshots_account_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hyperliquid_account_snapshots_account_id ON public.hyperliquid_account_snapshots USING btree (account_id);


--
-- Name: ix_hyperliquid_account_snapshots_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hyperliquid_account_snapshots_id ON public.hyperliquid_account_snapshots USING btree (id);


--
-- Name: ix_hyperliquid_trades_account_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hyperliquid_trades_account_id ON public.hyperliquid_trades USING btree (account_id);


--
-- Name: ix_hyperliquid_trades_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hyperliquid_trades_id ON public.hyperliquid_trades USING btree (id);


--
-- PostgreSQL database dump complete
--

\unrestrict EKaX0s9c77yrYrngqPRyd6BJzit8okuCjUdi30IvgQ21LNXVVkFMhSAA6lmPb39

