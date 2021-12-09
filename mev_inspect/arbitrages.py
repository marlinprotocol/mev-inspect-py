from itertools import groupby
from typing import List, Optional

from mev_inspect.schemas.arbitrages import Arbitrage
from mev_inspect.schemas.swaps import Swap


def get_arbitrages(swaps: List[Swap]) -> List[Arbitrage]:
    get_transaction_hash = lambda swap: swap.transaction_hash
    swaps_by_transaction = groupby(
        sorted(swaps, key=get_transaction_hash),
        key=get_transaction_hash,
    )

    all_arbitrages = []

    for _, transaction_swaps in swaps_by_transaction:
        all_arbitrages += _get_arbitrages_from_swaps(
            list(transaction_swaps),
        )

    return all_arbitrages


def _get_arbitrages_from_swaps(swaps: List[Swap]) -> List[Arbitrage]:
    pool_addresses = {swap.pool_address for swap in swaps}

    all_arbitrages = []

    for index, first_swap in enumerate(swaps):
        other_swaps = swaps[:index] + swaps[index + 1 :]

        if first_swap.from_address not in pool_addresses:
            # print("FS", first_swap.trace_address, first_swap.from_address, first_swap.to_address)
            # print("starting with", first_swap)
            arbitrage = _get_arbitrage_starting_with_swap(first_swap, other_swaps)

            if arbitrage is not None:
                all_arbitrages.append(arbitrage)

    return all_arbitrages


def _get_arbitrage_starting_with_swap(
    start_swap: Swap,
    other_swaps: List[Swap],
) -> Optional[Arbitrage]:
    swap_path = [start_swap]
    current_swap: Swap = start_swap

    while True:
        next_swap = _get_swap_from_address(
            current_swap.to_address,
            current_swap.token_out_address,
            other_swaps,
        )
        
        if next_swap is None:
            return None

        # print("NS",  next_swap.trace_address, next_swap.from_address, next_swap.to_address)
        
        swap_path.append(next_swap)
        current_swap = next_swap

        if (
            current_swap.to_address == start_swap.from_address
            and current_swap.token_out_address == start_swap.token_in_address
        ):

            start_amount = start_swap.token_in_amount
            end_amount = current_swap.token_out_amount
            profit_amount = end_amount - start_amount

            return Arbitrage(
                swaps=swap_path,
                block_number=start_swap.block_number,
                transaction_hash=start_swap.transaction_hash,
                account_address=start_swap.from_address,
                profit_token_address=start_swap.token_in_address,
                start_amount=start_amount,
                end_amount=end_amount,
                profit_amount=profit_amount,
            )

    return None


def _get_swap_from_address(
    address: str, token_address: str, swaps: List[Swap]
) -> Optional[Swap]:
    for swap in swaps:
        if swap.pool_address == address and swap.token_in_address == token_address:
            return swap

    return None
