CREATE TABLE public.arbitrages (
    id character varying(256) NOT NULL,
    created_at timestamp without time zone DEFAULT now(),
    account_address character varying(256) NOT NULL,
    profit_token_address character varying(256) NOT NULL,
    block_number numeric NOT NULL,
    transaction_hash character varying(256) NOT NULL,
    start_amount numeric NOT NULL,
    end_amount numeric NOT NULL,
    profit_amount numeric NOT NULL,
    error character varying(256),
    protocols character varying(256)[] DEFAULT '{}'::character varying[]
);

ALTER TABLE ONLY public.arbitrages
    ADD CONSTRAINT arbitrages_pkey PRIMARY KEY (id);

