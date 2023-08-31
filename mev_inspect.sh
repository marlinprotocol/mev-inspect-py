#!/bin/bash

export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=mP73yeCm7pSW7yr
export POSTGRES_HOST=mev-inspect.csur8vbmm7gf.us-west-1.rds.amazonaws.com
export RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/9HgvqM2ZpLSs4d9q3x5yiER07j7Dun90

python3 listener.py
