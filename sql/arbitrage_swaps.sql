CREATE TABLE public.arbitrage_swaps (
    created_at timestamp without time zone DEFAULT now(),
    arbitrage_id character varying(1024) NOT NULL,
    swap_transaction_hash character varying(66) NOT NULL,
    swap_trace_address integer[] NOT NULL
);

ALTER TABLE ONLY public.arbitrage_swaps
    ADD CONSTRAINT arbitrage_swaps_pkey PRIMARY KEY (arbitrage_id, swap_transaction_hash, swap_trace_address);

CREATE INDEX arbitrage_swaps_swaps_idx ON public.arbitrage_swaps USING btree (swap_transaction_hash, swap_trace_address);

ALTER TABLE ONLY public.arbitrage_swaps
    ADD CONSTRAINT arbitrage_swaps_arbitrage_id_fkey FOREIGN KEY (arbitrage_id) REFERENCES public.arbitrages(id) ON DELETE CASCADE;

