import requests
from mev_inspect.schemas.arbitrages import Arbitrage
from typing import List
import random

_known_coins = {
    "0x2791bca1f2de4661ed88a30c99a7a9449aa84174": "USDC",
    "0x0d500b1d8e8ef31e21c99d1db9a6444d3adf1270": "wMATIC",
    "0x7ceb23fd6bc0add59e62ac25578270cff1b9f619": "wETH(polygon)"
}

def notify_discord(webhook, arbitrages: List[Arbitrage]):
    colors = [11711680, 11700000, 16742280, 16711680]
    for idx, arb in enumerate(arbitrages):
        profit_token_address = arb.profit_token_address
        profit_amount = arb.profit_amount
        if profit_token_address in _known_coins.keys():
            profit_token_address = _known_coins[profit_token_address]
            profit_amount = f'{profit_amount/10**18:.3g} {profit_token_address}'
        html = {
            "embeds": [{
                "title": "Arbitrage Detected",
                "url": f"https://polygonscan.com/tx/{arb.transaction_hash}",
                "color": random.choice(colors),
                "fields": [
                    {
                        "name": "Block",
                        "value": arb.block_number,
                        "inline": True
                    },
                    {
                        "name": "Address",
                        "value": arb.account_address,
                        "inline": True
                    },
                    {
                        "name": "TxHash",
                        "value": arb.transaction_hash,
                        "inline": False
                    },
                    {
                        "name": "Profit",
                        "value": profit_amount,
                        "inline": True
                    },
                    {
                        "name": "Profit token",
                        "value": profit_token_address,
                        "inline": True
                    },
                ],
                "footer": {
                    "icon_url": "https://www.drivingtests.co.nz/resources/wp-content/uploads/2013/10/120px-New_Zealand_PW-53.svg_.png",
                    "text": "Value shown above are estimates, and may not be exact."
                }
            }]
        }
        requests.post(webhook, json=html)
        # print("hello", idx, arb)