import asyncio

from web3 import Web3
from web3.exceptions import ContractLogicError

from mev_inspect.events.helpers import (
    parse_address,
    parse_blockNumber,
    parse_data,
    parse_logIndex,
    parse_token,
    parse_topic,
    parse_transactionHash,
)
from mev_inspect.schemas.swaps import Swap


def get_swap_synapse(data):
    data = data[2:]
    # print(data)
    return (
        int(data[0:64], base=16),
        int(data[64:128], base=16),
        data[128:192],
        data[192:256],
    )


async def get_token(w3, addr, tokenId):
    try:
        token = await w3.eth.call({"to": addr, "data": "0x82b86600" + tokenId})
    except ContractLogicError:
        token = await w3.eth.call({"to": addr, "data": "0xc6610657" + tokenId})
    return token


async def get_synapse(log, w3, reserves, new_synapse_reserves):
    block = parse_blockNumber(log)
    transaction_hash = parse_transactionHash(log)
    pool_address = parse_address(log)

    sold, bought, soldId, boughtId = get_swap_synapse(parse_data(log))

    soldKey = pool_address + soldId[32:]
    boughtKey = pool_address + boughtId[32:]

    soldToken, boughtToken = None, None
    if soldKey in reserves:
        soldToken = reserves[soldKey]
    if boughtKey in reserves:
        boughtToken = reserves[boughtKey]

    if soldToken is None and boughtToken is None:
        addr = Web3.toChecksumAddress(pool_address)
        soldToken, boughtToken = await asyncio.gather(
            get_token(w3, addr, soldId),
            get_token(w3, addr, boughtId),
        )
        soldToken = parse_token(w3, soldToken)
        boughtToken = parse_token(w3, boughtToken)
        reserves[soldKey] = soldToken
        reserves[boughtKey] = boughtToken
        new_synapse_reserves.extend(
            [
                {
                    "pool_address_index": soldKey,
                    "token": soldToken,
                },
                {
                    "pool_address_index": boughtKey,
                    "token": boughtToken,
                },
            ]
        )
    elif soldToken is None:
        addr = Web3.toChecksumAddress(pool_address)
        soldToken = await get_token(w3, addr, soldId)
        soldToken = parse_token(w3, soldToken)
        reserves[soldKey] = soldToken
        new_synapse_reserves.append(
            {
                "pool_address_index": soldKey,
                "token": soldToken,
            }
        )
    elif boughtToken is None:
        addr = Web3.toChecksumAddress(pool_address)
        boughtToken = await get_token(w3, addr, boughtId)
        boughtToken = parse_token(w3, boughtToken)
        reserves[boughtKey] = boughtToken
        new_synapse_reserves.append(
            {
                "pool_address_index": boughtKey,
                "token": boughtToken,
            }
        )
    return Swap(
        abi_name="synapse",
        transaction_hash=transaction_hash,
        block_number=block,
        trace_address=[parse_logIndex(log)],
        contract_address=pool_address,
        from_address="0x" + parse_topic(log, 1)[26:],
        to_address="0x" + parse_topic(log, 1)[26:],
        token_in_address=soldToken,
        token_in_amount=sold,
        token_out_address=boughtToken,
        token_out_amount=bought,
        protocol=None,
        error=None,
    )
