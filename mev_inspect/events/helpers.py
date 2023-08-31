def twos_complement(hexstr, bits):
    value = int(hexstr, 16)
    if value & (1 << (bits - 1)):
        value -= 1 << bits
    return value


def parse_topic(log, index):
    return log["topics"][index].hex()


def parse_blockNumber(log):
    return log["blockNumber"]


def parse_transactionHash(log):
    return log["transactionHash"].hex()


def parse_address(log):
    return log["address"].lower()


def parse_logIndex(log):
    return log["logIndex"]


def parse_data(log):
    return log["data"]


def parse_token(w3, token):
    return "0x" + w3.toHex(token)[26:]
