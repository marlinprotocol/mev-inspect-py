import logging
import requests
import json

from web3 import Web3

from mev_inspect.arbitrages import get_arbitrages
from mev_inspect.block import create_from_block_number, create_from_block_numbers, get_classified_traces_from_events
from mev_inspect.classifiers.trace import TraceClassifier
from mev_inspect.crud.arbitrages import (
    delete_arbitrages_for_block,
    write_arbitrages,
)
from mev_inspect.crud.classified_traces import (
    delete_classified_traces_for_block,
    write_classified_traces,
)
from mev_inspect.crud.miner_payments import (
    delete_miner_payments_for_block,
    write_miner_payments,
)

from mev_inspect.crud.swaps import delete_swaps_for_block, write_swaps


from mev_inspect.crud.transfers import delete_transfers_for_block, write_transfers
from mev_inspect.crud.liquidations import (
    delete_liquidations_for_block,
    write_liquidations,
)
from mev_inspect.miner_payments import get_miner_payments
from mev_inspect.schemas.swaps import Swap
from mev_inspect.swaps import get_swaps
from mev_inspect.transfers import get_transfers
from mev_inspect.aave_liquidations import get_aave_liquidations


logger = logging.getLogger(__name__)


def inspect_block(
    db_session,
    base_provider,
    w3: Web3,
    block_number: int,
    should_cache: bool,
    should_write_classified_traces: bool = True,
    should_write_swaps: bool = True,
    should_write_transfers: bool = True,
    should_write_arbitrages: bool = True,
    should_write_liquidations: bool = True,
    should_write_miner_payments: bool = True,
):
    block = create_from_block_number(base_provider, w3, block_number, should_cache)

    logger.info(f"Total traces: {len(block.traces)}")

    total_transactions = len(
        set(t.transaction_hash for t in block.traces if t.transaction_hash is not None)
    )
    logger.info(f"Total transactions: {total_transactions}")

    trace_clasifier = TraceClassifier()
    classified_traces = trace_clasifier.classify(block.traces)
    for cl in classified_traces:
        print(cl) 
    logger.info(f"Returned {len(classified_traces)} classified traces")

    # if should_write_classified_traces:
    #     delete_classified_traces_for_block(db_session, block_number)
    #     write_classified_traces(db_session, classified_traces)

    transfers = get_transfers(classified_traces)
    # if should_write_transfers:
    #     delete_transfers_for_block(db_session, block_number)
    #     write_transfers(db_session, transfers)

    swaps = get_swaps(classified_traces)
    logger.info(f"Found {len(swaps)} swaps")

    # if should_write_swaps:
    #     delete_swaps_for_block(db_session, block_number)
    #     write_swaps(db_session, swaps)

    arbitrages = get_arbitrages(swaps)
    logger.info(f"Found {len(arbitrages)} arbitrages")

    if len(arbitrages) > 0:
        _payload = list()
        for arb in arbitrages:
            arb_payload = dict()
            arb_payload['block_number'] = arb.block_number
            arb_payload['transaction'] = arb.transaction_hash
            arb_payload['account'] = arb.account_address
            arb_payload['profit_amt'] = arb.profit_amount
            arb_payload['token'] = arb.profit_token_address
            _payload.append(arb_payload)
        resp = requests.post("https://asia-south1-marlin-internal.cloudfunctions.net/mevPolygon/alerts", headers={'Content-type': 'application/json'}, json={"arbitrages": _payload})
        print(resp)
        print(resp.content.decode("utf-8"))
    # if should_write_arbitrages:
    #     delete_arbitrages_for_block(db_session, block_number)
    #     write_arbitrages(db_session, arbitrages)

    liquidations = get_aave_liquidations(classified_traces)
    logger.info(f"Found {len(liquidations)} liquidations")

    # if should_write_liquidations:
    #     delete_liquidations_for_block(db_session, block_number)
    #     write_liquidations(db_session, liquidations)

    miner_payments = get_miner_payments(
        block.miner, block.base_fee_per_gas, classified_traces, block.receipts
    )

    # if should_write_miner_payments:
    #     delete_miner_payments_for_block(db_session, block_number)
    #     write_miner_payments(db_session, miner_payments)


def inspect_many_blocks(
    db_session,
    base_provider,
    w3: Web3,
    after_block,
    before_block
):
    count = 0
    arbitrages_payload = []
    for swaps in get_classified_traces_from_events(base_provider, w3, after_block, before_block):
        arbitrages = get_arbitrages(swaps)
        count += len(arbitrages)
        logger.info(f"{count} Found {len(swaps)} swaps and {len(arbitrages)} arbitrages")
        if len(arbitrages) > 0:
            for arb in arbitrages:
                arb_payload = dict()
                arb_payload['block_number'] = arb.block_number
                arb_payload['transaction'] = arb.transaction_hash
                arb_payload['account'] = arb.account_address
                arb_payload['profit_amt'] = arb.profit_amount
                arb_payload['token'] = arb.profit_token_address
                arbitrages_payload.append(arb_payload)
                count += 1
        
            if count >= 100:
                print("sending to endpoint now")
                resp = requests.post("https://asia-south1-marlin-internal.cloudfunctions.net/mevPolygon/alerts", headers={'Content-type': 'application/json'}, json={"arbitrages": arbitrages_payload})
                print("sending to endpoint ", resp.content.decode("utf-8"), flush=True)
                arbitrages_payload = []
                count = 0

def swap_with_tfrs(
    swap: Swap,
    transfers
):
    if swap.from_address != swap.to_address:
        return [swap]
    
    swaps = []
    for tfr in transfers:
        if tfr.from_address == swap.to_address:
            swaps.append(Swap(
                abi_name="uniswap_v2",
                transaction_hash=swap.transaction_hash,
                block_number=swap.block_number,
                trace_address=swap.trace_address,
                pool_address=swap.pool_address,
                from_address=swap.from_address,
                to_address=tfr.to_address,
                token_in_address=swap.token_in_address,
                token_in_amount=swap.token_in_amount, 
                token_out_address=swap.token_out_address,
                token_out_amount=tfr.amount,
                protocol=None,
                error=None
            ))
    return swaps
    # pool_address = trace.to_address
    # recipient_address = _get_recipient_address(trace)

    # if recipient_address is None:
    #     return None

    # transfers_to_pool = filter_transfers(prior_transfers, to_address=pool_address)

    # if len(transfers_to_pool) == 0:
    #     transfers_to_pool = filter_transfers(child_transfers, to_address=pool_address)

    # if len(transfers_to_pool) == 0:
    #     return None

    # transfers_from_pool_to_recipient = filter_transfers(
    #     child_transfers, to_address=recipient_address, from_address=pool_address
    # )

    # if len(transfers_from_pool_to_recipient) != 1:
    #     return None

    # transfer_in = transfers_to_pool[-1]
    # transfer_out = transfers_from_pool_to_recipient[0]

    # return Swap(
    #     abi_name=trace.abi_name,
    #     transaction_hash=trace.transaction_hash,
    #     block_number=trace.block_number,
    #     trace_address=trace.trace_address,
    #     pool_address=pool_address,
    #     from_address=transfer_in.from_address,
    #     to_address=transfer_out.to_address,
    #     token_in_address=transfer_in.token_address,
    #     token_in_amount=transfer_in.amount,
    #     token_out_address=transfer_out.token_address,
    #     token_out_amount=transfer_out.amount,
    #     error=trace.error,
    # )
