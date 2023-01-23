import logging

from . import AAVE, ALL_EVENTS, SYNAPSE, UNISWAP_V2, UNISWAP_V3
from .helpers import parse_topic
from .specs.aave import get_aave
from .specs.synapse import get_synapse
from .specs.uniswap_v2 import get_uniswap_v2
from .specs.uniswap_v3 import get_uniswap_v3

logger = logging.getLogger(__name__)


async def _get_logs_for_topics(w3, after_block, before_block, topics):
    return await w3.eth.get_logs(
        {
            "fromBlock": hex(after_block),
            "toBlock": hex(before_block),
            "topics": topics,
        }
    )


async def _classify_logs(logs, reserves, w3):
    cswaps = []
    cliquidations = []
    new_reserves = []
    new_synapse_reserves = []

    for log in logs:
        if parse_topic(log, 0) == UNISWAP_V2:
            swap = await get_uniswap_v2(log, w3, reserves, new_reserves)
            cswaps.append(swap)
        elif parse_topic(log, 0) == UNISWAP_V3:
            swap = await get_uniswap_v3(log, w3, reserves, new_reserves)
            cswaps.append(swap)
        elif parse_topic(log, 0) == SYNAPSE:
            swap = await get_synapse(log, w3, reserves, new_synapse_reserves)
            cswaps.append(swap)
        elif parse_topic(log, 0) == AAVE:
            liquidation = get_aave(log)
            cliquidations.append(liquidation)

    return cswaps, cliquidations, new_reserves, new_synapse_reserves


async def get_classified_traces_from_events(w3, after_block, before_block, reserves):
    start = after_block
    stride = 2000

    while start < before_block:
        begin = start
        end = start + stride if (start + stride) < before_block else before_block
        end -= 1
        start += stride
        logger.info("fetching from node... {} {}".format(begin, end))
        all_logs = await _get_logs_for_topics(
            w3,
            begin,
            end,
            [ALL_EVENTS],
        )
        yield await _classify_logs(all_logs, reserves, w3)
