from back_test.bkt_option_set import BktOptionSet
from back_test.bkt_util import BktUtil
from back_test.data_option import get_50option_mktdata,get_comoption_mktdata
import QuantLib as ql
import pandas as pd
from sqlalchemy import create_engine, MetaData, Table, Column, TIMESTAMP
import datetime
from back_test.bkt_strategy_ivbymoneyness import BktStrategyMoneynessVol
from back_test.data_option import get_50option_mktdata as get_mktdata


start_date = datetime.date(2018,6,4)
end_date = datetime.date(2018,6,8)

calendar = ql.China()
daycounter = ql.ActualActual()
util = BktUtil()
engine = create_engine('mysql+pymysql://root:liz1128@101.132.148.152/metrics', echo=False)
conn = engine.connect()
metadata = MetaData(engine)
optionMetrics = Table('option_metrics', metadata, autoload=True)


name_option = 'sr'
df_option_metrics = get_comoption_mktdata(start_date,end_date,name_option)
bkt_optionset = BktOptionSet('daily', df_option_metrics)
while bkt_optionset.index <= len(bkt_optionset.dt_list):
    evalDate = bkt_optionset.eval_date

    print(evalDate)
    option_metrics = bkt_optionset.collect_option_metrics()
    try:
        for r in option_metrics:
            res = optionMetrics.select((optionMetrics.c.id_instrument == r['id_instrument'])
                                       &(optionMetrics.c.dt_date == r['dt_date'])).execute()
            if res.rowcount > 0:
                optionMetrics.delete((optionMetrics.c.id_instrument == r['id_instrument'])
                                       &(optionMetrics.c.dt_date == r['dt_date'])).execute()
            conn.execute(optionMetrics.insert(), r)
        print(evalDate, ' : option metrics -- inserted into data base succefully')
    except Exception as e:
        print(e)
        pass
    if evalDate == bkt_optionset.end_date:
        break
    bkt_optionset.next()


name_option = 'm'
df_option_metrics = get_comoption_mktdata(start_date,end_date,name_option)
bkt_optionset = BktOptionSet('daily', df_option_metrics)

while bkt_optionset.index <= len(bkt_optionset.dt_list):
    # if bkt_optionset.index == 0:
    #     bkt_optionset.next()
    #     continue
    evalDate = bkt_optionset.eval_date


    print(evalDate)
    option_metrics = bkt_optionset.collect_option_metrics()
    try:
        for r in option_metrics:
            res = optionMetrics.select((optionMetrics.c.id_instrument == r['id_instrument'])
                                       &(optionMetrics.c.dt_date == r['dt_date'])).execute()
            if res.rowcount > 0:
                optionMetrics.delete((optionMetrics.c.id_instrument == r['id_instrument'])
                                       &(optionMetrics.c.dt_date == r['dt_date'])).execute()
            conn.execute(optionMetrics.insert(), r)
        print(evalDate, ' : option metrics -- inserted into data base succefully')
    except Exception as e:
        print(e)
        pass
    if evalDate == bkt_optionset.end_date:
        break
    bkt_optionset.next()


df_option_metrics = get_50option_mktdata(start_date,end_date)
bkt_optionset = BktOptionSet('daily', df_option_metrics)

while bkt_optionset.index <= len(bkt_optionset.dt_list):
    #     continue
    evalDate = bkt_optionset.eval_date

    print(evalDate)
    option_metrics = bkt_optionset.collect_option_metrics()
    print(option_metrics)
    try:
        for r in option_metrics:
            res = optionMetrics.select((optionMetrics.c.id_instrument == r['id_instrument'])
                                       &(optionMetrics.c.dt_date == r['dt_date'])).execute()
            if res.rowcount > 0:
                optionMetrics.delete((optionMetrics.c.id_instrument == r['id_instrument'])
                                       &(optionMetrics.c.dt_date == r['dt_date'])).execute()
            conn.execute(optionMetrics.insert(), r)
        print(evalDate, ' : option metrics -- inserted into data base succefully')
    except Exception as e:
        print(e)
        pass
    if evalDate == bkt_optionset.end_date:
        break
    bkt_optionset.next()

""" Calculate ATM Implied Volatility"""

df_option_metrics = get_mktdata(start_date, end_date)

bkt = BktStrategyMoneynessVol(df_option_metrics)
bkt.set_min_holding_days(8) # TODO: 选择期权最低到期日
res = bkt.ivs_mdt1_run()
table = Table('option_atm_iv', metadata, autoload=True)
for r in res:
    try:
        conn.execute(table.insert(), r)
        # r.to_sql(name='option_atm_iv', con=engine, if_exists='append', index=False)
    except Exception as e:
        print(e)
        continue