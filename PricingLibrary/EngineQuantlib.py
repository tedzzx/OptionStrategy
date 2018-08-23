import typing
import math
import datetime
import back_test.model.constant as constant
import QuantLib as ql

"""
                 dt_eval: datetime.date,
                 dt_maturity: datetime.date,
                 strike: float,
                 type: OptionType,
                 spot: float,
                 vol: float,
                 rf: float = 0.03
"""


class QlBinomial(object):
    def __init__(self, n: int, dt_eval: datetime.date, dt_maturity: datetime.date,
                 option_type: constant.OptionType, option_exercise_type: constant.OptionExerciseType,
                 spot: float, strike: float, vol: float, rf: float = 0.03, dividend_rate: float = 0.0):

        self.values: typing.List[typing.List[float]] = []
        self.asset_values: typing.List[typing.List[float]] = []
        self.exercise_values: typing.List[typing.List[float]] = []
        self.strike = strike
        self.spot = spot
        self.vol = vol
        self.rf = rf
        self.dividend_rate = dividend_rate
        self.steps: int = n
        self.maturity_date = constant.QuantlibUtil.to_ql_date(dt_maturity)
        self.settlement = constant.QuantlibUtil.to_ql_date(dt_eval)
        ql.Settings.instance().evaluationDate = self.settlement
        if option_type == constant.OptionType.PUT:
            self.option_type = ql.Option.Put
        else:
            self.option_type = ql.Option.Call
        payoff = ql.PlainVanillaPayoff(self.option_type, strike)
        if option_exercise_type == constant.OptionExerciseType.AMERICAN:
            self.exercise = ql.AmericanExercise(self.settlement, self.maturity_date)
            self.ql_option = ql.VanillaOption(payoff, self.exercise)
        else:
            self.exercise = ql.EuropeanExercise(self.maturity_date)
            self.ql_option = ql.VanillaOption(payoff, self.exercise)
        self.day_count = ql.ActualActual()
        self.calendar = ql.NullCalendar()
        self.spot_handle = ql.QuoteHandle(ql.SimpleQuote(spot))
        self.flat_ts = ql.YieldTermStructureHandle(
            ql.FlatForward(self.settlement, rf, self.day_count)
        )
        self.dividend_yield = ql.YieldTermStructureHandle(
            ql.FlatForward(self.settlement, self.dividend_rate, self.day_count)
        )
        self.flat_vol_ts = ql.BlackVolTermStructureHandle(
            ql.BlackConstantVol(self.settlement, self.calendar, self.vol, self.day_count)
        )
        self.bsm_process = ql.BlackScholesMertonProcess(self.spot_handle,
                                                        self.dividend_yield,
                                                        self.flat_ts,
                                                        self.flat_vol_ts)

    def NPV(self) -> float:
        binomial_engine = ql.BinomialVanillaEngine(self.bsm_process, "crr", self.steps)
        self.ql_option.setPricingEngine(binomial_engine)
        price = self.ql_option.NPV()
        return price

    def reset_vol(self, vol):
        self.flat_vol_ts = ql.BlackVolTermStructureHandle(
            ql.BlackConstantVol(self.settlement, self.calendar, vol, self.day_count)
        )
        self.bsm_process = ql.BlackScholesMertonProcess(self.spot_handle,
                                                        self.dividend_yield,
                                                        self.flat_ts,
                                                        self.flat_vol_ts)

    def estimate_vol(self, price: float, presion:float=0.00001,max_vol:float=2.0):
        l = presion
        r = max_vol
        while l < r and round((r - l), 5) > presion:
            m = round(l + (r - l) / 2, 5)
            self.reset_vol(m)
            p = self.NPV()
            if p < price:
                l = m
            else:
                r = m
        return m, p