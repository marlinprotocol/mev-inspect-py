from mev_inspect.events.helpers import (
    parse_blockNumber,
    parse_data,
    parse_logIndex,
    parse_topic,
    parse_transactionHash,
)
from mev_inspect.schemas.liquidations import Liquidation


def get_liquidation(data):
    data = data[2:]
    # print(data)
    return (
        int(data[0:64], base=16),
        int(data[64:128], base=16),
        "0x" + data[128 + 24 : 168 + 24],
    )


def get_aave(log):
    block = str(parse_blockNumber(log))
    am_debt, am_recv, addr_usr = get_liquidation(parse_data(log))
    return Liquidation(
        liquidated_user="0x" + parse_topic(log, 3)[26:],
        liquidator_user=addr_usr,
        debt_token_address="0x" + parse_topic(log, 2)[26:],
        debt_purchase_amount=am_debt,
        received_amount=am_recv,
        received_token_address="0x" + parse_topic(log, 1)[26:],
        protocol=None,
        transaction_hash=parse_transactionHash(log),
        trace_address=[parse_logIndex(log)],
        block_number=block,
        error=None,
    )
