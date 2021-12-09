from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from .blocks import Trace


class Classification(Enum):
    unknown = "unknown"
    swap = "swap"
    burn = "burn"
    transfer = "transfer"
    liquidate = "liquidate"


class Protocol(Enum):
    uniswap_v2 = "uniswap_v2"
    uniswap_v3 = "uniswap_v3"
    sushiswap = "sushiswap"
    aave = "aave"
    weth = "weth"
    curve = "curve"
    zero_ex = "0x"
    balancer_v1 = "balancer_v1"

class ClassifiedTrace(Trace):
    transaction_hash: str
    block_number: int
    trace_address: List[int]
    classification: Classification
    error: Optional[str]
    to_address: Optional[str]
    from_address: Optional[str]
    gas: Optional[int]
    value: Optional[int]
    gas_used: Optional[int]
    protocol: Optional[Protocol]
    function_name: Optional[str]
    function_signature: Optional[str]
    inputs: Optional[Dict[str, Any]]
    abi_name: Optional[str]

    class Config:
        validate_assignment = True
        json_encoders = {
            # a little lazy but fine for now
            # this is used for bytes value inputs
            bytes: lambda b: b.hex(),
        }


class CallTrace(ClassifiedTrace):
    to_address: str
    from_address: str


class DecodedCallTrace(CallTrace):
    inputs: Dict[str, Any]
    abi_name: str
    protocol: Optional[Protocol]
    gas: Optional[int]
    gas_used: Optional[int]
    function_name: Optional[str]
    function_signature: Optional[str]


class ClassifierSpec(BaseModel):
    abi_name: str
    protocol: Optional[Protocol] = None
    valid_contract_addresses: Optional[List[str]] = None
    classifications: Dict[str, Classification] = {}
