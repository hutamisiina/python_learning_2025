import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
from collections import deque

class MarketStructureTrader:
    def __init__(self, symbol="USDJPY", timeframe=mt5.TIMEFRAME_M15, lot_size=0.1):
        self.symbol = symbol
        self.timeframe = timeframe
        self.lot_size = lot_size
        self.magic_number = 234567
        
        # Structure tracking
        self.pivot_highs = deque(maxlen=5)
        self.pivot_lows = deque(maxlen=5)
        self.pivot_high_times = deque(maxlen=5)
        self.pivot_low_times = deque(maxlen=5)
        
        self.structure_direction = "bullish"
        self.last_bos_time = None
        
        # Liquidity levels
        self.bottom_tlq_price = None
        self.top_tlq_price = None
        self.bottom_ilq_price = None
        self.top_ilq_price = None
        
        # Signals
        self.is_price_efficient = False
        
    def initialize_mt5(self):
        """MT5への接続"""
        if not mt5.initialize():
            print("MT5の初期化に失敗しました")
            return False
        print(f"MT5に接続しました - {self.symbol}")
        return True
    
    def get_rates(self, count=500):
        """価格データを取得"""
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, count)
        if rates is None:
            print("価格データの取得に失敗しました")
            return None
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df
    
    def is_bullish_candle(self, row):
        """陽線判定"""
        return row['close'] > row['open']
    
    def is_bearish_candle(self, row):
        """陰線判定"""
        return row['close'] < row['open']
    
    def find_swing_points(self, df, lookback=3):
        """スイングハイ・ローの検出"""
        df['swing_high'] = False
        df['swing_low'] = False
        
        for i in range(lookback, len(df) - lookback):
            # Swing High
            if all(df.iloc[i]['high'] > df.iloc[i-j]['high'] for j in range(1, lookback+1)) and \
               all(df.iloc[i]['high'] > df.iloc[i+j]['high'] for j in range(1, lookback+1)):
                df.at[i, 'swing_high'] = True
            
            # Swing Low
            if all(df.iloc[i]['low'] < df.iloc[i-j]['low'] for j in range(1, lookback+1)) and \
               all(df.iloc[i]['low'] < df.iloc[i+j]['low'] for j in range(1, lookback+1)):
                df.at[i, 'swing_low'] = True
        
        return df
    
    def update_market_structure(self, df):
        """Market Structureの更新"""
        df = self.find_swing_points(df)
        
        # 最新のスイングポイントを取得
        swing_highs = df[df['swing_high'] == True].tail(5)
        swing_lows = df[df['swing_low'] == True].tail(5)
        
        if len(swing_highs) > 0:
            for idx, row in swing_highs.iterrows():
                if len(self.pivot_highs) == 0 or row['high'] != list(self.pivot_highs)[0]:
                    self.pivot_highs.appendleft(row['high'])
                    self.pivot_high_times.appendleft(row['time'])
        
        if len(swing_lows) > 0:
            for idx, row in swing_lows.iterrows():
                if len(self.pivot_lows) == 0 or row['low'] != list(self.pivot_lows)[0]:
                    self.pivot_lows.appendleft(row['low'])
                    self.pivot_low_times.appendleft(row['time'])
        
        return df
    
    def detect_structure_break(self, current_price):
        """Break of Structure（BOS）の検出"""
        bos_signal = None
        
        # Bearish BOS: 下のTLQを下抜け
        if self.bottom_tlq_price and current_price < self.bottom_tlq_price:
            if self.structure_direction != "bearish":
                bos_signal = "BEARISH_BOS"
                self.structure_direction = "bearish"
                self.last_bos_time = datetime.now()
                print(f"🔴 Bearish BOS検出: {current_price} < {self.bottom_tlq_price}")
        
        # Bullish BOS: 上のTLQを上抜け
        if self.top_tlq_price and current_price > self.top_tlq_price:
            if self.structure_direction != "bullish":
                bos_signal = "BULLISH_BOS"
                self.structure_direction = "bullish"
                self.last_bos_time = datetime.now()
                print(f"🟢 Bullish BOS検出: {current_price} > {self.top_tlq_price}")
        
        return bos_signal
    
    def update_liquidity_levels(self):
        """流動性レベルの更新"""
        if len(self.pivot_highs) < 2 or len(self.pivot_lows) < 2:
            return
        
        ph = list(self.pivot_highs)
        pl = list(self.pivot_lows)
        
        # Higher High検出 → Bullish Structure
        if ph[0] > ph[1] and ph[0] > ph[2]:
            # TLQ = 前回のLowの上位
            self.bottom_tlq_price = min(pl[0], pl[1]) if len(pl) > 1 else pl[0]
            self.top_tlq_price = None
            
            # ILQ = 最新のLow
            self.bottom_ilq_price = pl[0]
            self.top_ilq_price = None
        
        # Lower Low検出 → Bearish Structure
        if pl[0] < pl[1] and pl[0] < pl[2]:
            # TLQ = 前回のHighの下位
            self.top_tlq_price = max(ph[0], ph[1]) if len(ph) > 1 else ph[0]
            self.bottom_tlq_price = None
            
            # ILQ = 最新のHigh
            self.top_ilq_price = ph[0]
            self.bottom_ilq_price = None
    
    def detect_msu(self, df):
        """MSU（Market Structure Update）の検出"""
        if len(self.pivot_highs) < 2 or len(self.pivot_lows) < 2:
            return None
        
        ph = list(self.pivot_highs)
        pl = list(self.pivot_lows)
        current_high = df.iloc[-1]['high']
        current_low = df.iloc[-1]['low']
        
        # Bearish MSU: ph0 < ph1 and pl0 < pl1 and current_high in range
        is_bearish_msu = (ph[0] < ph[1]) and (pl[0] < pl[1]) and \
                         (current_high > ph[0] and current_high < ph[1])
        
        # Bullish MSU: pl0 > pl1 and ph0 > ph1 and current_low in range
        is_bullish_msu = (pl[0] > pl[1]) and (ph[0] > ph[1]) and \
                         (current_low < pl[0] and current_low > pl[1])
        
        if is_bearish_msu:
            return "BEARISH_MSU"
        elif is_bullish_msu:
            return "BULLISH_MSU"
        
        return None
    
    def generate_trading_signal(self, df):
        """総合的な売買シグナル生成"""
        current_price = df.iloc[-1]['close']
        current_high = df.iloc[-1]['high']
        current_low = df.iloc[-1]['low']
        
        # Market Structure更新
        df = self.update_market_structure(df)
        self.update_liquidity_levels()
        
        # BOS検出
        bos_signal = self.detect_structure_break(current_price)
        
        # MSU検出
        msu_signal = self.detect_msu(df)
        
        # シグナル判定
        signal = None
        reason = []
        
        # 【エントリーロジック1】BOS後のリテスト
        if bos_signal == "BULLISH_BOS":
            if self.bottom_ilq_price and current_price > self.bottom_ilq_price:
                signal = "BUY"
                reason.append("Bullish BOS + Price above ILQ")
        
        elif bos_signal == "BEARISH_BOS":
            if self.top_ilq_price and current_price < self.top_ilq_price:
                signal = "SELL"
                reason.append("Bearish BOS + Price below ILQ")
        
        # 【エントリーロジック2】MSUシグナル
        if msu_signal == "BULLISH_MSU" and self.structure_direction == "bullish":
            signal = "BUY"
            reason.append("Bullish MSU in Bullish Structure")
        
        elif msu_signal == "BEARISH_MSU" and self.structure_direction == "bearish":
            signal = "SELL"
            reason.append("Bearish MSU in Bearish Structure")
        
        # 【エントリーロジック3】ILQリテスト
        if self.structure_direction == "bullish" and self.bottom_ilq_price:
            if current_low <= self.bottom_ilq_price * 1.001 and current_price > self.bottom_ilq_price:
                signal = "BUY"
                reason.append("ILQ Retest (Bullish)")
        
        if self.structure_direction == "bearish" and self.top_ilq_price:
            if current_high >= self.top_ilq_price * 0.999 and current_price < self.top_ilq_price:
                signal = "SELL"
                reason.append("ILQ Retest (Bearish)")
        
        if signal:
            print(f"\n{'='*60}")
            print(f"🎯 {signal}シグナル検出!")
            print(f"理由: {', '.join(reason)}")
            print(f"構造方向: {self.structure_direction}")
            print(f"現在価格: {current_price}")
            if self.bottom_ilq_price:
                print(f"Bottom ILQ: {self.bottom_ilq_price}")
            if self.top_ilq_price:
                print(f"Top ILQ: {self.top_ilq_price}")
            print(f"{'='*60}\n")
        
        return signal
    
    def calculate_sl_tp(self, order_type, entry_price):
        """ストップロスとテイクプロフィットの計算"""
        symbol_info = mt5.symbol_info(self.symbol)
        point = symbol_info.point
        
        # ATRベースのSL/TP計算（簡略版）
        atr_multiplier_sl = 1.5
        atr_multiplier_tp = 3.0
        
        # 簡易的なATR代替：直近のボラティリティ
        df = self.get_rates(count=20)
        atr = (df['high'] - df['low']).mean()
        
        if order_type == mt5.ORDER_TYPE_BUY:
            sl = entry_price - (atr * atr_multiplier_sl)
            tp = entry_price + (atr * atr_multiplier_tp)
        else:
            sl = entry_price + (atr * atr_multiplier_sl)
            tp = entry_price - (atr * atr_multiplier_tp)
        
        return sl, tp
    
    def open_position(self, order_type):
        """ポジションを開く"""
        symbol_info = mt5.symbol_info(self.symbol)
        if symbol_info is None:
            print(f"{self.symbol}が見つかりません")
            return False
        
        if not symbol_info.visible:
            if not mt5.symbol_select(self.symbol, True):
                print(f"{self.symbol}の選択に失敗しました")
                return False
        
        tick = mt5.symbol_info_tick(self.symbol)
        price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid
        
        sl, tp = self.calculate_sl_tp(order_type, price)
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": self.lot_size,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": self.magic_number,
            "comment": "Market Structure Bot",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"❌ 注文失敗: {result.retcode} - {result.comment}")
            return False
        
        order_type_str = "買い" if order_type == mt5.ORDER_TYPE_BUY else "売り"
        print(f"✅ {order_type_str}注文成功: 価格={price:.5f}, SL={sl:.5f}, TP={tp:.5f}")
        return True
    
    def check_positions(self):
        """現在のポジションを確認"""
        positions = mt5.positions_get(symbol=self.symbol, magic=self.magic_number)
        return positions if positions else []
    
    def close_position(self, position):
        """ポジションを閉じる"""
        tick = mt5.symbol_info_tick(self.symbol)
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": position.volume,
            "type": mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
            "position": position.ticket,
            "price": tick.bid if position.type == mt5.ORDER_TYPE_BUY else tick.ask,
            "deviation": 20,
            "magic": self.magic_number,
            "comment": "Close by bot",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"ポジション決済失敗: {result.retcode}")
            return False
        
        print(f"✅ ポジション決済成功: #{position.ticket}")
        return True
    
    def run(self, check_interval=60):
        """メインループ"""
        if not self.initialize_mt5():
            return
        
        print(f"\n{'='*60}")
        print(f"Market Structure自動売買開始")
        print(f"通貨ペア: {self.symbol}")
        print(f"時間足: {self.timeframe}")
        print(f"ロットサイズ: {self.lot_size}")
        print(f"{'='*60}\n")
        
        try:
            while True:
                # 価格データ取得
                df = self.get_rates()
                if df is None:
                    time.sleep(check_interval)
                    continue
                
                # シグナル生成
                signal = self.generate_trading_signal(df)
                
                # 現在のポジション確認
                positions = self.check_positions()
                
                # エントリー判定
                if signal == 'BUY' and len(positions) == 0:
                    self.open_position(mt5.ORDER_TYPE_BUY)
                    
                elif signal == 'SELL' and len(positions) == 0:
                    self.open_position(mt5.ORDER_TYPE_SELL)
                
                # ポジション状況表示
                if len(positions) > 0:
                    for pos in positions:
                        pnl = pos.profit
                        pos_type = "買い" if pos.type == mt5.ORDER_TYPE_BUY else "売り"
                        print(f"保有中: {pos_type} | 損益: {pnl:.2f} | チケット: #{pos.ticket}")
                
                # 待機
                time.sleep(check_interval)
                
        except KeyboardInterrupt:
            print("\n自動売買を停止します...")
        finally:
            mt5.shutdown()


# 使用例
if __name__ == "__main__":
    trader = MarketStructureTrader(
        symbol="USDJPY",                    # 通貨ペア
        timeframe=mt5.TIMEFRAME_M15,        # 15分足
        lot_size=0.1                        # ロットサイズ
    )
    
    # 自動売買開始（60秒ごとにチェック）
    trader.run(check_interval=60)
