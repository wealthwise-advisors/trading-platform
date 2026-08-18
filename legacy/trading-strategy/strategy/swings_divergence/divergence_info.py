class DivergenceInfo:
    def __init__(self, index, trade_type, is_extreme, is_pre_condition, is_rsi_13, start_candle, end_candle, swing_used=None, pre_condition_only=False, only_rsi=False, post_condition_only=False, is_artificial_divergence=False):
        self.index = index
        self.trade_type = trade_type
        self.is_extreme = is_extreme
        self.is_pre_condition = is_pre_condition
        self.is_rsi_13 = is_rsi_13
        self.start_candle = start_candle
        self.end_candle = end_candle
        self.swing_used = swing_used
        self.pre_condition_only = pre_condition_only
        self.copied_from_flip_trade = False
        self.only_rsi = only_rsi
        self.is_extreme_buy_sell = False
        self.post_condition_only = post_condition_only
        self.is_artificial_divergence = is_artificial_divergence
        self.is_extreme_buy_sell = False


    @classmethod
    def from_candles(cls, start_candle, end_candle):
        return cls(
            index=-1,
            trade_type="UNKNOWN",
            is_extreme=False,
            is_pre_condition=False,
            is_rsi_13=False,
            start_candle=start_candle,
            end_candle=end_candle
        )

    def __eq__(self, other):
        if isinstance(other, DivergenceInfo):
            return (self.index == other.index and
                    self.is_extreme == other.is_extreme and
                    self.is_rsi_13 == other.is_rsi_13 and
                    self.start_candle == other.start_candle and
                    self.end_candle == other.end_candle)
        return False

    def __hash__(self):
        return hash((self.index, self.is_extreme, self.is_rsi_13, self.start_candle, self.end_candle))

    def __repr__(self):
        if self.is_extreme:
            return (f"trade_type={self.trade_type}, is_extreme={self.is_extreme}, is_rsi_13={self.is_rsi_13},  is_pre_condition={self.is_pre_condition}, "
                    f"start_rsi={self.start_candle.rsi}, end_rsi={self.end_candle.rsi}, "
                    f"start_date={self.start_candle.date}, end_date={self.end_candle.date}")
        else:
            return (f"trade_type={self.trade_type}, is_extreme={self.is_extreme}, is_rsi_13={self.is_rsi_13}, is_pre_condition={self.is_pre_condition}, is_rsi_13={self.is_rsi_13}, "
                    f"start_date={self.start_candle.date}, end_date={self.end_candle.date}, "
                    f"start_rsi={self.start_candle.rsi}, end_rsi={self.end_candle.rsi}, "
                    f"start_stoch_k={self.start_candle.stoch_k}, end_stoch_k={self.end_candle.stoch_k}, "
                    f"start_stoch_d={self.start_candle.stoch_d}, end_stoch_d={self.end_candle.stoch_d}, ")
