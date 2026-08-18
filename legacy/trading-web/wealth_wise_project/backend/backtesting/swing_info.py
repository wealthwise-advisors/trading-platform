class SwingInfo:
    def __init__(self, start_index, end_index, swing_high_price, swing_low_price, swing_high_close, swing_low_close, swing_high_rsi, swing_low_rsi, swing_type):
        self.start_index = start_index
        self.end_index = end_index
        self.swing_high_price = swing_high_price
        self.swing_low_price = swing_low_price
        self.swing_high_close = swing_high_close
        self.swing_low_close = swing_low_close
        self.swing_high_rsi = swing_high_rsi
        self.swing_low_rsi = swing_low_rsi
        self.swing_type = swing_type
        self.flat = False  # Initialize the flat variable to False

    def __eq__(self, other):
        if isinstance(other, SwingInfo):
            return (self.start_index == other.start_index and
                    self.end_index == other.end_index and
                    self.swing_type == other.swing_type)
        return False

    def __hash__(self):
        return hash((self.start_index, self.end_index, self.swing_type))

    def __repr__(self):
        swing_direction = "Upward" if self.swing_type == 1 else "Downward" if self.swing_type == -1 else "Unknown"
        return (f"{swing_direction} Swing(start_index={self.start_index}, end_index={self.end_index}, "
                f"swing_high_price={self.swing_high_price}, swing_low_price={self.swing_low_price}, "
                f"swing_high_close={self.swing_high_close}, swing_low_close={self.swing_low_close}, "
                f"swing_high_rsi={self.swing_high_rsi}, swing_low_rsi={self.swing_low_rsi}, "
                f"swing_type={self.swing_type}, flat={self.flat})")
