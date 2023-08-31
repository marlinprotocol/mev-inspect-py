from hexbytes._utils import hexstr_to_bytes


def hex_to_int(value: str) -> int:
    return int.from_bytes(hexstr_to_bytes(value), byteorder="big")



def equal_within_percent(
    first_value: int, second_value: int, threshold_percent: float
) -> bool:

    # If the two values are equal, immediately return True
    if first_value == second_value:
        return True

    # Check if 0.5 times the sum of the two values is zero to avoid division by zero
    if 0.5 * (first_value + second_value) == 0:
        return False

    difference = abs(
        (first_value - second_value) / (0.5 * (first_value + second_value))
    )

    return difference < threshold_percent

