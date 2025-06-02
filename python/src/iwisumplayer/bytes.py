def split_to_bytes(value):
    return [
        (value >> 24) & 0xFF,  # najbardziej znaczący bajt
        (value >> 16) & 0xFF,
        (value >> 8)  & 0xFF,
        value & 0xFF            # najmniej znaczący bajt
    ]

def combine_bytes(b0, b1, b2, b3):
    return (b0 << 24) | (b1 << 16) | (b2 << 8) | b3