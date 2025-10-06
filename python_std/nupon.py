import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime
import time
import warnings

# FutureWarningを抑制
warnings.filterwarnings('ignore', category=FutureWarning)

class FreshAlgoTrader_Exact:
    def __init__(self, symbol, timeframe=mt5.TIMEFRAME_M15, lot_size=0.01):
        self.symbol = symbol
        self.timeframe = timeframe
        self.lot_size = lot_size
        self.magic_number = 234000
        
        # 元のPineScriptのパラメータ
        self.sensitivity = 2.4
        self.st_tuner = 10
        self.ema150_period = 150
        self.ema250_period = 250
        self.hma55_period = 55
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9
        self.dchannel_period = 30
        
        self.presets = "All Signals"
        self.filter_style = "Trending Signals [Mode]"
        
        # リスク管理
        self.mult_tp1 = 1.0
        self.mult_tp2 = 2.0
        self.mult_tp3 = 3.0
        self.atr_multiplier = 2.2
        
        self.last_trade_time = 0
        self.min_interval = 60
        
    def initialize_mt5(self):
        """MT5接続"""
        if not mt5.initialize():
            print("MT5初期化失敗")
            return False
        
        account_info = mt5.account_info()
        if account_info:
            account_type = "デモ" if account_info.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO else "リアル"
            print(f"接続成功 - 口座: {account_info.login} ({account_type})")
            print(f"残高: {account_info.balance} {account_info.currency}")
        return True
    
    def get_rates(self, count=500):
        """データ取得"""
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, count)
        if rates is None:
            return None
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df
    
    def ema(self, data, period):
        """EMA計算"""
        return data.ewm(span=period, adjust=False).mean()
    
    def atr(self, df, period):
        """ATR計算"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        return atr
    
    def supertrend(self, df, multiplier, period):
        """スーパートレンド計算"""
        src = df['close'].copy()
        atr_values = self.atr(df, period)
        
        upper_band = src + (multiplier * atr_values)
        lower_band = src - (multiplier * atr_values)
        
        supertrend = pd.Series(np.nan, index=df.index, dtype=float)
        direction = pd.Series(1, index=df.index, dtype=int)
        
        supertrend.iloc[0] = lower_band.iloc[0]
        
        for i in range(1, len(df)):
            if pd.isna(atr_values.iloc[i]):
                continue
                
            prev_lower = lower_band.iloc[i-1]
            prev_upper = upper_band.iloc[i-1]
            prev_close = src.iloc[i-1]
            curr_close = src.iloc[i]
            prev_st = supertrend.iloc[i-1]
            
            # lowerBandの更新
            if lower_band.iloc[i] > prev_lower or prev_close < prev_lower:
                final_lower = lower_band.iloc[i]
            else:
                final_lower = prev_lower
            
            # upperBandの更新
            if upper_band.iloc[i] < prev_upper or prev_close > prev_upper:
                final_upper = upper_band.iloc[i]
            else:
                final_upper = prev_upper
            
            # 方向の決定
            if pd.isna(prev_st):
                direction.iloc[i] = 1
                supertrend.iloc[i] = final_lower
            elif prev_st == prev_upper:
                if curr_close > final_upper:
                    direction.iloc[i] = 1
                    supertrend.iloc[i] = final_lower
                else:
                    direction.iloc[i] = -1
                    supertrend.iloc[i] = final_upper
            else:
                if curr_close < final_lower:
                    direction.iloc[i] = -1
                    supertrend.iloc[i] = final_upper
                else:
                    direction.iloc[i] = 1
                    supertrend.iloc[i] = final_lower
        
        return supertrend
    
    def hma(self, data, period):
        """Hull Moving Average"""
        half_length = int(period / 2)
        sqrt_length = int(np.sqrt(period))
        
        def wma(series, length):
            weights = np.arange(1, length + 1)
            def calc(x):
                if len(x) < length:
                    return np.nan
                return np.sum(weights * x) / np.sum(weights)
            return series.rolling(length).apply(calc, raw=True)
        
        wma1 = wma(data, half_length)
        wma2 = wma(data, period)
        raw_hma = 2 * wma1 - wma2
        hma_result = wma(raw_hma, sqrt_length)
        
        return hma_result
    
    def dchannel(self, df, length):
        """Donchian Channel Trend"""
        hh = df['high'].rolling(window=length).max()
        ll = df['low'].rolling(window=length).min()
        
        trend = pd.Series(0, index=df.index, dtype=int)
        
        for i in range(length, len(df)):
            if df['close'].iloc[i] > hh.iloc[i-1]:
                trend.iloc[i] = 1
            elif df['close'].iloc[i] < ll.iloc[i-1]:
                trend.iloc[i] = -1
            else:
                trend.iloc[i] = trend.iloc[i-1]
        
        return trend
    
    def macd(self, data, fast, slow, signal):
        """MACD計算"""
        ema_fast = self.ema(data, fast)
        ema_slow = self.ema(data, slow)
        macd_line = ema_fast - ema_slow
        signal_line = self.ema(macd_line, signal)
        return macd_line, signal_line
    
    def analyze_signals(self, df):
        """シグナル分析（警告修正版）"""
        close = df['close']
        
        # 各種指標の計算
        df['ema150'] = self.ema(close, self.ema150_period)
        df['ema250'] = self.ema(close, self.ema250_period)
        df['hma55'] = self.hma(close, self.hma55_period)
        
        # スーパートレンド
        df['supertrend'] = self.supertrend(df, self.sensitivity, self.st_tuner)
        
        # MACD
        df['macd'], df['macd_signal'] = self.macd(close, self.macd_fast, 
                                                   self.macd_slow, self.macd_signal)
        
        # Donchian Channel Trend
        df['maintrend'] = self.dchannel(df, self.dchannel_period)
        
        # クロスオーバー検出（警告修正）
        close_above_st = (close > df['supertrend']).astype(bool)
        close_below_st = (close < df['supertrend']).astype(bool)
        
        # infer_objects() を使用してFutureWarningを回避
        close_above_st_prev = close_above_st.shift(1)
        close_above_st_prev = close_above_st_prev.fillna(False).infer_objects(copy=False)
        
        close_below_st_prev = close_below_st.shift(1)
        close_below_st_prev = close_below_st_prev.fillna(False).infer_objects(copy=False)
        
        df['crossover'] = (~close_above_st_prev) & close_above_st
        df['crossunder'] = (~close_below_st_prev) & close_below_st
        
        # クロスオーバー条件
        crossover_shifted = df['crossover'].shift(1)
        crossover_shifted = crossover_shifted.fillna(False).infer_objects(copy=False)
        
        crossunder_shifted = df['crossunder'].shift(1)
        crossunder_shifted = crossunder_shifted.fillna(False).infer_objects(copy=False)
        
        crossover_condition = (
            df['crossover'] | 
            (crossover_shifted & (df['maintrend'].shift(1) < 0))
        )
        
        crossunder_condition = (
            df['crossunder'] | 
            (crossunder_shifted & (df['maintrend'].shift(1) > 0))
        )
        
        # 確認シグナル
        conf_bull = (
            crossover_condition &
            (df['macd'] > 0) &
            (df['macd'] > df['macd'].shift(1)) &
            (df['ema150'] > df['ema250']) &
            (df['hma55'] > df['hma55'].shift(2)) &
            (df['maintrend'] > 0)
        )
        
        conf_bear = (
            crossunder_condition &
            (df['macd'] < 0) &
            (df['macd'] < df['macd'].shift(1)) &
            (df['ema150'] < df['ema250']) &
            (df['hma55'] < df['hma55'].shift(2)) &
            (df['maintrend'] < 0)
        )
        
        # シグナル
        if self.presets == "All Signals":
            df['bull_signal'] = df['crossover']
            df['bear_signal'] = df['crossunder']
        else:
            conf_bull_shifted = conf_bull.shift(1)
            conf_bull_shifted = conf_bull_shifted.fillna(False).infer_objects(copy=False)
            
            conf_bear_shifted = conf_bear.shift(1)
            conf_bear_shifted = conf_bear_shifted.fillna(False).infer_objects(copy=False)
            
            df['bull_signal'] = conf_bull & (~conf_bull_shifted)
            df['bear_signal'] = conf_bear & (~conf_bear_shifted)
        
        # NaNを False に変換
        df['bull_signal'] = df['bull_signal'].fillna(False).infer_objects(copy=False)
        df['bear_signal'] = df['bear_signal'].fillna(False).infer_objects(copy=False)
        
        return df
    
    def calculate_sl_tp(self, df, entry_price, signal_type):
        """SL/TP計算"""
        atr_value = self.atr(df, 14).iloc[-1]
        
        if pd.isna(atr_value) or atr_value == 0:
            atr_value = entry_price * 0.01
        
        if signal_type == "BUY":
            sl = entry_price - (atr_value * self.atr_multiplier)
            risk = entry_price - sl
            tp1 = entry_price + (risk * self.mult_tp1)
            tp2 = entry_price + (risk * self.mult_tp2)
            tp3 = entry_price + (risk * self.mult_tp3)
        else:
            sl = entry_price + (atr_value * self.atr_multiplier)
            risk = sl - entry_price
            tp1 = entry_price - (risk * self.mult_tp1)
            tp2 = entry_price - (risk * self.mult_tp2)
            tp3 = entry_price - (risk * self.mult_tp3)
        
        return sl, tp1, tp2, tp3
    
    def send_order(self, signal_type, sl, tp):
        """注文送信"""
        current_time = time.time()
        if current_time - self.last_trade_time < self.min_interval:
            print(f"取引間隔制限: {self.min_interval}秒待機")
            return False
        
        symbol_info = mt5.symbol_info(self.symbol)
        if symbol_info is None:
            print(f"{self.symbol}が見つかりません")
            return False
            
        if not symbol_info.visible:
            if not mt5.symbol_select(self.symbol, True):
                print(f"{self.symbol}を選択できません")
                return False
        
        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            print("価格取得失敗")
            return False
            
        price = tick.ask if signal_type == "BUY" else tick.bid
        
        # 価格の正規化
        digits = symbol_info.digits
        sl = round(sl, digits)
        tp = round(tp, digits)
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": self.lot_size,
            "type": mt5.ORDER_TYPE_BUY if signal_type == "BUY" else mt5.ORDER_TYPE_SELL,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": self.magic_number,
            "comment": "FreshAlgo",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            self.last_trade_time = current_time
            print(f"[OK] {signal_type} @ {price}, SL: {sl}, TP: {tp}")
            return True
        else:
            print(f"[NG] 注文失敗: {result.comment} (code: {result.retcode})")
            return False
    
    def check_positions(self):
        """ポジション確認"""
        positions = mt5.positions_get(symbol=self.symbol, magic=self.magic_number)
        return len(positions) if positions else 0
    
    def run(self):
        """メインループ"""
        if not self.initialize_mt5():
            return
        
        print("="*60)
        print("Fresh Algo V24 - PineScript完全再現版")
        print(f"通貨ペア: {self.symbol}")
        print(f"時間軸: {self.timeframe}")
        print(f"プリセット: {self.presets}")
        print("="*60)
        
        try:
            while True:
                if self.check_positions() > 0:
                    time.sleep(30)
                    continue
                
                df = self.get_rates(500)
                if df is None or len(df) < 300:
                    print("データ取得失敗")
                    time.sleep(30)
                    continue
                
                try:
                    df = self.analyze_signals(df)
                except Exception as e:
                    print(f"分析エラー: {e}")
                    time.sleep(30)
                    continue
                
                # シグナルチェック
                if len(df) >= 2:
                    if df['bull_signal'].iloc[-1] and not df['bull_signal'].iloc[-2]:
                        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] BUY シグナル検出")
                        entry = df['close'].iloc[-1]
                        sl, tp1, tp2, tp3 = self.calculate_sl_tp(df, entry, "BUY")
                        self.send_order("BUY", sl, tp1)
                    
                    elif df['bear_signal'].iloc[-1] and not df['bear_signal'].iloc[-2]:
                        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] SELL シグナル検出")
                        entry = df['close'].iloc[-1]
                        sl, tp1, tp2, tp3 = self.calculate_sl_tp(df, entry, "SELL")
                        self.send_order("SELL", sl, tp1)
                
                time.sleep(30)
                
        except KeyboardInterrupt:
            print("\n停止しました")
        except Exception as e:
            print(f"\nエラー: {e}")
        finally:
            mt5.shutdown()

# 使用例
if __name__ == "__main__":
    trader = FreshAlgoTrader_Exact(
        symbol="BTCUSD",
        timeframe=mt5.TIMEFRAME_M1,
        lot_size=0.01
    )
    
    trader.run()