#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Sep 27 20:53:06 2017

@author: remi
"""


####    Retreive data
#Open API Connection
import krakenex
import numpy as np
k = krakenex.API()

symbol='XXBTZEUR'

#OHLC History (pair,interval,)
response = k.query_public('OHLC', {'pair': symbol, 'interval': '1440','since':'1441012282'})
ts=np.vstack(response['result'][symbol])
import pandas as pd
ts=pd.DataFrame(ts)
ts.columns=['Date','o','h','l','c','w','v','t']

############################
####    Backtest strategy
#import backtest as bt
from backtest import indicator, window, bar, sBuy, sSell, sBuyStop, sSellStop
from backtest import buildOlhc, execStrat, vizStrat

####    Build backend dataset
buildOlhc(ts)

####    Define indicators
@indicator
def sd(per):
    return window(per).ret.std()

@indicator
def est(per):
    return window(per).cret.mean()

#   Levels
@indicator
def bEnterLvl():
    return bar().est+2*bar().sd
@indicator
def sEnterLvl():
    return bar().est-2*bar().sd
@indicator
def bStopLvl():
    return bar().est
@indicator
def sStopLvl():
    return bar().est

#Calculate indicators
#   Band
signPer=7

#   Evaluate indicators
sd(signPer)
est(signPer)

bEnterLvl()
sEnterLvl()
bStopLvl()
sStopLvl()

####    Evaluate signals
sBuy('cret>bEnterLvl')
sSell('cret<sEnterLvl')
sBuyStop('cret<bStopLvl')
sSellStop('cret>sStopLvl')

####    Execute strategy
execStrat()

####    Visualize results
#   List signals to visualize
from bokeh.palettes import Greens4,Reds4
sig=[
     {'high':'bEnterLvl','low':'bStopLvl','color':Greens4[2],'legend':'Buy'},
     {'high':'sEnterLvl','low':'sStopLvl','color':Reds4[2],'legend':'Sell'}     
    ]
vizStrat(sig)
