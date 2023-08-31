CREATE TABLE public.liquidations (
    created_at timestamp without time zone DEFAULT now(),
    liquidated_user character varying(256) NOT NULL,
    liquidator_user character varying(256) NOT NULL,
    debt_token_address character varying(256) NOT NULL,
    debt_purchase_amount numeric NOT NULL,
    received_amount numeric NOT NULL,
    protocol character varying(256),
    transaction_hash character varying(66) NOT NULL,
    trace_address character varying(256) NOT NULL,
    block_number numeric NOT NULL,
    received_token_address character varying(256),
    error character varying(256)
);

ALTER TABLE ONLY public.liquidations
    ADD CONSTRAINT liquidations_pkey PRIMARY KEY (transaction_hash, trace_address);

