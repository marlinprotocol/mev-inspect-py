CREATE TABLE public.swaps (
    created_at timestamp without time zone DEFAULT now(),
    abi_name character varying(1024) NOT NULL,
    transaction_hash character varying(66) NOT NULL,
    block_number numeric NOT NULL,
    protocol character varying(256),
    contract_address character varying(256) NOT NULL,
    from_address character varying(256) NOT NULL,
    to_address character varying(256) NOT NULL,
    token_in_address character varying(256) NOT NULL,
    token_in_amount numeric NOT NULL,
    token_out_address character varying(256) NOT NULL,
    token_out_amount numeric NOT NULL,
    trace_address integer[] NOT NULL,
    error character varying(256),
    transaction_position numeric
);

ALTER TABLE ONLY public.swaps
    ADD CONSTRAINT swaps_pkey PRIMARY KEY (block_number, transaction_hash, trace_address);

