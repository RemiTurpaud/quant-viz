#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A Pandas-based trading simulator

Created on Sat Sep  2 00:06:39 2017

@author: remi
"""


####    Prepare dataframe
import pandas as pd
import numpy as np

df=pd.DataFrame()

def buildOlhc(ts):
    if not set(['Date','o','h','l','c']).issubset(ts.columns):
        raise ValueError("Data Frame must at least contain columns ['Date','o','h','l','c']")
        
    df[['o','h','l','c']]=ts[['o','h','l','c']].astype('float')
    df['Date']=pd.to_datetime(ts.Date,unit='s')
    df['lr']=np.log(1+df.c.astype('float').pct_change())
    df['hlr']=np.log(df.h.astype('float')/df.c.astype('float'))
    df['llr']=np.log(df.l.astype('float')/df.c.astype('float'))
    df['clr']=df['lr'].cumsum()
    df.sort_values('Date',inplace=True)
    
####    Indicator decorator
def indicator(ind):
    def append(*args,**kwargs):
        df[ind.__name__]=ind(*args,**kwargs)
    return append
  
####    Input functions for indicators
#Trailing window for indicators
def window(per):
    if per<0:
        raise ValueError("Window length must be positive.")
    return df.rolling(per)

def bar():
    return df

####    Signal functions
def signal(name,expr):
    expr='('+expr+')==True'
    df[name]=df.eval(expr).shift(1)
    df[name].fillna(False,inplace=True)

def sBuy(expr):
    "Buy signal"
    signal('sBuy',expr)

def sSell(expr):
    "Sell signal"    
    signal('sSell',expr)

def sBuyStop(expr):
    "Stop signal for long positions"
    signal('sBuyStop',expr)

def sSellStop(expr):
    "Stop signal for short positions"
    signal('sSellStop',expr)



####    Execute strategy
def execStrat(comCost=0):
    ####    Define States (positions)
    df['pBuy']=np.NAN
    df.loc[df['sBuy'],['pBuy']]=True
    df.loc[df['sBuyStop'] | df['sSell'],['pBuy']]=False
    df['pBuy'].fillna(method='ffill',inplace=True)
    
    df['pSell']=np.NAN
    df.loc[df['sSell'],['pSell']]=True
    df.loc[df['sSellStop'] | df['sBuy'],'pSell']=False
    df['pSell'].fillna(method='ffill',inplace=True)
    
    #       Propagate states
    df['pBuy'].fillna(False,inplace=True)
    df['pSell'].fillna(False,inplace=True)
    df['pBuy']=df['pBuy'].astype(bool)
    df['pSell']=df['pSell'].astype(bool)
    #       Consolidate states
    df['State']=df['pBuy'].astype('int')-df['pSell'].astype('int')
    
    #       Add trade enter/exit indicators
    df['pBuyEnter']=df['pBuy'].diff() & df['pBuy']
    df['pSellEnter']=df['pSell'].diff() & df['pSell']
    df['pBuyExit']=df['pBuy'].diff() & (df['sBuyStop']  | df['sSell'])
    df['pSellExit']=df['pSell'].diff() & (df['sSellStop']  | df['sBuy'] )
    
    
    ####    Identify Trades
    #   Trades
    df['pBuyTradeNo']=df['pBuyEnter'].cumsum()*df['pBuy']
    df['pSellTradeNo']=df['pSellEnter'].cumsum()*df['pSell']
    df['TradeNo']=(df['pBuyEnter'] | df['pSellEnter']).cumsum()*(df['State'].abs())
    
    ####    Calculate P&L
    #Bar profit
    df['pl']=df['pBuy']*df['lr']-df['lr']*df['pSell']
    #TODO   Adjust entry/exit points - for SLTP
    #       Exit
    #df.loc[df['pBuyExit'],['pl']]=(df['bStopLvl']-(df['clr']-df['lr']))[df['pBuyExit']]
    #df.loc[df['pSellExit'],['pl']]=-(df['sStopLvl']-(df['clr']-df['lr']))[df['pSellExit']]
    
    
    #   Add commission cost
    df.loc[((df['pBuyEnter']) | (df['pSellEnter'])),['pl']]-=comCost
    
    #Calculate running P&L
    df['cpl']=df['pl'].cumsum()


    ###     Analysis
    #Total P&L
    print(df['pl'].sum(),',',df['lr'].sum())


####    Visualisation
#       TODO: Break down into primitives, identify indicators, alow user-defined viz types...
def vizStrat(sigPlot=[],comCost=0):
    from bokeh.layouts import column,row
    from bokeh.plotting import figure, show
    from bkcharts import Donut
    from bokeh.palettes import Blues4,Greens4,Reds4
    from bokeh.models import Span
    
    #P&L
    #   Graph Return
    pRet = figure(x_axis_type="datetime", title="Performance Cc Return",plot_width=800, plot_height=400)
    pRet.grid.grid_line_alpha=0.3
    pRet.xaxis.axis_label = 'Date'
    pRet.yaxis.axis_label = 'Return'
    
    pRet.line(df['Date'], df['clr'], color=Blues4[1], legend='Ref')
    pRet.line(df['Date'], df['cpl'], color=Greens4[1], legend='Strat')
    pRet.legend.location = "top_left"
    
    #   Trades type distribution
    pie = pd.Series([df.pBuyTradeNo.max(),df.pSellTradeNo.max()], index = ["Long","Short"],name='Trade Type')
    pDist= Donut(pie ,color=[Greens4[1],Reds4[1]],title='Total Trades',plot_width=400,hover_text='Trades',toolbar_location = None)
    
    pie = pd.Series([(~(df.pBuy&df.pBuy)).sum(),df.pBuy.sum(),df.pSell.sum()], index = ["Idle","Long","Short"])
    pDistBar= Donut(pie ,color=[Blues4[1],Greens4[1],Reds4[1]],title='Total Trade time',plot_width=400,hover_text='Bars',toolbar_location = None)
    
    #   Trades return histogram
    bTradeRet=df[df.State>0].groupby('TradeNo').pl.sum()
    sTradeRet=df[df.State<0].groupby('TradeNo').pl.sum()
    bH=np.histogram(bTradeRet,density=True, bins=10)
    sH=np.histogram(sTradeRet,density=True, bins=10)
    
    #       Draw histograms
    pTradeRet = figure(x_axis_type="linear", title="Trade Return",plot_width=400, plot_height=400)
    pTradeRet.quad(top=bH[0], bottom=0, left=bH[1][:-1], right=bH[1][1:],
            fill_color=Greens4[2], line_color=None,fill_alpha=.7)
    pTradeRet.quad(top=sH[0], bottom=0, left=sH[1][:-1], right=sH[1][1:],
            fill_color=Reds4[2], line_color=None,fill_alpha=.5)
    #       Draw boundary lines
    pTradeRet.segment(x0=bTradeRet.min(),x1=bTradeRet.min(),y0=0, y1=-1,color=Greens4[1], line_width=2)
    pTradeRet.segment(x0=bTradeRet.max(),x1=bTradeRet.max(),y0=0, y1=-1,color=Greens4[1], line_width=2)
    pTradeRet.segment(x0=bTradeRet.mean(),x1=bTradeRet.mean(),y0=1, y1=-1,color=Greens4[1], line_width=2)
    pTradeRet.segment(x0=sTradeRet.min(),x1=sTradeRet.min(),y0=0, y1=-1,color=Reds4[1], line_width=2)
    pTradeRet.segment(x0=sTradeRet.max(),x1=sTradeRet.max(),y0=0, y1=-1,color=Reds4[1], line_width=2)
    pTradeRet.segment(x0=sTradeRet.mean(),x1=sTradeRet.mean(),y0=1, y1=-1,color=Reds4[1], line_width=2)
    
    pTradeRet.y_range.start=-1
    
    #   Bar return histogram
    bH=np.histogram(df[df.State>0].pl,density=True, bins=10)
    sH=np.histogram(df[df.State<0].pl,density=True, bins=10)
    
    #       Draw histograms
    pBarRet = figure(x_axis_type="linear", title="Bar Return",plot_width=400, plot_height=400)
    pBarRet.quad(top=bH[0], bottom=0, left=bH[1][:-1], right=bH[1][1:],
            fill_color=Greens4[2], line_color=None,fill_alpha=.7)
    pBarRet.quad(top=sH[0], bottom=0, left=sH[1][:-1], right=sH[1][1:],
            fill_color=Reds4[2], line_color=None,fill_alpha=.5)
    
    #       Draw boundary lines
    pBarRet.segment(x0=df[df.State>0].pl.min(),x1=df[df.State>0].pl.min(),y0=0, y1=-1,color=Greens4[1], line_width=2)
    pBarRet.segment(x0=df[df.State>0].pl.max(),x1=df[df.State>0].pl.max(),y0=0, y1=-1,color=Greens4[1], line_width=2)
    pBarRet.segment(x0=df[df.State>0].pl.mean(),x1=df[df.State>0].pl.mean(),y0=1, y1=-1,color=Greens4[1], line_width=2)
    pBarRet.segment(x0=df[df.State<0].pl.min(),x1=df[df.State<0].pl.min(),y0=0, y1=-1,color=Reds4[1], line_width=2)
    pBarRet.segment(x0=df[df.State<0].pl.max(),x1=df[df.State<0].pl.max(),y0=0, y1=-1,color=Reds4[1], line_width=2)
    pBarRet.segment(x0=df[df.State<0].pl.mean(),x1=df[df.State<0].pl.mean(),y0=1, y1=-1,color=Reds4[1], line_width=2)
    
    pBarRet.y_range.start=-1
    
            
    #Strategy signals
    #   hlc graph
    pStrat = figure(x_axis_type="datetime", title="Strategy",plot_width=800, plot_height=400)
    pStrat.grid.grid_line_alpha=0.3
    pStrat.xaxis.axis_label = 'Date'
    pStrat.yaxis.axis_label = 'Return'
    pStrat.quad(top=df['clr']+df['hlr'], bottom=df['clr']+df['llr'], left=df['Date']-df['Date'].diff(), right=df['Date'],
                  color=Blues4[1], legend="Ref")
    
    #   Signals
    for s in sigPlot:
        if set(['high','low','color']).issubset(s.keys()):
            pStrat.quad(top=df[s['high']], bottom=df[s['low']], left=df['Date']-df['Date'].diff(), right=df['Date'],
              color=s['color'], alpha=.5, legend=s['legend'] if 'legend' in s.keys() else None)

        if set(['line','color']).issubset(s.keys()):
            pStrat.line(df['Date'], df[s['line']], color=s['color'], legend=s['legend'] if 'legend' in s.keys() else s['line'])
    
    #   Trades
    x0, x1, y0, y1,col=[],[],[],[],[]
    for k,g in df[df.State!=0].groupby('TradeNo'):
        x0.append(g.Date.min())
        x1.append(g.Date.max())           
        if g.State.iloc[0]>0:
            col.append(Greens4[0])
            y0.append(g.bEnterLvl.iloc[0])
            y1.append(g.bStopLvl.iloc[-1])       
        else:
            col.append(Reds4[0])
            y0.append(g.sEnterLvl.iloc[0])
            y1.append(g.sStopLvl.iloc[-1])
    pStrat.segment(x0=x0,x1=x1,y0=y0, y1=y1,color=col,line_width=1)
    pStrat.circle(x0, y0, size=3,color=col,line_color=col, fill_alpha=1)
    pStrat.circle(x1, y1, size=3,color='white',line_color=col, fill_alpha=1)
        
    pStrat .legend.location = "top_left"
    
    #Show Plots
    board=column(pRet,row(pDistBar,pDist),row(pBarRet,pTradeRet),pStrat)
    show(board)
    
    #Gridplot version
    #board = gridplot([[pRet],[pDistBar,pDist], [pStrat]])
    #show(board)
