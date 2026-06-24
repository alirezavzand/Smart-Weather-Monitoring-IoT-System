#!/usr/bin/env python
# coding: utf-8




import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
from prophet import *

df = pd.read_csv(r'C:\Users\Alireza\Desktop\University Stuff\Unibo\Iot\influxdata.csv', skiprows=3)  
#plt.plot(df["time"],df["Temperature"])
#plt.show()

def forecast_data(df, input):
    df['time'] = pd.to_datetime(df['time']).dt.tz_localize(None)
    df['time'] = pd.DatetimeIndex(df['time'])
    df = df.rename(columns={'time': 'ds', input: 'y'})
    df.set_index('ds')
    model = Prophet(interval_width=0.95)
    model.fit(df)
    future_dates = model.make_future_dataframe(periods=1000, freq='s')
    forecast = model.predict(future_dates)
    model.plot(forecast, uncertainty=True)
    #model.plot_components(forecast)
    
#forecast_data(df, "Temperature")
#forecast_data(df, "Humidity")
forecast_data(df, "Light")


