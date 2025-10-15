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
MAGIC_NUMBER = 1234 # unique identifier for this bot's order
GRID_TAG = "enhanced grid" # order tag
CHECK_INTERVAL = 1.0 # sec

# 
def _discover_terminals() -> list[str]:
    paths = []
    if psutil:
        for p in psutil.process_iter(attr=["name", "exe"]):
            if "terminal64.exe" in (p.info.get("name") or "").lower(): # name = p.name()だと遅いしps止まったりするとエラーになる。info.get()だとpsutilが内部的にinfo_dict = p.name()みたいな処理して
               exe = p.info.get("exe") or "" # except節でinfo_dict["name"] = None　みたいにエラーも処理してくれてる
               if exe and exe not in paths:
                   path.append(exe)
    return paths
