--
-- PostgreSQL database dump
--

-- Dumped from database version 9.5.5
-- Dumped by pg_dump version 9.5.5

SET statement_timeout = 0;
SET lock_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SET check_function_bodies = false;
SET client_min_messages = warning;
SET row_security = off;

SET search_path = public, pg_catalog;

SET default_tablespace = ssd;

SET default_with_oids = false;

--
-- Name: articles; Type: TABLE; Schema: public; Owner: adam; Tablespace: ssd
--

CREATE TABLE articles (
    id integer NOT NULL,
    f_path character varying(512) NOT NULL,
    site character varying(64) NOT NULL,
    mtime timestamp without time zone NOT NULL,
    url character varying(512) NOT NULL,
    title text,
    synopsis text,
    fulltext_tsvector tsvector,
    fulltext_no_html text
);


ALTER TABLE articles OWNER TO adam;

--
-- Name: articles_id_seq; Type: SEQUENCE; Schema: public; Owner: adam
--

CREATE SEQUENCE articles_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE articles_id_seq OWNER TO adam;

--
-- Name: articles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: adam
--

ALTER SEQUENCE articles_id_seq OWNED BY articles.id;


SET default_tablespace = '';

--
-- Name: articles_raw; Type: TABLE; Schema: public; Owner: adam
--

CREATE TABLE articles_raw (
    id integer,
    fulltext text,
    raw_document bytea,
    f_path_raw bytea,
    raw_document_checksum bytea
);


ALTER TABLE articles_raw OWNER TO adam;

--
-- Name: id; Type: DEFAULT; Schema: public; Owner: adam
--

ALTER TABLE ONLY articles ALTER COLUMN id SET DEFAULT nextval('articles_id_seq'::regclass);


SET default_tablespace = ssd;

--
-- Name: articles_pkey; Type: CONSTRAINT; Schema: public; Owner: adam; Tablespace: ssd
--

ALTER TABLE ONLY articles
    ADD CONSTRAINT articles_pkey PRIMARY KEY (id);


--
-- Name: articles_fulltext_idx; Type: INDEX; Schema: public; Owner: adam; Tablespace: ssd
--

CREATE INDEX articles_fulltext_idx ON articles USING gin (fulltext_tsvector);


--
-- Name: articles_id; Type: INDEX; Schema: public; Owner: adam; Tablespace: ssd
--

CREATE UNIQUE INDEX articles_id ON articles USING btree (id);


SET default_tablespace = '';

--
-- Name: articles_raw_id; Type: INDEX; Schema: public; Owner: adam
--

CREATE INDEX articles_raw_id ON articles_raw USING btree (id);


--
-- Name: articles; Type: ACL; Schema: public; Owner: adam
--

REVOKE ALL ON TABLE articles FROM PUBLIC;
REVOKE ALL ON TABLE articles FROM adam;
GRANT ALL ON TABLE articles TO adam;
GRANT SELECT ON TABLE articles TO web;


--
-- PostgreSQL database dump complete
--

