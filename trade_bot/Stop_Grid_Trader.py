import tkinter as tk
from tkinter import messagebox, ttk
import threading, time, sys
import MetaTrader5 as mt5
import numpy as np
from datetime import datetime 

# psutil = None でスキップするなら手動で使いたいMT5のパスを入力する処理書かないと、、
try: 
    import psutil
except ImportError:
    psutil = None

# constants
DEF_SYMBOL = "BTCUSD"
DEF_DIGITS = 2
DEF_LOTS = 0.02 #Lot size = Dick size
DEF_ORDERS_SIDE = 10 # 0.02lot片側に10注文ずつだと大体残高10万JPYは欲しい
DEF_MULTIPLIER = 2.0  #スプレッドのn倍間隔で指値置く default 2.0
DEF_LOOP = 10 # 1LOOP = 上下どちらかの指値を食ったら終了してどこかの哺乳類みたいに次の指値をばら撒く
DEF_MAX_RISK = 50.0 # % 耐えられるのか?その手取りで

# trend 
DEF_USE_TREND = True
DEF_USE_DYNAMIC = True
DEVIATION = 100 # points