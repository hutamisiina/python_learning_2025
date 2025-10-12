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
DEF_LOTS = 0.02
DEF_ORDERS_SIDE = 10
DEF_MULTIPLIER = 2.0
DEF_LOOP = 10
DEF_MAX_RISK = 50.0
