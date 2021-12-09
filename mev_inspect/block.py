from os import P_WAIT
from pathlib import Path
from typing import List
import asyncio, aiohttp
import time
import json
from aiohttp.client import request
import requests

from web3 import Web3

from mev_inspect.fees import fetch_base_fee_per_gas
from mev_inspect.schemas import Block, Trace, TraceType
from mev_inspect.schemas import receipts
from mev_inspect.schemas.classified_traces import Classification, ClassifiedTrace
from mev_inspect.schemas.receipts import Receipt
from mev_inspect.schemas.swaps import Swap


cache_directory = "./cache"


def get_latest_block_number(w3: Web3) -> int:
    return int(w3.eth.get_block("latest")["number"])


def create_from_block_number(
    base_provider, w3: Web3, block_number: int, should_cache: bool
) -> Block:
    if not should_cache:
        return fetch_block(w3, base_provider, block_number)

    cache_path = _get_cache_path(block_number)

    if cache_path.is_file():
        print(f"Cache for block {block_number} exists, " "loading data from cache")

        return Block.parse_file(cache_path)
    else:
        print(f"Cache for block {block_number} did not exist, getting data")

        block = fetch_block(w3, base_provider, block_number)

        cache_block(cache_path, block)

        return block

def _get_logs_for_topics(base_provider, after_block, before_block, topics):
    print("getting log traces")
    start = time.time()
    logs = base_provider.make_request("eth_getLogs",
        [{
            "fromBlock": hex(after_block),
            "toBlock": hex(before_block),
            "topics": topics,
        }])
    print("getting log traces done ", time.time() - start, len(logs))
    return logs['result']

def _make_custom_payloads(logs):
    txs_seen = set()
    # temp_payload = []
    payloads = []
    block_hashes = dict()
    block_counts = dict()
    for log in logs:
        # print("log", log)
        if log['transactionHash'] in txs_seen:
            continue
        txs_seen.add(log['transactionHash'])
        block = int(log['blockNumber'], 16)
        if block in block_counts:
            block_counts[block].append(log['transactionHash'])
        else:
            block_hashes[block] = log['blockHash']
            block_counts[block] = [log['transactionHash']]
    ctr = 0
    for block in block_counts:
        if ctr == 0:
            payloads.append([{"block": hex(block), "transactions": block_counts[block]}])
            ctr += 1
        else:    
            payloads[-1].append({"block": hex(block), "transactions": block_counts[block]})
            ctr += 1
        if ctr >= 1:
            ctr = 0
    return payloads, block_hashes

def _get_traces_custom_rpc(base_provider, payload):
    # print("getting custom traces")
    start = time.time()
    # data = {
    #     "jsonrpc": "2.0",
    #     "id": "0",
    #     "method": "debug_traceBlockByHash2",
    #     "params": [payload, {
    #         "tracer": "callTracer",
    #     }],
    # }
    # traces = base_provider.make_request("debug_traceBlockByHash2",
    #     [payload, {
    #         "tracer": "callTracer",
    #     }], timeout=100)
    # print("new way of requesting")
    resp = requests.post("http://94.130.242.196:8545", data='{"jsonrpc":"2.0","method":"debug_traceBlockByHash2","params":['+str(payload).replace("'", '"')+',{"tracer": "callTracer"}],"id":74}', headers={'content-type': 'application/json'}, timeout=100)
    if resp.status_code == 200:
        traces = json.loads(resp.content.decode("utf-8"))
        print("getting custom traces done ", time.time() - start, len(traces), flush=True)
        return traces

def create_from_block_numbers(
    base_provider, w3: Web3, after_block: int, before_block: int
) -> List[Block]:
    topics = ["0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822"]
    logs = _get_logs_for_topics(base_provider, after_block, before_block, topics)
    payloads, block_hashes = _make_custom_payloads(logs)
    # print('payloads', len(payloads))
    # for payload in payloads:
    #     print(len(payload))

    for payload in payloads:
        # print("fetching...", flush=True)
        got_traces = False
        while not got_traces:
            try:
                traces = _get_traces_custom_rpc(base_provider, payload)['result']
                got_traces = True
            except Exception as e:
                print("got exceptions ", e)
        trace_idx = 0
        for block in payload:
            block_tx_idx = 0
            parity_traces = []
            # print("block", block)
            block_json = {'number': int(block['block'], 16), 'hash': block_hashes[int(block['block'], 16)], 'transactions': block['transactions']}
            # print("block_json ", int(block['block'], 16), len(block_json['transactions']), trace_idx, len(traces))
            for _tx in block['transactions']:
                if trace_idx >= len(traces) or 'result' not in traces[trace_idx]:
                    continue
                # print("trace id ", traces[trace_idx])
                # print('txhash', traces[trace_idx]['txhash'])
                parity_traces.extend(_unwrap_tx_trace_for_parity(block_json, block_tx_idx, traces[trace_idx]['result'], txhash=traces[trace_idx]['txhash']))
                block_tx_idx += 1
                trace_idx += 1
            # print("block_json ", len(block_json['transactions']), trace_idx)
            # print("parity_traces", parity_traces)
            yield Block(
                block_number=int(block['block'], 16),
                miner="0x0",
                base_fee_per_gas=0,
                traces=parity_traces,
                receipts=[]
            )

def _geth_get_tx_traces(base_provider, block_hash):
    print("getting tx traces")
    start = time.time()
    block_trace = base_provider.make_request("debug_traceBlockByHash", [block_hash.hex(), {"tracer": "callTracer"}])
    print("getting tx traces done ", time.time() - start, len(block_trace))
    return block_trace


def _unwrap_tx_trace_for_parity(
    block_json, tx_pos_in_block, tx_trace, position=[], txhash=None
) -> List[Trace]:
    response_list = []
    _calltype_mapping = {
        "CALL": "call",
        "DELEGATECALL": "delegateCall",
        "CREATE": "create",
        "SUICIDE": "suicide",
        "REWARD": "reward",
    }
    try:
        if tx_trace["type"] == "STATICCALL":
            return []
        action_dict = dict()
        action_dict["callType"] = _calltype_mapping[tx_trace["type"]]
        if action_dict["callType"] == "call":
            action_dict["value"] = tx_trace["value"]
        for key in ["from", "to", "gas", "input"]:
            action_dict[key] = tx_trace[key]

        result_dict = dict()
        for key in ["gasUsed", "output"]:
            result_dict[key] = tx_trace[key]

        response_list.append(
            Trace(
                action=action_dict,
                block_hash = str(block_json['hash']),
                block_number=int(block_json["number"]),
                result=result_dict,
                subtraces=len(tx_trace["calls"]) if "calls" in tx_trace.keys() else 0,
                trace_address=position,
                transaction_hash=txhash,
                transaction_position=tx_pos_in_block,
                type=TraceType(_calltype_mapping[tx_trace["type"]]),
            )
        )
    except Exception as e:
        # print("errdectrace ", e)
        # print("error while decoding trace", tx_trace, e)
        return []

    # print("got trace ", base_trace.action)
    # response_list = [base_trace]

    if "calls" in tx_trace.keys():
        for idx, subcall in enumerate(tx_trace["calls"]):
            response_list.extend(
                _unwrap_tx_trace_for_parity(
                    block_json, tx_pos_in_block, subcall, position + [idx], txhash
                )
            )
    return response_list


def geth_get_tx_traces_parity_format(base_provider, block_json):
    block_hash = block_json['hash']
    block_trace = _geth_get_tx_traces(base_provider, block_hash)
    # print("geth_trace_len: ", len(block_trace)/1000)
    # print("block number ", block_json['number'], "tx count ", len(block_json['transactions']), "full trace JSON len: ", len(json.dumps(block_trace))/1000, "K", block_trace)
    parity_traces = []
    for idx, trace in enumerate(block_trace['result']):
        if 'result' in trace:
            parity_traces.extend(_unwrap_tx_trace_for_parity(block_json, idx, trace['result']))
    # print("full trace ", len(json.dumps(parity_traces)))
    return parity_traces

async def _get_tx_receipts(session, endpoint_uri, tx):
    data = {
        "jsonrpc": "2.0",
        "id": "0",
        "method": "eth_getTransactionReceipt",
        "params": [tx.hex()],
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
        tasks = [
            asyncio.create_task(_get_tx_receipts(session, endpoint_uri, tx))
            for tx in transactions
        ]
        geth_tx_receipts = await asyncio.gather(*tasks)
    print("getting tx receipts done ", time.time() - start)
    return [json.loads(tx_receipts) for tx_receipts in geth_tx_receipts]

def geth_get_tx_receipts(base_provider, transactions):
    return asyncio.run(_geth_get_tx_receipts(base_provider.endpoint_uri, transactions))

def _unwrap_tx_receipt_for_parity(block_json, tx_pos_in_block, tx_receipt) -> Receipt:
    # base_trace = Trace
    # receipt = Receipt
    try:
        if tx_pos_in_block != int(tx_receipt["transactionIndex"], 16):
            print(
                "Alert the position of transaction in block is mismatching ",
                tx_pos_in_block,
                tx_receipt["transactionIndex"],
            )
        return Receipt(
            block_number=block_json["number"],
            transaction_hash=tx_receipt["transactionHash"],
            transaction_index=tx_pos_in_block,
            gas_used=tx_receipt["gasUsed"],
            effective_gas_price=tx_receipt["effectiveGasPrice"],
            cumulative_gas_used=tx_receipt["cumulativeGasUsed"],
            to=tx_receipt["to"],
        )

    except Exception as e:
        print("error while decoding receipt", tx_receipt, e)

    return Receipt()

def geth_receipts_translator(block_json, geth_tx_receipts) -> List[Receipt]:
    json_decoded_receipts = [
        tx_receipt["result"]
        if tx_receipt != None and ("result" in tx_receipt.keys())
        else None
        for tx_receipt in geth_tx_receipts
    ]
    results = []
    for idx, tx_receipt in enumerate(json_decoded_receipts):
        if tx_receipt != None:
            results.append(_unwrap_tx_receipt_for_parity(block_json, idx, tx_receipt))
    return results

def fetch_block(w3, base_provider, block_number: int) -> Block:
    block_json = w3.eth.get_block(block_number)
    # print("got block json ", block_json)

    parity_block_traces = geth_get_tx_traces_parity_format(base_provider, block_json)
    geth_tx_receipts = geth_get_tx_receipts(base_provider, block_json["transactions"])
    # print("Got geth traces and receipts", len(geth_tx_traces), len(geth_tx_receipts))

    # parity_block_traces = geth_trace_translator(block_json, geth_tx_traces)
    parity_receipts = geth_receipts_translator(block_json, geth_tx_receipts)
    print(
        "Translated parity traces and receipts",
        len(parity_block_traces),
        len(parity_receipts),
    )

    return Block(
        block_number=block_number,
        miner=block_json["miner"],  # TODO: Polygon miners are 0x000 ?
        base_fee_per_gas=0,  # TODO
        traces=parity_block_traces,
        receipts=parity_receipts,
    )

# def fetch_block(w3, base_provider, block_number: int) -> Block:
#     block_json = w3.eth.get_block(block_number)
#     receipts_json = base_provider.make_request("eth_getBlockReceipts", [block_number])
#     traces_json = w3.parity.trace_block(block_number)

#     receipts: List[Receipt] = [
#         Receipt(**receipt) for receipt in receipts_json["result"]
#     ]
#     traces = [Trace(**trace_json) for trace_json in traces_json]
#     base_fee_per_gas = fetch_base_fee_per_gas(w3, block_number)

#     return Block(
#         block_number=block_number,
#         miner=block_json["miner"],
#         base_fee_per_gas=base_fee_per_gas,
#         traces=traces,
#         receipts=receipts,
#     )


def get_transaction_hashes(calls: List[Trace]) -> List[str]:
    result = []

    for call in calls:
        if call.type != TraceType.reward:
            if (
                call.transaction_hash is not None
                and call.transaction_hash not in result
            ):
                result.append(call.transaction_hash)

    return result


def cache_block(cache_path: Path, block: Block):
    write_mode = "w" if cache_path.is_file() else "x"

    cache_path.parent.mkdir(parents=True, exist_ok=True)

    with open(cache_path, mode=write_mode) as cache_file:
        cache_file.write(block.json())


def _get_cache_path(block_number: int) -> Path:
    cache_directory_path = Path(cache_directory)
    return cache_directory_path / f"{block_number}-new.json"

def get_classified_traces_from_events(base_provider, w3: Web3, after_block: int, before_block: int) -> List[ClassifiedTrace]:
    start = after_block
    stride = 300
    reserves = dict()
    while start < before_block:
        begin = start
        end = start + stride if (start + stride) < before_block else before_block
        start += stride
        print("fetching from node...", begin, end, flush=True)
        swaplogs = _get_logs_for_topics(base_provider, begin, end, ["0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822"])
        logs_by_tx = _logs_by_tx(swaplogs)
        for tx in logs_by_tx.keys():
            yield classify_logs(logs_by_tx[tx], reserves, w3)
    # tfrlogs = _get_logs_for_topics(base_provider, after_block, before_block, ["0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"])
    
    # all_logs = tfrlogs + swaplogs
    # print("lens", len(tfrlogs), len(swaplogs))
    
        # if tx != "0x0e5e20a274e0b27a1b757d0212bf32ccb44cf118939ad44a1d72a4a74474b60f":
        #     continue
        # print(len(logs_by_tx[tx]))
        
        # pass

    # partial_swaps_list = get_partial_swaps(logs, w3, reserves)
    # # print(partial_swaps_list)
    # for p_swap in partial_swaps_list:
    #     yield partial_swaps_list[p_swap]

def _logs_by_tx(logs):
    logs_by_tx = dict()
    for log in logs:
        transaction_hash = log['transactionHash']
        if transaction_hash in logs_by_tx.keys():
            logs_by_tx[transaction_hash].append(log)
        else:
            logs_by_tx[transaction_hash] = [log]
    return logs_by_tx

def classify_logs(logs, reserves, w3):
    clogs = []
    cswaps = []
    topic_transfer = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
    topic_swap = "0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822"
    for log in logs:
        if log['topics'][0] == topic_transfer:
            # transfer
            clogs.append(ClassifiedTrace(
                action={},
                block_hash=log['blockHash'],
                subtraces=0,
                transaction_hash=log['transactionHash'],
                block_number=int(log['blockNumber'], 16),
                trace_address=[int(log['logIndex'], 16)],
                type=TraceType.call,
                classification=Classification.transfer,
                to_address=log['address'],
                from_address="0x" + log['topics'][1][26:],
                inputs={"amount": int(log['data'], 16), "recipient": "0x" + log['topics'][2][26:]}
            ))
        elif log['topics'][0] == topic_swap:
            # print(log)
            block = int(log['blockNumber'], 16)
            transaction_hash = log['transactionHash']
            pool_address = log['address']
            if pool_address in reserves:
                token0, token1 = reserves[pool_address]
            else:
                contract = w3.eth.contract(address=Web3.toChecksumAddress(pool_address), abi=univ2abi)
                token0 = contract.functions.token0().call()
                token1 = contract.functions.token1().call()
                # print("pool ", pool_address, token0, token1)
                reserves[pool_address] = (token0, token1)

            am0in, am1in, am0out, am1out = get_amounts(log['data'])
            swap = Swap(
                abi_name="uniswap_v2",
                transaction_hash=transaction_hash,
                block_number=block,
                trace_address=[int(log['logIndex'], 16)],
                pool_address=pool_address,
                from_address="0x"+log['topics'][1][26:],
                to_address="0x"+log['topics'][2][26:],
                token_in_address=token0 if am0in != 0 else token1, # TODO
                token_in_amount= am0in if am0in != 0 else am1in, 
                token_out_address=token1 if am1out != 0 else token0, # TODO
                token_out_amount= am0out if am0out != 0 else am1out,
                protocol=None,
                error=None
            )
            # print(log, "\n",  am0in, am1in, am0out, am1out, "\n", swap)
            cswaps.append(swap)
            # if transaction_hash in tx_counts:
            #     tx_counts[transaction_hash].append(swap)
            # else:
            #     tx_counts[transaction_hash] = [swap]
            # # uniswap swap
            # pass
    return cswaps


def get_partial_swaps(logs, w3, reserves):
    tx_counts = dict()
    for log in logs:
        # print(log)
        block = int(log['blockNumber'], 16)
        transaction_hash = log['transactionHash']
        pool_address = log['address']
        if pool_address in reserves:
            token0, token1 = reserves[pool_address]
        else:
            contract = w3.eth.contract(address=Web3.toChecksumAddress(pool_address), abi=univ2abi)
            token0 = contract.functions.token0().call()
            token1 = contract.functions.token1().call()
            reserves[pool_address] = (token0, token1)

        am0in, am1in, am0out, am1out = get_amounts(log['data'])
        swap = Swap(
             abi_name="uniswap_v2",
             transaction_hash=transaction_hash,
             block_number=block,
             trace_address=[0],
             pool_address=pool_address,
             from_address=log['topics'][1],
             to_address=log['topics'][2],
             token_in_address=token0 if am0in != 0 else token1, # TODO
             token_in_amount= am0in if am0in != 0 else am1in, 
             token_out_address=token1 if am1in != 0 else token0, # TODO
             token_out_amount= am0out if am0out != 0 else am1out,
             protocol=None,
             error=None
        )
        if transaction_hash in tx_counts:
            tx_counts[transaction_hash].append(swap)
        else:
            tx_counts[transaction_hash] = [swap]
    return tx_counts

def get_amounts(data):
    data = data[2:]
    # print(data)
    return int(data[0:64], base=16), int(data[64:128], base=16), int(data[128:192], base=16), int(data[192:256], base=16)

univ2abi = '''
[{"inputs":[],"stateMutability":"nonpayable","type":"constructor"},{"anonymous":false,"inputs":[{"indexed":true,"internalType":"address","name":"owner","type":"address"},{"indexed":true,"internalType":"address","name":"spender","type":"address"},{"indexed":false,"internalType":"uint256","name":"value","type":"uint256"}],"name":"Approval","type":"event"},{"anonymous":false,"inputs":[{"indexed":true,"internalType":"address","name":"sender","type":"address"},{"indexed":false,"internalType":"uint256","name":"amount0","type":"uint256"},{"indexed":false,"internalType":"uint256","name":"amount1","type":"uint256"},{"indexed":true,"internalType":"address","name":"to","type":"address"}],"name":"Burn","type":"event"},{"anonymous":false,"inputs":[{"indexed":true,"internalType":"address","name":"sender","type":"address"},{"indexed":false,"internalType":"uint256","name":"amount0","type":"uint256"},{"indexed":false,"internalType":"uint256","name":"amount1","type":"uint256"}],"name":"Mint","type":"event"},{"anonymous":false,"inputs":[{"indexed":true,"internalType":"address","name":"sender","type":"address"},{"indexed":false,"internalType":"uint256","name":"amount0In","type":"uint256"},{"indexed":false,"internalType":"uint256","name":"amount1In","type":"uint256"},{"indexed":false,"internalType":"uint256","name":"amount0Out","type":"uint256"},{"indexed":false,"internalType":"uint256","name":"amount1Out","type":"uint256"},{"indexed":true,"internalType":"address","name":"to","type":"address"}],"name":"Swap","type":"event"},{"anonymous":false,"inputs":[{"indexed":false,"internalType":"uint112","name":"reserve0","type":"uint112"},{"indexed":false,"internalType":"uint112","name":"reserve1","type":"uint112"}],"name":"Sync","type":"event"},{"anonymous":false,"inputs":[{"indexed":true,"internalType":"address","name":"from","type":"address"},{"indexed":true,"internalType":"address","name":"to","type":"address"},{"indexed":false,"internalType":"uint256","name":"value","type":"uint256"}],"name":"Transfer","type":"event"},{"inputs":[],"name":"DOMAIN_SEPARATOR","outputs":[{"internalType":"bytes32","name":"","type":"bytes32"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"MINIMUM_LIQUIDITY","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"PERMIT_TYPEHASH","outputs":[{"internalType":"bytes32","name":"","type":"bytes32"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"","type":"address"},{"internalType":"address","name":"","type":"address"}],"name":"allowance","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"spender","type":"address"},{"internalType":"uint256","name":"value","type":"uint256"}],"name":"approve","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"","type":"address"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"to","type":"address"}],"name":"burn","outputs":[{"internalType":"uint256","name":"amount0","type":"uint256"},{"internalType":"uint256","name":"amount1","type":"uint256"}],"stateMutability":"nonpayable","type":"function"},{"inputs":[],"name":"decimals","outputs":[{"internalType":"uint8","name":"","type":"uint8"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"factory","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"getReserves","outputs":[{"internalType":"uint112","name":"_reserve0","type":"uint112"},{"internalType":"uint112","name":"_reserve1","type":"uint112"},{"internalType":"uint32","name":"_blockTimestampLast","type":"uint32"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"_token0","type":"address"},{"internalType":"address","name":"_token1","type":"address"}],"name":"initialize","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[],"name":"kLast","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"to","type":"address"}],"name":"mint","outputs":[{"internalType":"uint256","name":"liquidity","type":"uint256"}],"stateMutability":"nonpayable","type":"function"},{"inputs":[],"name":"name","outputs":[{"internalType":"string","name":"","type":"string"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"","type":"address"}],"name":"nonces","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"owner","type":"address"},{"internalType":"address","name":"spender","type":"address"},{"internalType":"uint256","name":"value","type":"uint256"},{"internalType":"uint256","name":"deadline","type":"uint256"},{"internalType":"uint8","name":"v","type":"uint8"},{"internalType":"bytes32","name":"r","type":"bytes32"},{"internalType":"bytes32","name":"s","type":"bytes32"}],"name":"permit","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[],"name":"price0CumulativeLast","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"price1CumulativeLast","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"to","type":"address"}],"name":"skim","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"uint256","name":"amount0Out","type":"uint256"},{"internalType":"uint256","name":"amount1Out","type":"uint256"},{"internalType":"address","name":"to","type":"address"},{"internalType":"bytes","name":"data","type":"bytes"}],"name":"swap","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[],"name":"symbol","outputs":[{"internalType":"string","name":"","type":"string"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"sync","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[],"name":"token0","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"token1","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"totalSupply","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"value","type":"uint256"}],"name":"transfer","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"from","type":"address"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"value","type":"uint256"}],"name":"transferFrom","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"}]
'''