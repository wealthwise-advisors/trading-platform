import copy
from datetime import datetime, timedelta

class RsiStochFibNumber:
    def __init__(self, open, close, high, low, rsi, stoch_k, stoch_d, fib, date, body, close_open, index):
        self.open = open
        self.close = close
        self.high = high
        self.low = low
        self.rsi = rsi
        self.stoch_k = stoch_k
        self.stoch_d = stoch_d
        self.fib = fib
        self.date = date
        self.body = body
        self.close_open = close_open
        self.index = index
        self.new_high_candle = None
        self.new_low_candle = None
        self.cumulative_close_diff = 0
        self.previous_swing_info = None
        self.is_new_high = False
        self.is_new_low = False
        self.divergence_used = False
        self.previous_open = None
        self.previous_close = None
        self.green_wick_up_percent = None
        self.green_wick_down_percent = None
        self.red_wick_up_percent = None
        self.red_wick_down_percent = None
        self.body_percent = None
        self.volume = None
        self.previous_green_wick_up_percent = None
        self.previous_green_wick_down_percent = None
        self.previous_red_wick_up_percent = None
        self.previous_red_wick_down_percent = None
        self.previous_body_percent = None
        self.previous_volume = None
        self.body_volume = None
        self.previous_body_volume = None
        self.previous_fib = None
        self.previous_body = None
        self.previous_rsi = None
        self.previous_stoch_k = None
        self.previous_stoch_d = None
        self.range = None
        self.previous_range = None
        self.previous_high = None
        self.previous_low = None
        self.buy = None
        self.short = None
        self.pre_condition_buy = None
        self.pre_condition_short = None
        self.choppy = None
        self.swing_rsi_check_used = False
        self.upward_swing_start_time = None
        self.downward_swing_start_time = None
        self.negative_candle = None
        self.positive_candle = None
        self.no_swing_used = False
        self.range_bound_status = False
        self.upper_band = None
        self.lower_band = None
        self.higher_datetime = None
        self.kama = None
        self.isFlat = False
        self.choppy = None
        self.previous_choppy = None
        self.previous_index = None
        self.ema_5 = None
        self.ema_12 = None
        self.ema_200 = None
        self.rsi_13 = None
        self.vwap = None
        self.median = None
        self.avg_median = None
        self.previous_avg_median = None
        self.previous_median = None
        self.previous_previous_avg_median = None
        self.previous_previous_median = None
        self.previous_previous_body = None
        self.std_avg_close = None
        self.std_second_top_price = None
        self.std_second_bottom_price = None
        self.std_one_top_price = None
        self.std_one_bottom_price = None
        self.adx = None
        self.is_extreme_buy_sell = None
        self.previous_rsi_13 = None
        self.rsi_13_used_for_cancel = False
        self.rsi_13_below_45_cancel = False
        self.check_rsi_13_close_below = False
        self.divergence_start_candle = None
        self.divergence_end_candle = None
        self.shorted_due_to_all_green = False
        self.lowest_candle_cancelled_before = None
        self.side_ways_structure_detected = False
        self.lowest_candle_cancelled_previous_highest_rsi_candle = None
        self.special_extreme_short_triggered = False
        self.buy_divergence_two_cancel_candle_index = None
        self.buy_divergence_six_cancel_candle_index = None
        self.buy_divergence_one_cancel_candle_index = None
        self.buy_divergence_seven_cancel_candle = None
        self.short_cancel_due_to_rsi_13_and_Above_55 = None
        self.short_cancelled_due_to_new_buy_divergence = False
        self.shorted_due_to_all_extreme = False
        self.buy_due_to_all_extreme = False
        self.short_cancelled_due_to_stoch_k_above_80_candle = None
        self.green_overlap_condition_triggered_candle = None
        self.short_should_have_been_cancelled_but_skipped_due_to_below_55 = None
        self.buy_cancelled_due_to_rsi_and_rsi_13_overlap_candle = None
        self.previous_lowest_rsi_candle = None
        self.previous_highest_rsi_candle = None
        self.buy_due_to_all_extreme_went_wrong = False
        self.skipped_cancel_before = False
        self.buy_cancelled_due_short_divergence_candle = None
        self.cancel_message = None
        self.short_due_to_all_extreme_or_strong_downtrend = False

        try:
            self.datetime = datetime.strptime(date, "%m/%d %I:%M %p")
            self.previous_candle_datetime = self.datetime - timedelta(minutes=1)
        except:
            pass



    def copy(self):
        return RsiStochFibNumber(
            open=copy.deepcopy(self.open),
            close=copy.deepcopy(self.close),
            high=copy.deepcopy(self.high),
            low=copy.deepcopy(self.low),
            rsi=copy.deepcopy(self.rsi),
            stoch_k=copy.deepcopy(self.stoch_k),
            stoch_d=copy.deepcopy(self.stoch_d),
            fib=copy.deepcopy(self.fib),
            date=copy.deepcopy(self.date),
            body=copy.deepcopy(self.body),
            close_open=copy.deepcopy(self.close_open),
            index=copy.deepcopy(self.index)
        )

    def to_dict(self):
        return {
            'Date': self.date,
            'RSI': self.rsi,
            'Close': self.close,
            'Fib_Number': self.fib,
            'High': self.high,
            'Open': self.open,
            'Low': self.low,
            'Stock_K': self.stoch_k,
            'Stock_D': self.stoch_d,
            'Index': self.index,
        }

    def __eq__(self, other):
        if isinstance(other, RsiStochFibNumber):
            return self.datetime == other.datetime
        return False

    def __hash__(self):
        return hash(self.datetime)


    def __repr__(self):
        if self.is_new_high:
            return f"Upward Swing # start_date={self.date}, low_price={self.low}, end_date = {self.new_high_candle.date}, high_price = {self.new_high_candle.high}"
        elif self.is_new_low:
            return f"Downward Swing # start_date={self.date}, high_price = {self.high},  end_date = {self.new_low_candle.date}, low_price={self.new_low_candle.low}"
        else:
            return (f"RsiStochFibNumber(date={self.date}, open={self.open}, high={self.high}, "
                    f"low={self.low}, close={self.close}, rsi={self.rsi}, stoch_k={self.stoch_k}, fib_number={self.fib},"
                    f"stoch_d={self.stoch_d}, is_new_high={self.is_new_high}, is_new_low={self.is_new_low}, volume={self.volume},"
                    f"new_high_candle={self.new_high_candle}, new_low_candle={self.new_low_candle})")
        # return (f"RsiStochFibNumber(date={self.date}, open={self.open}, high={self.high}, "
        #         f"low={self.low}, close={self.close}, new_high_candle={self.new_high_candle}, new_low_candle={self.new_low_candle})")