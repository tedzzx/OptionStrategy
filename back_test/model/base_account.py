import pandas as pd
import numpy as np
import datetime
from typing import Union
from back_test.model.abstract_account import AbstractAccount
from back_test.model.base_product import BaseProduct
from back_test.model.constant import Util, TradeType, LongShort
from back_test.model.trade import Order


class BaseAccount():
    def __init__(self, init_fund, leverage=1.0, fee_rate=3.0 / 10000.0, rf=0.03):
        # super().__init__()
        self.df_records = pd.DataFrame()
        self.list_records = []
        self.trade_book = pd.DataFrame(columns=Util.TRADE_BOOK_COLUMN_LIST)
        self.dict_holding = {}  # id_instrument -> Product
        self.account = pd.DataFrame()
        self.init_fund = init_fund
        self.max_leverage = leverage
        self.fee_rate = fee_rate
        self.rf = rf
        self.cash = init_fund  # 现金账户：初始资金为现金
        self.actual_leverage = 0.0
        self.total_mtm_position = 0.0  # 总多空持仓市值(abs value)加总
        # self.total_margin_trade_mtm_position = 0.0

    def add_holding(self, base_product: BaseProduct):
        if base_product.id_instrument() not in self.dict_holding.keys():
            self.dict_holding.update({base_product.id_instrument(): base_product})

    def add_record(self, execution_record: pd.Series, base_product: BaseProduct):
        if execution_record is None: return
        self.list_records.append(execution_record)
        self.add_holding(base_product)
        id_instrument = execution_record[Util.ID_INSTRUMENT]
        if not self.trade_book.empty and id_instrument in self.trade_book.index:
            book_series = self.trade_book.loc[id_instrument]
            # """ New record has opposite direction """
            if book_series[Util.TRADE_LONG_SHORT] != execution_record[Util.TRADE_LONG_SHORT]:
                # """ close out """
                if book_series[Util.TRADE_UNIT] == execution_record[Util.TRADE_UNIT]:
                    trade_long_short = book_series[Util.TRADE_LONG_SHORT]
                    trade_unit = 0
                    last_price = execution_record[Util.TRADE_PRICE]
                    trade_margin_capital = 0.0
                    trade_book_value = 0.0
                    average_position_cost = 0.0
                    trade_realized_pnl = book_series[Util.TRADE_REALIZED_PNL] + \
                                         book_series[Util.NBR_MULTIPLIER] * \
                                         execution_record[Util.TRADE_UNIT] * execution_record[
                                             Util.TRADE_LONG_SHORT].value * \
                                         (execution_record[Util.TRADE_PRICE] -
                                          book_series[Util.AVERAGE_POSITION_COST])
                    self.cash += book_series[Util.TRADE_MARGIN_CAPITAL]
                    self.cash += book_series[Util.TRADE_REALIZED_PNL]
                    position_current_value = self.get_position_current_value(id_instrument, trade_unit,
                                                                             trade_long_short.value,
                                                                             average_position_cost)
                    self.dict_holding.pop(id_instrument, None)
                # """ close partial """
                elif book_series[Util.TRADE_UNIT] > execution_record[Util.TRADE_UNIT]:
                    ratio = execution_record[Util.TRADE_UNIT] / book_series[Util.TRADE_UNIT]
                    trade_long_short = book_series[Util.TRADE_LONG_SHORT]
                    trade_unit = book_series[Util.TRADE_UNIT] - execution_record[Util.TRADE_UNIT]
                    last_price = execution_record[Util.TRADE_PRICE]
                    margin_released = book_series[Util.TRADE_MARGIN_CAPITAL] * ratio
                    trade_margin_capital = book_series[Util.TRADE_MARGIN_CAPITAL] - margin_released
                    trade_book_value = book_series[Util.TRADE_BOOK_VALUE] * (1 - ratio)
                    average_position_cost = book_series[Util.AVERAGE_POSITION_COST]
                    realized_pnl = book_series[Util.NBR_MULTIPLIER] * \
                                   execution_record[Util.TRADE_UNIT] * book_series[Util.TRADE_LONG_SHORT].value * \
                                   (execution_record[Util.TRADE_PRICE] - book_series[Util.AVERAGE_POSITION_COST])
                    trade_realized_pnl = book_series[Util.TRADE_REALIZED_PNL] + realized_pnl
                    self.cash += realized_pnl + margin_released
                    position_current_value = self.get_position_current_value(id_instrument, trade_unit,
                                                                             trade_long_short.value,
                                                                             average_position_cost)

                # """ open opposite :平仓加反向开仓 """
                else:
                    trade_long_short = execution_record[Util.TRADE_LONG_SHORT]
                    trade_unit = execution_record[Util.TRADE_UNIT] - book_series[Util.TRADE_UNIT]
                    last_price = execution_record[Util.TRADE_PRICE]
                    trade_margin_capital = execution_record[Util.TRADE_MARGIN_CAPITAL] * \
                                           (1 - book_series[Util.TRADE_UNIT] / execution_record[Util.TRADE_UNIT])
                    margin_released = book_series[Util.TRADE_MARGIN_CAPITAL]
                    trade_book_value = book_series[Util.NBR_MULTIPLIER] * execution_record[Util.TRADE_LONG_SHORT].value \
                                       * trade_unit * last_price
                    average_position_cost = last_price
                    realized_pnl = book_series[Util.NBR_MULTIPLIER] * book_series[Util.TRADE_UNIT] * \
                                   book_series[Util.TRADE_LONG_SHORT].value * \
                                   (execution_record[Util.TRADE_PRICE] - book_series[Util.AVERAGE_POSITION_COST])
                    trade_realized_pnl = book_series[Util.TRADE_REALIZED_PNL] + realized_pnl
                    self.cash += realized_pnl - trade_margin_capital + margin_released
                    position_current_value = self.get_position_current_value(id_instrument, trade_unit,
                                                                             trade_long_short.value,
                                                                             average_position_cost)

            # """ add position : New record has the same direction """"
            else:
                trade_long_short = execution_record[Util.TRADE_LONG_SHORT]
                trade_unit = book_series[Util.TRADE_UNIT] + execution_record[Util.TRADE_UNIT]
                last_price = execution_record[Util.TRADE_PRICE]
                trade_margin_capital = execution_record[Util.TRADE_MARGIN_CAPITAL]
                trade_book_value = book_series[Util.TRADE_BOOK_VALUE] + execution_record[Util.TRADE_BOOK_VALUE]
                average_position_cost = abs(book_series[Util.TRADE_BOOK_VALUE]) / book_series[Util.TRADE_UNIT]
                trade_realized_pnl = book_series[Util.TRADE_REALIZED_PNL]  # No added realized pnl
                self.cash -= trade_margin_capital
                position_current_value = self.get_position_current_value(id_instrument, trade_unit,
                                                                         trade_long_short.value, average_position_cost)
            self.trade_book.loc[id_instrument, Util.TRADE_LONG_SHORT] = trade_long_short
            self.trade_book.loc[id_instrument, Util.LAST_PRICE] = last_price
            self.trade_book.loc[id_instrument, Util.TRADE_UNIT] = trade_unit
            self.trade_book.loc[id_instrument, Util.TRADE_REALIZED_PNL] = trade_realized_pnl
            self.trade_book.loc[id_instrument, Util.AVERAGE_POSITION_COST] = average_position_cost
            self.trade_book.loc[id_instrument, Util.TRADE_BOOK_VALUE] = trade_book_value
            self.trade_book.loc[id_instrument, Util.TRADE_MARGIN_CAPITAL] = trade_margin_capital
        else:
            # """ Open a new position """
            trade_unit = execution_record[Util.TRADE_UNIT]
            trade_long_short = execution_record[Util.TRADE_LONG_SHORT]
            average_position_cost = execution_record[Util.TRADE_PRICE]
            book_series = pd.Series({
                Util.TRADE_UNIT: trade_unit,
                Util.LAST_PRICE: execution_record[Util.TRADE_PRICE],
                Util.TRADE_MARGIN_CAPITAL: execution_record[Util.TRADE_MARGIN_CAPITAL],
                Util.TRADE_BOOK_VALUE: execution_record[Util.TRADE_BOOK_VALUE],
                Util.TRADE_LONG_SHORT: trade_long_short,
                Util.AVERAGE_POSITION_COST: average_position_cost,
                Util.TRADE_REALIZED_PNL: 0.0,
                Util.NBR_MULTIPLIER: base_product.multiplier()
            })
            self.trade_book.loc[id_instrument] = book_series
            self.cash -= execution_record[Util.TRADE_MARGIN_CAPITAL]
            position_current_value = self.get_position_current_value(id_instrument, trade_unit, trade_long_short.value,
                                                                     average_position_cost)
        self.cash -= execution_record[Util.TRADE_MARKET_VALUE] # 无保证金交易（期权买方、股票等）的头寸市值从现金账户中全部扣除
        self.trade_book.loc[id_instrument, Util.POSITION_CURRENT_VALUE] = position_current_value
        self.update_account_status()

    # 股票与购买期权杠杆率计算方法不一样：base_product加入current value(不包含保证金)？？
    # 保证金交易的future、期权卖方为零，股票、ETF、期权买方为当前MTM value
    def update_account_status(self):
        total_mtm_position = (self.trade_book.loc[:, Util.TRADE_UNIT] * self.trade_book.loc[:, Util.LAST_PRICE]
                              * self.trade_book[Util.NBR_MULTIPLIER]).sum()
        total_margin = self.trade_book[Util.TRADE_MARGIN_CAPITAL].sum()
        total_current_value = self.trade_book[Util.POSITION_CURRENT_VALUE].sum()
        self.actual_leverage = total_mtm_position / (self.cash + total_margin + total_current_value)
        self.total_mtm_position = total_mtm_position

    # Option write position current value is unrealized pnl, option buy position is the premium.
    def get_position_current_value(self, id_instrument, trade_unit, long_short, average_position_cost):
        base_product = self.dict_holding[id_instrument]
        if base_product.get_current_value(long_short) == 0.0:
            # 对于保证金交易，头寸价值为未实现损益（unrealized pnl）：每日净额结算后，将浮盈浮亏入账，用average_position_cost计算有问题
            # position_current_value = trade_unit * long_short * (base_product.mktprice_close() - average_position_cost)
            # 暂定：保证金交易头寸价值为零，暂不考虑日内的浮动盈亏。
            position_current_value = 0.0
        else:
            # 对于购买股票/期权买方等，头寸价值为当前市值
            position_current_value = base_product.get_current_value(long_short) * trade_unit * base_product.multiplier()
        return position_current_value

    # 总保证金交易的市值（按照last trade price，不考虑日内未实现损益），多空绝对市值相加，用于仓位控制。
    def get_total_margin_trade_mtm_position(self):
        total_margin_trade_mtm_position = 0.0
        for (i,row) in self.trade_book.iteritems():
            id_instrument = row[Util.ID_INSTRUMENT]
            long_short = row[Util.TRADE_LONG_SHORT]
            base_product = self.dict_holding[id_instrument]
            if base_product.get_current_value(long_short) == 0.0:
                total_margin_trade_mtm_position += row[Util.TRADE_UNIT] * row[Util.NBR_MULTIPLIER] * row[Util.LAST_PRICE]
        return total_margin_trade_mtm_position

    # For calculate MAX trade unit before execute order.
    def get_investable_market_value(self):
        total_margin_trade_mtm_position = self.get_total_margin_trade_mtm_position()
        total_margin_capital = self.trade_book[Util.TRADE_MARGIN_CAPITAL].sum()
        investable_cash = max(0.0,self.cash + total_margin_capital - total_margin_trade_mtm_position / self.max_leverage)
        return investable_cash * self.max_leverage

    def create_trade_order(self, dt_trade: datetime.date, id_instrument: str,
                           trade_type: TradeType, trade_price: Union[float, None],
                           time_signal: Union[datetime.datetime, None], multiplier: float,
                           trade_unit: int = None, long_short=None):
        if trade_type == TradeType.CLOSE_SHORT or trade_type == TradeType.CLOSE_LONG:
            book_series = self.trade_book.loc[id_instrument]
            trade_unit = book_series[Util.TRADE_UNIT]
            if trade_type == TradeType.CLOSE_SHORT and book_series[Util.TRADE_LONG_SHORT] == LongShort.LONG:
                return
            elif trade_type == TradeType.CLOSE_LONG and book_series[Util.TRADE_LONG_SHORT] == LongShort.SHORT:
                return
            order = Order(dt_trade, id_instrument, trade_type, trade_unit, trade_price,
                          time_signal, long_short)
            return order
        max_unit = np.floor(self.get_investable_market_value() / (trade_price * multiplier))
        if max_unit < 1:
            return
        else:
            trade_unit = min(max_unit, trade_unit)
            order = Order(dt_trade, id_instrument, trade_type, trade_unit, trade_price,
                          time_signal, long_short)
            return order


    # TODO : trigger end of day
    def daily_accounting(self):
        total_position_value = 0.0
        for (id_instrument, row) in self.trade_book.iterrows():
            if row[Util.TRADE_UNIT] == 0.0: continue
            base_product = self.dict_holding[id_instrument]
            trade_unit = row[Util.TRADE_UNIT]
            trade_long_short = row[Util.TRADE_LONG_SHORT]
            average_position_cost = row[Util.AVERAGE_POSITION_COST]
            # calculate margin capital
            trade_margin_capital_add = base_product.get_maintain_margin() * row[Util.TRADE_UNIT] - row[
                Util.TRADE_MARGIN_CAPITAL]
            self.trade_book.loc[id_instrument, Util.TRADE_MARGIN_CAPITAL] += trade_margin_capital_add
            self.cash -= trade_margin_capital_add
            # Calculate NPV
            position_current_value = self.get_position_current_value(id_instrument, trade_unit, trade_long_short.value,
                                                                     average_position_cost)
            self.trade_book.loc[id_instrument, Util.POSITION_CURRENT_VALUE] = position_current_value
            total_position_value += position_current_value
        total_margin = self.trade_book[Util.TRADE_MARGIN_CAPITAL].sum()
        portfolio_mtm_value = self.cash + total_margin + total_position_value
        npv = portfolio_mtm_value / self.init_fund
        self.update_account_status()
