--
-- PostgreSQL database dump
--

\restrict jjoKk8MKGuGTTOQmBp6GoSDdP7BMF6Nm9KuttjoO0qD3aSE2cESF7MMcW9tPeQe

-- Dumped from database version 17.6
-- Dumped by pg_dump version 17.6

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

DROP DATABASE IF EXISTS bsiaw;
--
-- Name: bsiaw; Type: DATABASE; Schema: -; Owner: postgres
--

CREATE DATABASE bsiaw WITH TEMPLATE = template0 ENCODING = 'UTF8' LOCALE_PROVIDER = libc LC_COLLATE = 'C' LC_CTYPE = 'C.UTF-8';


ALTER DATABASE bsiaw OWNER TO postgres;

\unrestrict jjoKk8MKGuGTTOQmBp6GoSDdP7BMF6Nm9KuttjoO0qD3aSE2cESF7MMcW9tPeQe
\connect bsiaw
\restrict jjoKk8MKGuGTTOQmBp6GoSDdP7BMF6Nm9KuttjoO0qD3aSE2cESF7MMcW9tPeQe

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
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
-- Name: sessions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.sessions (
    session_key character varying(32) NOT NULL,
    valid_until timestamp without time zone NOT NULL,
    user_id integer
);


ALTER TABLE public.sessions OWNER TO postgres;

--
-- Name: users; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.users (
    id bigint NOT NULL,
    login character varying(32),
    email text NOT NULL UNIQUE,
    password_hash character varying(64),
    password_salt character varying(16)
);


ALTER TABLE public.users OWNER TO postgres;

--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.users_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.users_id_seq OWNER TO postgres;

--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Data for Name: sessions; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.sessions (session_key, valid_until, user_id) FROM stdin;
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: postgres
--

--
-- Name: users_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.users_id_seq', 1, false);


--
-- Name: sessions sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sessions
    ADD CONSTRAINT sessions_pkey PRIMARY KEY (session_key);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: sessions sessions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sessions
    ADD CONSTRAINT sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

-- This table stores "who knows whom" as an undirected edge.
-- We keep each friendship only once by ordering the pair (low < high).

CREATE TABLE public.friendships (
    user_id_low  bigint NOT NULL,
    user_id_high bigint NOT NULL,
    created_at   timestamp without time zone NOT NULL DEFAULT now(),
    CONSTRAINT friendships_pk PRIMARY KEY (user_id_low, user_id_high),
    CONSTRAINT friendships_distinct CHECK (user_id_low < user_id_high),
    CONSTRAINT friendships_user_low_fk  FOREIGN KEY (user_id_low)  REFERENCES public.users(id) ON DELETE CASCADE,
    CONSTRAINT friendships_user_high_fk FOREIGN KEY (user_id_high) REFERENCES public.users(id) ON DELETE CASCADE
);

-- This view exposes "friend_id" for each user_id so the UI can
-- simply query: SELECT friend_id FROM public.user_friends WHERE user_id = $1;

CREATE VIEW public.user_friends AS
SELECT f.user_id_low  AS user_id, f.user_id_high AS friend_id, f.created_at
FROM public.friendships f
UNION ALL
SELECT f.user_id_high AS user_id, f.user_id_low  AS friend_id, f.created_at
FROM public.friendships f;

-- ===========================
-- Seed users for testing
-- ===========================
-- Per request: login is the first part of the email; password fields are alice/bob.

INSERT INTO public.users (login, email, password_hash, password_salt)
VALUES
  ('alice', 'alice@example.com',  'ce3b149242e9571ee6a6b4b2faae78970119cb69a7666b92900b147356dc0e56', 'f1b6df226df9a43b'),
  ('bob',   'bob@example.com',   'da1dca24a7b3aad9787dc2ecfb089ba23d4960b5ba08c2dc8d011159282253dd', '1306eeebb06f4c74');

-- ===========================
-- Seed a sample friendship
-- ===========================
-- Create an undirected friendship between Alice and Bob (no duplicates if rerun).

INSERT INTO public.friendships (user_id_low, user_id_high)
SELECT LEAST(u1.id, u2.id), GREATEST(u1.id, u2.id)
FROM public.users u1
JOIN public.users u2 ON u1.email = 'alice@example.com' AND u2.email = 'bob@example.com'
ON CONFLICT DO NOTHING;

-- ===========================
-- Example UI-friendly query (for reference)
-- ===========================
-- -- Get all friends for a given user (e.g., user id 1):
-- SELECT friend_id FROM public.user_friends WHERE user_id = 1 ORDER BY friend_id;

    -- ===========================
-- Messages table (simple chat)
-- ===========================
-- Stores direct messages between two users. We keep both directions;
-- queries filter by the pair (me, friend).

CREATE TABLE public.messages (
    id          bigserial PRIMARY KEY,
    sender_id   bigint NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    receiver_id bigint NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    body        text   NOT NULL CHECK (length(body) <= 2000),
    created_at  timestamp without time zone NOT NULL DEFAULT now()
);

-- Helpful indexes for conversation lookups and ordering
CREATE INDEX messages_conv_idx ON public.messages
    (LEAST(sender_id, receiver_id), GREATEST(sender_id, receiver_id), created_at);

CREATE INDEX messages_receiver_idx ON public.messages (receiver_id, created_at);

--
-- PostgreSQL database dump complete
--

\unrestrict jjoKk8MKGuGTTOQmBp6GoSDdP7BMF6Nm9KuttjoO0qD3aSE2cESF7MMcW9tPeQe
