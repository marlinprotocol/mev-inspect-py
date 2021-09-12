from web3 import Web3
import asyncio, aiohttp
import time
import json
from mev_inspect.schemas import Trace, TraceType
from mev_inspect.schemas import receipts
from mev_inspect.schemas.receipts import Receipt
from typing import List

async def _get_tx_trace(session, endpoint_uri, tx):
    data = {
        'jsonrpc': '2.0',
        'id': '0',
        'method': 'debug_traceTransaction',
        'params': [tx.hex(), {'tracer': 'callTracer'}]
    }
    async with session.post(endpoint_uri, json=data) as response:
        if response.status != 200:
            response.raise_for_status()
        return await response.text()

async def _geth_get_tx_traces(endpoint_uri, transactions):
    print("getting tx traces")
    start = time.time()
    geth_tx_traces = []
    async with aiohttp.ClientSession() as session:
        tasks = [asyncio.create_task(_get_tx_trace(session, endpoint_uri, tx)) for tx in transactions]
        geth_tx_traces = await asyncio.gather(*tasks)
    print("getting tx traces done ", time.time() - start)
    return [json.loads(tx_trace) for tx_trace in geth_tx_traces]

_calltype_mapping = {
    "CALL": "call",
    "DELEGATECALL": "delegateCall",
    "CREATE": "create",
    "SUICIDE": "suicide",
    "REWARD": "reward"
}

def _unwrap_tx_trace_for_parity(block_json, tx_pos_in_block, tx_trace, position=[]) -> List[Trace]:
    response_list = []
    try:
        if tx_trace['type'] == 'STATICCALL':
            return []
        action_dict = dict()
        action_dict['callType'] =  _calltype_mapping[tx_trace['type']]
        if action_dict['callType'] == "call":
            action_dict['value'] = tx_trace['value']
        for key in ['from', 'to', 'gas', 'input']:
            action_dict[key] = tx_trace[key]

        result_dict = dict()
        for key in ['gasUsed', 'output']:
            result_dict[key] = tx_trace[key]

        response_list.append(Trace(
            action=action_dict,
            # block_hash = block_json['hash'],
            block_number = int(block_json['number']),
            result=result_dict,
            subtraces=len(tx_trace['calls']) if 'calls' in tx_trace.keys() else 0,
            trace_address=position,
            transaction_hash=block_json['transactions'][tx_pos_in_block].hex(),
            transaction_position = tx_pos_in_block,
            type = TraceType(_calltype_mapping[tx_trace['type']])
        ))
    except Exception as e:
        # print("err")
        print("error while decoding trace", tx_trace, e)
        return []

    # print("got trace ", base_trace.action)
    # response_list = [base_trace]

    if 'calls' in tx_trace.keys():
        for idx, subcall in enumerate(tx_trace['calls']):
            response_list.extend(_unwrap_tx_trace_for_parity(block_json, tx_pos_in_block, subcall, position + [idx]))

    return response_list

def geth_get_tx_traces(base_provider, transactions):
    return asyncio.run(_geth_get_tx_traces(base_provider.endpoint_uri, transactions))

async def _get_tx_receipts(session, endpoint_uri, tx):
    data = {
        'jsonrpc': '2.0',
        'id': '0',
        'method': 'eth_getTransactionReceipt',
        'params': [tx.hex()]
    }
    async with session.post(endpoint_uri, json=data) as response:
        if response.status != 200:
            response.raise_for_status()
        return await response.text()

async def _geth_get_tx_receipts(endpoint_uri, transactions):
    # print("getting tx traces")
    start = time.time()
    geth_tx_receipts = []
    async with aiohttp.ClientSession() as session:
        tasks = [asyncio.create_task(_get_tx_receipts(session, endpoint_uri, tx)) for tx in transactions]
        geth_tx_receipts = await asyncio.gather(*tasks)
    print("getting tx receipts done ", time.time() - start)
    return [json.loads(tx_receipts) for tx_receipts in geth_tx_receipts]

def geth_get_tx_receipts(base_provider, transactions):
    return asyncio.run(_geth_get_tx_receipts(base_provider.endpoint_uri, transactions))

def geth_trace_translator(block_json, geth_tx_traces) -> List[Trace]:
    json_decoded_traces = [tx_trace['result'] if tx_trace != None and ('result' in tx_trace.keys()) else None for tx_trace in geth_tx_traces]
    results = []
    for idx, tx_trace in enumerate(json_decoded_traces):
        if tx_trace != None:
            results.extend(_unwrap_tx_trace_for_parity(block_json, idx, tx_trace))
    return results


def _unwrap_tx_receipt_for_parity(block_json, tx_pos_in_block, tx_receipt) -> Receipt:
    # base_trace = Trace
    # receipt = Receipt
    try:
        if tx_pos_in_block != int(tx_receipt['transactionIndex'], 16):
            print("Alert the position of transaction in block is mismatching ", tx_pos_in_block, tx_receipt['transactionIndex'])
        return Receipt(
        block_number = block_json['number'],
        transaction_hash = tx_receipt['transactionHash'],
        transaction_index = tx_pos_in_block,
        gas_used = tx_receipt['gasUsed'],
        effective_gas_price = tx_receipt['effectiveGasPrice'],
        cumulative_gas_used = tx_receipt['cumulativeGasUsed'],
        to = tx_receipt['to']
        )

    except Exception as e:
        print("error while decoding receipt", tx_receipt, e)
    
    return Receipt


def geth_receipts_translator(block_json, geth_tx_receipts) -> List[Receipt]:
    json_decoded_receipts = [tx_receipt['result'] if tx_receipt != None and ('result' in tx_receipt.keys()) else None for tx_receipt in geth_tx_receipts]
    results = []
    for idx, tx_receipt in enumerate(json_decoded_receipts):
        if tx_receipt != None:
            results.append(_unwrap_tx_receipt_for_parity(block_json, idx, tx_receipt))
    return results