import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time

class FreshAlgoTrader:
    def __init__(self, symbol, timeframe, lot_size=0.01):
        self.symbol = symbol
        self.timeframe = timeframe
        self.lot_size = lot_size
        self.magic_number = 234000
        
        # パラメータ（Pineスクリプトから）
        self.sensitivity = 2.4
        self.st_tuner = 10
        self.ema150_period = 150
        self.ema250_period = 250
        self.rsi_period = 50
        self.rsi_smooth = 30
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9
        
        # リスク管理
        self.use_perc_sl = False
        self.perc_trailing_sl = 1.0
        self.mult_tp1 = 1.0
        self.mult_tp2 = 2.0
        self.mult_tp3 = 3.0
        
    def initialize_mt5(self):
        """MT5に接続"""
        if not mt5.initialize():
            print("MT5初期化失敗")
            return False
        print(f"MT5接続成功: {mt5.version()}")
        return True
    
    def get_rates(self, count=500):
        """過去のレートデータを取得"""
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, count)
        if rates is None:
            print("レートデータ取得失敗")
            return None
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df
    
    def calculate_ema(self, data, period):
        """EMAを計算"""
        return data.ewm(span=period, adjust=False).mean()
    
    def calculate_supertrend(self, df, multiplier, period):
        """スーパートレンド指標を計算"""
        hl2 = (df['high'] + df['low']) / 2
        
        # ATRを計算
        df['tr'] = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                abs(df['high'] - df['close'].shift(1)),
                abs(df['low'] - df['close'].shift(1))
            )
        )
        atr = df['tr'].rolling(window=period).mean()
        
        # バンドを計算
        upper_band = hl2 + (multiplier * atr)
        lower_band = hl2 - (multiplier * atr)
        
        # スーパートレンドを計算
        supertrend = pd.Series(index=df.index, dtype=float)
        direction = pd.Series(index=df.index, dtype=int)
        
        for i in range(1, len(df)):
            if pd.isna(supertrend.iloc[i-1]):
                supertrend.iloc[i] = lower_band.iloc[i]
                direction.iloc[i] = 1
            else:
                if df['close'].iloc[i] > supertrend.iloc[i-1]:
                    direction.iloc[i] = 1
                    supertrend.iloc[i] = lower_band.iloc[i]
                    if supertrend.iloc[i] < supertrend.iloc[i-1]:
                        supertrend.iloc[i] = supertrend.iloc[i-1]
                else:
                    direction.iloc[i] = -1
                    supertrend.iloc[i] = upper_band.iloc[i]
                    if supertrend.iloc[i] > supertrend.iloc[i-1]:
                        supertrend.iloc[i] = supertrend.iloc[i-1]
        
        return supertrend, direction
    
    def calculate_rsi(self, data, period):
        """RSIを計算"""
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_macd(self, data, fast, slow, signal):
        """MACDを計算"""
        ema_fast = self.calculate_ema(data, fast)
        ema_slow = self.calculate_ema(data, slow)
        macd_line = ema_fast - ema_slow
        signal_line = self.calculate_ema(macd_line, signal)
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram
    
    def analyze_signals(self, df):
        """トレードシグナルを分析"""
        # 各種指標を計算
        df['ema150'] = self.calculate_ema(df['close'], self.ema150_period)
        df['ema250'] = self.calculate_ema(df['close'], self.ema250_period)
        df['ema200'] = self.calculate_ema(df['close'], 200)
        df['hma55'] = self.calculate_hma(df['close'], 55)
        
        # スーパートレンドを計算
        df['supertrend'], df['st_direction'] = self.calculate_supertrend(
            df, self.sensitivity, self.st_tuner
        )
        
        # RSIを計算
        rsi_raw = self.calculate_rsi(df['close'], self.rsi_period)
        df['rsi_smooth'] = self.calculate_ema(rsi_raw, self.rsi_smooth)
        
        # MACDを計算
        df['macd'], df['macd_signal'], df['macd_hist'] = self.calculate_macd(
            df['close'], self.macd_fast, self.macd_slow, self.macd_signal
        )
        
        # トレンド判定
        df['maintrend'] = self.calculate_dchannel(df, 30)
        
        # ブルシグナルの条件
        bull_condition = (
            ((df['close'] > df['supertrend']) | 
             ((df['close'].shift(1) > df['supertrend'].shift(1)) & 
              (df['maintrend'].shift(1) < 0))) &
            (df['macd'] > 0) &
            (df['macd'] > df['macd'].shift(1)) &
            (df['ema150'] > df['ema250']) &
            (df['hma55'] > df['hma55'].shift(2)) &
            (df['maintrend'] > 0)
        )
        
        # ベアシグナルの条件
        bear_condition = (
            ((df['close'] < df['supertrend']) | 
             ((df['close'].shift(1) < df['supertrend'].shift(1)) & 
              (df['maintrend'].shift(1) > 0))) &
            (df['macd'] < 0) &
            (df['macd'] < df['macd'].shift(1)) &
            (df['ema150'] < df['ema250']) &
            (df['hma55'] < df['hma55'].shift(2)) &
            (df['maintrend'] < 0)
        )
        
        df['bull_signal'] = bull_condition
        df['bear_signal'] = bear_condition
        
        return df
    
    def calculate_hma(self, data, period):
        """Hull移動平均を計算"""
        half_length = int(period / 2)
        sqrt_length = int(np.sqrt(period))
        
        wma_half = data.rolling(window=half_length).apply(
            lambda x: np.sum(x * np.arange(1, half_length + 1)) / np.sum(np.arange(1, half_length + 1))
        )
        wma_full = data.rolling(window=period).apply(
            lambda x: np.sum(x * np.arange(1, period + 1)) / np.sum(np.arange(1, period + 1))
        )
        
        raw_hma = 2 * wma_half - wma_full
        hma = raw_hma.rolling(window=sqrt_length).apply(
            lambda x: np.sum(x * np.arange(1, sqrt_length + 1)) / np.sum(np.arange(1, sqrt_length + 1))
        )
        
        return hma
    
    def calculate_dchannel(self, df, length):
        """ドンチャンチャネルトレンドを計算"""
        highest = df['high'].rolling(window=length).max()
        lowest = df['low'].rolling(window=length).min()
        
        trend = pd.Series(0, index=df.index)
        for i in range(length, len(df)):
            if df['close'].iloc[i] > highest.iloc[i-1]:
                trend.iloc[i] = 1
            elif df['close'].iloc[i] < lowest.iloc[i-1]:
                trend.iloc[i] = -1
            else:
                trend.iloc[i] = trend.iloc[i-1]
        
        return trend
    
    def calculate_stop_loss_take_profit(self, entry_price, signal_type, atr):
        """ストップロスとテイクプロフィットを計算"""
        if signal_type == "BUY":
            sl = entry_price - (atr * 2.2)
            tp1 = entry_price + (entry_price - sl) * self.mult_tp1
            tp2 = entry_price + (entry_price - sl) * self.mult_tp2
            tp3 = entry_price + (entry_price - sl) * self.mult_tp3
        else:  # SELL
            sl = entry_price + (atr * 2.2)
            tp1 = entry_price - (sl - entry_price) * self.mult_tp1
            tp2 = entry_price - (sl - entry_price) * self.mult_tp2
            tp3 = entry_price - (sl - entry_price) * self.mult_tp3
        
        return sl, tp1, tp2, tp3
    
    def send_order(self, signal_type, sl, tp):
        """注文を送信"""
        symbol_info = mt5.symbol_info(self.symbol)
        if symbol_info is None:
            print(f"{self.symbol}が見つかりません")
            return False
        
        if not symbol_info.visible:
            if not mt5.symbol_select(self.symbol, True):
                print(f"{self.symbol}を選択できません")
                return False
        
        point = symbol_info.point
        price = mt5.symbol_info_tick(self.symbol).ask if signal_type == "BUY" else mt5.symbol_info_tick(self.symbol).bid
        
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
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"注文失敗: {result.retcode}")
            return False
        
        print(f"注文成功: {signal_type} @ {price}, SL: {sl}, TP: {tp}")
        return True
    
    def check_open_positions(self):
        """オープンポジションをチェック"""
        positions = mt5.positions_get(symbol=self.symbol)
        return len(positions) if positions else 0
    
    def run(self):
        """メインループ"""
        if not self.initialize_mt5():
            return
        
        print(f"自動売買開始: {self.symbol}")
        print("デモアカウントで十分にテストしてください！")
        
        try:
            while True:
                # オープンポジションをチェック
                if self.check_open_positions() > 0:
                    print("既存のポジションがあります。新規エントリーをスキップ")
                    time.sleep(60)
                    continue
                
                # データを取得して分析
                df = self.get_rates(500)
                if df is None:
                    time.sleep(60)
                    continue
                
                df = self.analyze_signals(df)
                
                # 最新のシグナルをチェック
                if df['bull_signal'].iloc[-1]:
                    print("★ ブルシグナル検出")
                    atr = df['tr'].iloc[-20:].mean()
                    entry_price = df['close'].iloc[-1]
                    sl, tp1, tp2, tp3 = self.calculate_stop_loss_take_profit(
                        entry_price, "BUY", atr
                    )
                    self.send_order("BUY", sl, tp1)
                
                elif df['bear_signal'].iloc[-1]:
                    print("★ ベアシグナル検出")
                    atr = df['tr'].iloc[-20:].mean()
                    entry_price = df['close'].iloc[-1]
                    sl, tp1, tp2, tp3 = self.calculate_stop_loss_take_profit(
                        entry_price, "SELL", atr
                    )
                    self.send_order("SELL", sl, tp1)
                
                # 1分待機
                time.sleep(60)
                
        except KeyboardInterrupt:
            print("\n自動売買を停止しました")
        finally:
            mt5.shutdown()

# 使用例
if __name__ == "__main__":
    # 設定
    SYMBOL = "USDJPY"  # 通貨ペア
    TIMEFRAME = mt5.TIMEFRAME_M15  # 15分足
    LOT_SIZE = 0.01  # ロットサイズ（デモで小さく）
    
    # トレーダーを初期化して実行
    trader = FreshAlgoTrader(SYMBOL, TIMEFRAME, LOT_SIZE)
    trader.run()