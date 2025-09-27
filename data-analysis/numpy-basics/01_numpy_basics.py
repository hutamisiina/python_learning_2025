"""
NumPy基礎 - Day 1
学習日: 2025-09-27
トピック: 配列の作成と基本操作
"""

import numpy as np

print("="*50)
print(" NumPy学習 Day 1：配列の基礎")
print("="*50)

# 1. 配列の作成
print("\n【1. 配列の作成】")
print("-"*30)

# Pythonリストから配列を作成
python_list = [1, 2, 3, 4, 5]
numpy_array = np.array(python_list)

print(f"Pythonリスト: {python_list}")
print(f"NumPy配列: {numpy_array}")
print(f"配列の型: {type(numpy_array)}")
print(f"データ型: {numpy_array.dtype}")

# 2. 便利な配列生成関数
print("\n【2. 便利な配列生成関数】")
print("-"*30)

# 0から9まで
arr_range = np.arange(10)
print(f"arange(10): {arr_range}")

# 2から20まで、3刻み
arr_step = np.arange(2, 20, 3)
print(f"arange(2,20,3): {arr_step}")

# 0から1まで5等分
arr_linspace = np.linspace(0, 1, 5)
print(f"linspace(0,1,5): {arr_linspace}")

# 3. 特殊な配列
print("\n【3. 特殊な配列】")
print("-"*30)

zeros = np.zeros(5)
ones = np.ones(5)
full = np.full(5, 7)  # 7で埋めた配列

print(f"zeros(5): {zeros}")
print(f"ones(5): {ones}")
print(f"full(5, 7): {full}")

# 4. 配列の演算（ベクトル化の威力）
print("\n【4. 配列の演算】")
print("-"*30)

arr1 = np.array([1, 2, 3, 4, 5])
arr2 = np.array([10, 20, 30, 40, 50])

print(f"arr1: {arr1}")
print(f"arr2: {arr2}")
print(f"足し算: {arr1 + arr2}")
print(f"掛け算: {arr1 * 2}")
print(f"累乗: {arr1 ** 2}")

# Pythonリストとの速度比較
print("\n【Bonus: なぜNumPyは速い？】")
print("-"*30)
import time

size = 100000
py_list = list(range(size))
np_array = np.arange(size)

# Pythonリストの場合
start = time.time()
py_result = [x * 2 for x in py_list]
py_time = time.time() - start

# NumPy配列の場合
start = time.time()
np_result = np_array * 2
np_time = time.time() - start

print(f"Pythonリスト処理時間: {py_time:.5f}秒")
print(f"NumPy配列処理時間: {np_time:.5f}秒")
print(f"NumPyは約{py_time/np_time:.1f}倍速い！")

print("\n✅ Day 1 完了！明日はPandasを学習します。")
