import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime
import time
import warnings

warnings.filterwarnings('ignore', category=FutureWarning)

class FreshAlgoTrader_Fixed:
    def __init__(self, symbol, timeframe=mt5.TIMEFRAME_M15, lot_size=0.01):
        self.symbol = symbol
        self.timeframe = timeframe
        self.lot_size = lot_size
        self.magic_number = 234000
        
        # PineScriptパラメータ
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
        
        # フィルター設定
        self.cons_signals_filter = self.filter_style == "Trending Signals [Mode]"
        self.strong_signals_only = self.filter_style == "Strong [Filter]"
        self.high_vol_signals = self.filter_style == "High Volume [Filter]"
        self.contrarian_only = self.filter_style == "Contrarian Signals [Mode]"
        self.signals_trend_cloud = self.filter_style in ["Smooth [Cloud Filter]", 
                                                          "Scalping [Cloud Filter]", 
                                                          "Scalping+ [Cloud Filter]", 
                                                          "Swing [Cloud Filter]"]
        
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
        """ATR計算（Wilderのスムージング）"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # Wilderのスムージング
        atr = pd.Series(index=df.index, dtype=float)
        atr.iloc[period-1] = tr.iloc[:period].mean()
        
        for i in range(period, len(df)):
            atr.iloc[i] = (atr.iloc[i-1] * (period - 1) + tr.iloc[i]) / period
        
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
            
            if lower_band.iloc[i] > prev_lower or prev_close < prev_lower:
                final_lower = lower_band.iloc[i]
            else:
                final_lower = prev_lower
            
            if upper_band.iloc[i] < prev_upper or prev_close > prev_upper:
                final_upper = upper_band.iloc[i]
            else:
                final_upper = prev_upper
            
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
    
    def dmi(self, df, period):
        """ADX計算"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        plus_dm = high.diff()
        minus_dm = -low.diff()
        
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0
        
        tr = self.atr(df, 1) * period
        
        plus_di = 100 * (plus_dm.ewm(span=period, adjust=False).mean() / tr)
        minus_di = 100 * (minus_dm.ewm(span=period, adjust=False).mean() / tr)
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.ewm(span=period, adjust=False).mean()
        
        return adx
    
    def calculate_ts(self, df):
        """TsFast/TsSlow計算（Contrarian用）"""
        src = df['close']
        
        # RSI計算
        rsi = src.diff()
        gain = rsi.where(rsi > 0, 0)
        loss = -rsi.where(rsi < 0, 0)
        
        avg_gain = gain.ewm(span=50, adjust=False).mean()
        avg_loss = loss.ewm(span=50, adjust=False).mean()
        
        rs = avg_gain / avg_loss
        rsi_value = 100 - (100 / (1 + rs))
        
        # RSII
        rsii = rsi_value.ewm(span=30, adjust=False).mean()
        
        # TR
        tr = abs(rsii - rsii.shift(1))
        
        # WWMA
        wwalpha = 1 / 50
        wwma = pd.Series(0.0, index=df.index)
        for i in range(1, len(df)):
            wwma.iloc[i] = wwalpha * tr.iloc[i] + (1 - wwalpha) * wwma.iloc[i-1]
        
        # ATRRSI
        atrrsi = pd.Series(0.0, index=df.index)
        for i in range(1, len(df)):
            atrrsi.iloc[i] = wwalpha * wwma.iloc[i] + (1 - wwalpha) * atrrsi.iloc[i-1]
        
        # TsFast
        ts_fast = rsii
        
        # TsUP/TsDN
        ts_up = ts_fast + atrrsi * 4.236
        ts_dn = ts_fast - atrrsi * 4.236
        
        # TsSlow
        ts_slow = pd.Series(0.0, index=df.index)
        for i in range(1, len(df)):
            if ts_up.iloc[i] < ts_slow.iloc[i-1]:
                ts_slow.iloc[i] = ts_up.iloc[i]
            elif ts_fast.iloc[i] > ts_slow.iloc[i-1] and ts_fast.iloc[i-1] < ts_slow.iloc[i-1]:
                ts_slow.iloc[i] = ts_dn.iloc[i]
            elif ts_dn.iloc[i] > ts_slow.iloc[i-1]:
                ts_slow.iloc[i] = ts_dn.iloc[i]
            elif ts_fast.iloc[i] < ts_slow.iloc[i-1] and ts_fast.iloc[i-1] > ts_slow.iloc[i-1]:
                ts_slow.iloc[i] = ts_up.iloc[i]
            else:
                ts_slow.iloc[i] = ts_slow.iloc[i-1]
        
        return ts_fast, ts_slow
    
    def analyze_signals(self, df):
        """シグナル分析"""
        close = df['close']
        
        # 各種指標の計算
        df['ema150'] = self.ema(close, self.ema150_period)
        df['ema250'] = self.ema(close, self.ema250_period)
        df['ema200'] = self.ema(close, 200)
        df['hma55'] = self.hma(close, self.hma55_period)
        
        # スーパートレンド
        df['supertrend'] = self.supertrend(df, self.sensitivity, self.st_tuner)
        
        # MACD
        df['macd'], df['macd_signal'] = self.macd(close, self.macd_fast, 
                                                   self.macd_slow, self.macd_signal)
        
        # Donchian Channel Trend
        df['maintrend'] = self.dchannel(df, self.dchannel_period)
        
        # ADX
        df['adx'] = self.dmi(df, 14)
        
        # TsFast/TsSlow
        df['ts_fast'], df['ts_slow'] = self.calculate_ts(df)
        df['cont_bull'] = df['ts_fast'] < 35
        df['cont_bear'] = df['ts_fast'] > 65
        
        # Volume Filter（強制無効化）
        ema_vol_15 = df['tick_volume'].ewm(span=15, adjust=False).mean()
        ema_vol_20 = df['tick_volume'].ewm(span=20, adjust=False).mean()
        ema_vol_25 = df['tick_volume'].ewm(span=25, adjust=False).mean()
        df['vol_filter'] = (ema_vol_15 - ema_vol_20) / ema_vol_25 > 0
        self.high_vol_signals = False  # 強制無効
        
        # クロスオーバー検出
        close_above_st = (close > df['supertrend']).astype(bool)
        close_below_st = (close < df['supertrend']).astype(bool)
        
        close_above_st_prev = close_above_st.shift(1).fillna(False).infer_objects(copy=False)
        close_below_st_prev = close_below_st.shift(1).fillna(False).infer_objects(copy=False)
        
        df['crossover'] = (~close_above_st_prev) & close_above_st
        df['crossunder'] = (~close_below_st_prev) & close_below_st
        
        # クロスオーバー条件
        crossover_shifted = df['crossover'].shift(1).fillna(False).infer_objects(copy=False)
        crossunder_shifted = df['crossunder'].shift(1).fillna(False).infer_objects(copy=False)
        
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
        
        # none条件
        none_filter = pd.Series(True, index=df.index)
        
        # 基本シグナル
        if self.presets == "All Signals":
            base_bull = df['crossover']
            base_bear = df['crossunder']
        else:
            conf_bull_shifted = conf_bull.shift(1).fillna(False).infer_objects(copy=False)
            conf_bear_shifted = conf_bear.shift(1).fillna(False).infer_objects(copy=False)
            base_bull = conf_bull & (~conf_bull_shifted)
            base_bear = conf_bear & (~conf_bear_shifted)
        
        if self.presets == "Trend Scalper":
            base_bull = pd.Series(False, index=df.index)
            base_bear = pd.Series(False, index=df.index)
        
        # フィルター適用
        if self.strong_signals_only:
            strong_filter_bull = close > df['ema200']
            strong_filter_bear = close < df['ema200']
        else:
            strong_filter_bull = none_filter
            strong_filter_bear = none_filter
        
        if self.contrarian_only:
            contrarian_filter_bull = df['cont_bull']
            contrarian_filter_bear = df['cont_bear']
        else:
            contrarian_filter_bull = none_filter
            contrarian_filter_bear = none_filter
        
        if self.cons_signals_filter:
            cons_filter = df['adx'] > 20
        else:
            cons_filter = none_filter
        
        if self.high_vol_signals:
            vol_filter = df['vol_filter']
        else:
            vol_filter = none_filter
        
        if self.signals_trend_cloud:
            trend_cloud_filter_bull = none_filter
            trend_cloud_filter_bear = none_filter
        else:
            trend_cloud_filter_bull = none_filter
            trend_cloud_filter_bear = none_filter
        
        # 全フィルター適用
        df['bull_signal'] = (
            base_bull &
            strong_filter_bull &
            contrarian_filter_bull &
            cons_filter &
            vol_filter &
            trend_cloud_filter_bull
        )
        
        df['bear_signal'] = (
            base_bear &
            strong_filter_bear &
            contrarian_filter_bear &
            cons_filter &
            vol_filter &
            trend_cloud_filter_bear
        )
        
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
        
        digits = symbol_info.digits
        sl = round(sl, digits)
        tp = round(tp, digits)
        
        # フィリングモード自動判定
        filling_type = None
        if symbol_info.filling_mode & 1:
            filling_type = mt5.ORDER_FILLING_FOK
        elif symbol_info.filling_mode & 2:
            filling_type = mt5.ORDER_FILLING_IOC
        elif symbol_info.filling_mode & 4:
            filling_type = mt5.ORDER_FILLING_RETURN
        
        if filling_type is None:
            print("サポートされているフィリングモードが見つかりません")
            return False
        
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
            "type_filling": filling_type,
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
    
    def print_debug_info(self, df):
        """デバッグ情報を表示"""
        i = -1
        print(f"\n{'='*80}")
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] デバッグ情報")
        print(f"{'='*80}")
        
        # バー時刻
        print(f"【バー時刻】")
        print(f"  [-3]: {df['time'].iloc[-3]}")
        print(f"  [-2]: {df['time'].iloc[-2]} ← 確定バー（エントリー判定）")
        print(f"  [-1]: {df['time'].iloc[-1]} ← 形成中")
        
        # 価格情報
        print(f"\n【価格情報（確定バー[-2]）】")
        print(f"  Close[-2]: {df['close'].iloc[-2]:.2f}")
        print(f"  SuperTrend[-2]: {df['supertrend'].iloc[-2]:.2f}")
        print(f"  位置: {'Above ST' if df['close'].iloc[-2] > df['supertrend'].iloc[-2] else 'Below ST'}")
        
        # クロスオーバー判定
        print(f"\n【クロスオーバー判定】")
        close_above_st_2 = df['close'].iloc[-2] > df['supertrend'].iloc[-2]
        close_above_st_3 = df['close'].iloc[-3] > df['supertrend'].iloc[-3]
        print(f"  [-3]: Close={'Above' if close_above_st_3 else 'Below'} ST")
        print(f"  [-2]: Close={'Above' if close_above_st_2 else 'Below'} ST")
        print(f"  → Crossover[-2]: {df['crossover'].iloc[-2]}")
        print(f"  → Crossunder[-2]: {df['crossunder'].iloc[-2]}")
        
        # 主要指標
        print(f"\n【主要指標（最新[-1]）】")
        print(f"  EMA150: {df['ema150'].iloc[i]:.2f}")
        print(f"  EMA250: {df['ema250'].iloc[i]:.2f}")
        print(f"  MACD: {df['macd'].iloc[i]:.2f}")
        print(f"  MainTrend: {df['maintrend'].iloc[i]}")
        print(f"  ADX: {df['adx'].iloc[i]:.2f}")
        
        # フィルター判定
        print(f"\n【Trending Signals [Mode] フィルター】")
        print(f"  ✓ ADX > 20: {df['adx'].iloc[i] > 20} (ADX={df['adx'].iloc[i]:.2f})")
        print(f"  - Volume Filter: 強制無効")
        
        # シグナル
        print(f"\n【シグナル】")
        print(f"  Bull Signal[-3]: {df['bull_signal'].iloc[-3]}")
        print(f"  Bull Signal[-2]: {df['bull_signal'].iloc[-2]} ← エントリー判定")
        print(f"  Bear Signal[-3]: {df['bear_signal'].iloc[-3]}")
        print(f"  Bear Signal[-2]: {df['bear_signal'].iloc[-2]} ← エントリー判定")
        
        # エントリー条件チェック
        print(f"\n【エントリー条件】")
        will_buy = df['bull_signal'].iloc[-2] and not df['bull_signal'].iloc[-3]
        will_sell = df['bear_signal'].iloc[-2] and not df['bear_signal'].iloc[-3]
        print(f"  BUY条件: {will_buy}")
        print(f"  SELL条件: {will_sell}")
        
        print(f"{'='*80}\n")
    
    def run(self, debug_mode=False):
        """メインループ"""
        if not self.initialize_mt5():
            return
        
        print("="*60)
        print("Fresh Algo V24 - デバッグ対応版")
        print(f"通貨ペア: {self.symbol}")
        print(f"時間軸: {self.timeframe}")
        print(f"プリセット: {self.presets}")
        print(f"フィルタースタイル: {self.filter_style}")
        print(f"デバッグモード: {'ON' if debug_mode else 'OFF'}")
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
                    import traceback
                    traceback.print_exc()
                    time.sleep(30)
                    continue
                
                # デバッグモードで詳細表示
                if debug_mode:
                    self.print_debug_info(df)
                
                # シグナルチェック（確定バー[-2]を使用）
                if len(df) >= 3:
                    if df['bull_signal'].iloc[-2] and not df['bull_signal'].iloc[-3]:
                        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] BUY シグナル検出（確定バー）")
                        print(f"時刻: {df['time'].iloc[-2]}")
                        entry = df['close'].iloc[-2]
                        sl, tp1, tp2, tp3 = self.calculate_sl_tp(df, entry, "BUY")
                        self.send_order("BUY", sl, tp1)
                    
                    elif df['bear_signal'].iloc[-2] and not df['bear_signal'].iloc[-3]:
                        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] SELL シグナル検出（確定バー）")
                        print(f"時刻: {df['time'].iloc[-2]}")
                        entry = df['close'].iloc[-2]
                        sl, tp1, tp2, tp3 = self.calculate_sl_tp(df, entry, "SELL")
                        self.send_order("SELL", sl, tp1)
                
                time.sleep(30)
                
        except KeyboardInterrupt:
            print("\n停止しました")
        except Exception as e:
            print(f"\nエラー: {e}")
            import traceback
            traceback.print_exc()
        finally:
            mt5.shutdown()

# 使用例
if __name__ == "__main__":
    trader = FreshAlgoTrader_Fixed(
        symbol="BTCUSD",
        timeframe=mt5.TIMEFRAME_M15,  # M15推奨
        lot_size=0.01
    )
    
    # デバッグモードで起動
    trader.run(debug_mode=True)
    
    # フィルター無効化テスト
    # trader.cons_signals_filter = False
    # trader.run(debug_mode=True)