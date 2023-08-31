import asyncio

from web3 import Web3

from mev_inspect.events.helpers import (
    parse_address,
    parse_blockNumber,
    parse_data,
    parse_logIndex,
    parse_token,
    parse_topic,
    parse_transactionHash,
    twos_complement,
)
from mev_inspect.schemas.swaps import Swap


def get_swap_v3(data):
    data = data[2:]
    # print(data)
    return (
        twos_complement(data[0:64], 256),
        twos_complement(data[64:128], 256),
        int(data[152:192], base=16),
        int(data[224:256], base=16),
        twos_complement(data[314:320], 24),
    )


async def get_token0_token1(w3, addr):
    token0, token1 = await asyncio.gather(
        w3.eth.call({"to": addr, "data": "0x0dfe1681"}),
        w3.eth.call({"to": addr, "data": "0xd21220a7"}),
    )
    token0 = parse_token(w3, token0)
    token1 = parse_token(w3, token1)
    return token0, token1


async def get_uniswap_v3(log, w3, reserves, new_reserves):
    block = parse_blockNumber(log)
    transaction_hash = parse_transactionHash(log)
    pool_address = parse_address(log)
    if pool_address in reserves:
        token0, token1 = reserves[pool_address]
    else:
        addr = Web3.toChecksumAddress(pool_address)
        token0, token1 = await get_token0_token1(w3, addr)
        reserves[pool_address] = (token0, token1)
        new_reserves.append(
            {"pool_address": pool_address, "token0": token0, "token1": token1}
        )

    am0, am1, _, _, _ = get_swap_v3(parse_data(log))
    return Swap(
        abi_name="uniswap_v3",
        transaction_hash=transaction_hash,
        block_number=block,
        trace_address=[parse_logIndex(log)],
        contract_address=pool_address,
        from_address="0x" + parse_topic(log, 1)[26:],
        to_address="0x" + parse_topic(log, 2)[26:],
        token_in_address=token0 if am0 > 0 else token1,  # TODO
        token_in_amount=am0 if am0 > 0 else am1,
        token_out_address=token1 if am1 < 0 else token0,  # TODO
        token_out_amount=-am1 if am1 < 0 else -am0,
        protocol=None,
        error=None,
    )
