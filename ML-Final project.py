#!/usr/bin/env python
# coding: utf-8

# In[2]:


get_ipython().system('pip install -r requirements.txt')


# In[3]:


import websocket, json, pprint, ta, numpy
import config
from feature_transform import generate_feature
from binance.client import Client
from binance.enums import *
import pandas as pd 
from collections import deque
import numpy as np


# # Client

# ## Init Client

# In[4]:


print(config.API_KEY, config.API_SECRET)


# In[6]:


client = Client(config.API_KEY, config.API_SECRET, tld='vn', testnet=True)


# ## Get account information

# In[10]:


import requests

# Fetch the server time from Binance
response = requests.get('https://api.binance.com/api/v3/time')
server_time = response.json()['serverTime']

# Adjust the timestamp by subtracting 1000 milliseconds
adjusted_timestamp = server_time - 1000

# Make the get_account() request with the adjusted timestamp
client.get_account(timestamp=adjusted_timestamp)


# ### Explain
# 1. ``makerCommission`` và ``takerCommission``: Đây là mức phí giao dịch áp dụng trên sàn giao dịch Binance. ``makerCommission`` áp dụng cho người tạo lệnh (makers), tức là khi bạn đặt lệnh không khớp với giá thị trường. ``takerCommission`` áp dụng cho người khớp lệnh (takers), tức là khi bạn đặt lệnh và nó khớp với lệnh hiện có trên thị trường.
# 
# 2. ``buyerCommission`` và ``sellerCommission``: Đây là mức phí giao dịch áp dụng cho người mua và người bán trên sàn giao dịch Binance. buyerCommission là phí áp dụng khi bạn mua một tài sản từ một người bán, và ``sellerCommission`` là phí áp dụng khi bạn bán một tài sản cho một người mua.
# 
# 3. ``commissionRates`` (Tỷ lệ phí giao dịch): Đây là các tỷ lệ phí giao dịch áp dụng cho từng loại người tham gia thị trường trên sàn Binance. Cụ thể:
# - ``maker``: Tỷ lệ phí áp dụng cho người tạo lệnh (makers).
# - ``taker``: Tỷ lệ phí áp dụng cho người khớp lệnh (takers).
# - ``buyer``: Tỷ lệ phí áp dụng cho người mua.
# - ``seller``: Tỷ lệ phí áp dụng cho người bán.

# In[11]:


# get detail asset
print(client.get_asset_balance(asset='BTC'))
print(client.get_asset_balance(asset = 'USDT'))
print(client.get_asset_balance(asset = 'ETH'))


# In[12]:


# get balances for futures account
# print(client.futures_account_balance())

# get balances for margin account
# print(client.get_margin_account())


# In[13]:


# get latest price from Binance API
btc_price = client.get_symbol_ticker(symbol="BTCUSDT")
# print full output (dictionary)
print(btc_price)


# ### Explain
# 
# 
# 1. ``symbol`` (str) - (bắt buộc): Mã chứng khoán hoặc cặp giao dịch mà bạn muốn đặt lệnh.
# 2. ``side`` (str) - (bắt buộc): Hướng lệnh, có thể là 'BUY' (mua) hoặc 'SELL' (bán).
# 3. ``type`` (str) - (bắt buộc): Loại lệnh, có thể là 'LIMIT' (lệnh giới hạn) hoặc 'MARKET' (lệnh thị trường).
# 4. ``timeInForce`` (str) - (bắt buộc nếu lệnh giới hạn). Thời gian hiệu lực của lệnh giới hạn
#     - ``GTC`` (Good 'Til Cancelled): Lệnh giới hạn sẽ được duy trì và hiệu lực cho đến khi bạn hủy nó hoặc lệnh được thực hiện.
#     - ``IOC`` (Immediate or Cancel): Lệnh giới hạn sẽ được thực hiện ngay lập tức với phần không được khớp tức thì sẽ được hủy.
#     - ``FOK`` (Fill or Kill): Lệnh giới hạn yêu cầu hoàn toàn khớp được hoặc lệnh sẽ bị hủy.
#     - ``GTX`` (Good 'Til Crossing): Lệnh giới hạn sẽ được duy trì và hiệu lực cho đến khi thị trường chạm vào giá mục tiêu (đặt trước), sau đó lệnh sẽ được thực hiện ngay lập tức hoặc bị hủy.
# 5. ``quantity`` (decimal) - (bắt buộc): Số lượng cần mua hoặc bán.
# 6. ``quoteOrderQty`` (decimal) - (áp dụng cho lệnh thị trường): Số lượng tiền mà người dùng muốn chi (khi mua) hoặc nhận (khi bán) của tài sản tham chiếu. VD mua 100 USDT BTC
# 7. ``price`` (str) - (bắt buộc): Giá mua hoặc bán của lệnh giới hạn.
# 8. ``icebergQty`` (decimal) - Sử dụng với các loại lệnh giới hạn như 'LIMIT', 'STOP_LOSS_LIMIT' và 'TAKE_PROFIT_LIMIT' để tạo lệnh iceberg (lệnh băng).
# 
# 
# **More information:**
# - Docs: https://binance-docs.github.io/apidocs/spot/en/#spot-account-trade
# - Constant variable: https://python-binance.readthedocs.io/en/latest/constants.html#
# 

# ## Order

# In[14]:


# market buy example
client.create_order(symbol='BTCUSDT', side=SIDE_BUY, type=ORDER_TYPE_MARKET, quantity=0.001)
print(client.get_asset_balance(asset='BTC'))


# In[15]:


# market sell example
client.create_order(symbol='BTCUSDT', side=SIDE_SELL, type=ORDER_TYPE_MARKET, quantity=0.001)
print(client.get_asset_balance(asset='BTC'))


# In[16]:


#show open order
client.get_open_orders()


# In[17]:


#cancer order
for order in client.get_open_orders():
    client.cancel_order(symbol='BTCUSDT', orderId=order['orderId'])
client.get_open_orders()


# # Simple bot

# In[18]:


SOCKET = "wss://stream.binance.com:9443/ws/ethusdt@kline_1s"

RSI_PERIOD = 14
RSI_OVERBOUGHT = 30
RSI_OVERSOLD = 70
TRADE_SYMBOL = 'ETHUSDT'
TRADE_QUANTITY = 0.05

balances_history = []
closes = []
in_position = False

client = Client(config.API_KEY, config.API_SECRET, tld='vn', testnet=True)


# In[19]:


def order(side, quantity, symbol,order_type=ORDER_TYPE_MARKET):
    try:
        print("sending order")
        order = client.create_order(symbol=symbol, side=side, type=order_type, quantity=quantity)
        print(order)
    except Exception as e:
        print("an exception occured - {}".format(e))
        return False

    return True
    
def on_open(ws):
    print('opened connection')

def on_close(ws):
    print('closed connection')

def current_balance_usdt_btc_eth():
    balances_df = pd.DataFrame(client.get_account()['balances'])
    symbols_price_df =  pd.DataFrame(client.get_symbol_ticker(symbols= '''["BTCUSDT","ETHUSDT"]'''))
    current_bal = float(balances_df[balances_df['asset'] == 'USDT']['free']) + \
                    float(balances_df[balances_df['asset'] == 'BTC']['free']) * float(symbols_price_df[symbols_price_df['symbol'] == 'BTCUSDT']['price']) + \
                    float(balances_df[balances_df['asset'] == 'ETH']['free']) * float(symbols_price_df[symbols_price_df['symbol'] == 'ETHUSDT']['price'])
                    
    return current_bal


# In[20]:


#reset client

for balance in client.get_account()['balances']:
    if balance['asset'] not in ['BTC', 'ETH'] or float(balance['free']) <= 0.00000001 :
        continue
    order_succeeded = False
    while not order_succeeded:
        order_succeeded = order(SIDE_SELL, balance['free'], '{0}USDT'.format(balance['asset']))
    print(balance['asset'])
    


# In[21]:


client.get_account()['balances']


# In[22]:


from datetime import datetime, timedelta
now = datetime.now()
pre_3_hour = (now - timedelta(hours=9)).strftime('%F %T.%f')[:-3]
pre_3_hour


# In[23]:


#init data
btc_deque = deque(maxlen=150)
bars = client.get_historical_klines('BTCUSDT', '1m', start_str=pre_3_hour)
for line in bars:
	del line[6:]
btc_list = pd.DataFrame(bars, columns=['Date', 'Open', 'High', 'Low', 'Close', 'Volume']).to_dict('records')
btc_deque.extend(btc_list)


# In[24]:


btc_deque[-1]


# In[25]:


balances_history = []


# In[ ]:


def on_message(ws, message):
    global btc_df, in_position, balances_history
    
    print('received message')
    json_message = json.loads(message)
    # pprint.pprint(json_message)

    candle = json_message['k']

    is_candle_closed = candle['x']

    if is_candle_closed:
        # print(candle)
        new_frame = {
            'Date': candle['t'],
            'Open': candle['o'],
            'High': candle['h'],
            'Low': candle['l'],
            'Close': candle['c'],
            'Volume': candle['v']
        }
        btc_deque.append(new_frame)
        btc_df = pd.DataFrame(btc_deque)
        current_data_feature = generate_feature(btc_df).iloc[-1]
        ##YOUR CODE 
        # indicator = model.predict(current_data_feature.to_numpy())
        
        
        
# Historical data
csv_file_path = "C:\\Users\\Admin\\Desktop\\coinview\\coinview\\btc_price_per_mi.csv"
df = pd.read_csv(csv_file_path)
df = generate_feature(df)
df.dropna(inplace=True)

# Split data into train and test sets
train_size = int(0.8 * len(df))
train_data = df[:train_size]
test_data = df[train_size:]

# Train the model
from sklearn.linear_model import LinearRegression
model = LinearRegression()
model.fit(train_data[feature_cols], train_data[target_col])

# Evaluate the model
train_score = model.score(train_data[feature_cols], train_data[target_col])
test_score = model.score(test_data[feature_cols], test_data[target_col])
print(f"Train Score: {train_score}")
print(f"Test Score: {test_score}")

# Trading and backtesting
balances_history = []
in_position = False
btc_deque = deque(maxlen=150)

def order(side, quantity, symbol, order_type=ORDER_TYPE_MARKET):
    try:
        print("Sending order")
        order = client.create_order(symbol=symbol, side=side, type=order_type, quantity=quantity)
        print(order)
    except Exception as e:
        print("An exception occurred - {}".format(e))
        return False
    return True

def on_message(ws, message):
    global btc_deque, in_position, balances_history
    json_message = json.loads(message)
    candle = json_message['k']
    is_candle_closed = candle['x']
    
    if is_candle_closed:
        new_frame = {
            'Date': candle['t'],
            'Open': candle['o'],
            'High': candle['h'],
            'Low': candle['l'],
            'Close': candle['c'],
            'Volume': candle['v']
        }
        btc_deque.append(new_frame)
        btc_df = pd.DataFrame(btc_deque)
        current_data_feature = generate_feature(btc_df).iloc[-1]

        # Predict the price using the trained model
        predicted_price = model.predict([current_data_feature[feature_cols]])[0]

        # Trading strategy based on RSI and EMA
        last_rsi = current_data_feature['rsi_window_14']
        ema_34 = current_data_feature['ema_window_34']
        ema_89 = current_data_feature['ema_window_89']
        print('Last RSI:', last_rsi)
        
        if last_rsi < RSI_OVERSOLD and ema_34 > ema_89:
            if in_position:
                print("It is oversold and EMA34 > EMA89, but you already own it. Nothing to do.")
            else:
                print("Oversold and EMA34 > EMA89! Buy! Buy! Buy!")
                order_succeeded = order(SIDE_BUY, TRADE_QUANTITY, TRADE_SYMBOL)
                if order_succeeded:
                    in_position = True

        if last_rsi > RSI_OVERBOUGHT:
            if in_position:
                print("Overbought! Sell! Sell! Sell!")
                order_succeeded = order(SIDE_SELL, TRADE_QUANTITY, TRADE_SYMBOL)
                if order_succeeded:
                    in_position = False
            else:
                print("It is overbought, but we don't own any. Nothing to do.")

        # Track balance over time
        balances_history.append({
            'Date': candle['t'],
            'balance': current_balance_usdt_btc_eth()
        })

def current_balance_usdt_btc_eth():
    balances_df = pd.DataFrame(client.get_account()['balances'])
    symbols_price_df = pd.DataFrame(client.get_symbol_ticker(symbols='''["BTCUSDT","ETHUSDT"]'''))
    current_bal = float(balances_df[balances_df['asset'] == 'USDT']['free']) + \
                  float(balances_df[balances_df['asset'] == 'BTC']['free']) * \
                  float(symbols_price_df[symbols_price_df['symbol'] == 'BTCUSDT']['price']) + \
                  float(balances_df[balances_df['asset'] == 'ETH']['free']) * \
                  float(symbols_price_df[symbols_price_df['symbol'] == 'ETHUSDT']['price'])
    return current_bal

# WebSocket connection for real-time data
SOCKET = "wss://stream.binance.com:9443/ws/ethusdt@kline_1s"
ws = websocket.WebSocketApp(SOCKET, on_message=on_message)
ws.run_forever()

# Plot balance over time
dates = [pd.Timestamp.fromtimestamp(item['Date'] / 1000) for item in balances_history]
balances = [item['balance'] for item in balances_history]
plt.plot(dates, balances)
plt.xlabel('Date')
plt.ylabel('Balance')
plt.title('Balance over Time')
plt.show()

# Backtesting
initial_balance = 10000  # Initial balance in USDT
balance = initial_balance
backtest_balances = []

for index, row in test_data.iterrows():
    current_price = row['close']
    predicted_price = model.predict([row[feature_cols]])[0]
    
    if row['rsi_window_14'] < RSI_OVERSOLD and row['ema_window_34'] > row['ema_window_89']:
        if balance > 0:
            # Buy order
            buy_quantity = balance / current_price
            balance = 0
            balance -= buy_quantity * current_price
            in_position = True
    elif row['rsi_window_14'] > RSI_OVERBOUGHT:
        if in_position:
            # Sell order
            balance += buy_quantity * current_price
            in_position = False
    
    backtest_balances.append(balance)

# Plotting backtest results
dates = test_data['Date'].apply(lambda x: pd.Timestamp.fromtimestamp(x / 1000))
plt.plot(dates, backtest_balances)
plt.xlabel('Date')
plt.ylabel('Balance (USDT)')
plt.title('Backtest Results')
plt.show()

# Forward testing
balances_history = []
in_position = False

def on_message(ws, message):
    global in_position, balances_history
    
    json_message = json.loads(message)
    candle = json_message['k']
    is_candle_closed = candle['x']
    
    if is_candle_closed:
        new_frame = {
            'date': candle['t'],
            'open': candle['o'],
            'high': candle['h'],
            'low': candle['l'],
            'close': candle['c'],
            'volume': candle['v']
        }
        btc_deque.append(new_frame)
        btc_df = pd.DataFrame(btc_deque)
        current_data_feature = generate_feature(btc_df).iloc[-1]

        if current_data_feature['rsi_window_14'] < RSI_OVERSOLD and current_data_feature['ema_window_34'] > current_data_feature['ema_window_89']:
            if not in_position:
                # Buy order
                order_succeeded = order(SIDE_BUY, TRADE_QUANTITY, TRADE_SYMBOL)
                if order_succeeded:
                    in_position = True
        elif current_data_feature['rsi_window_14'] > RSI_OVERBOUGHT:
            if in_position:
                # Sell order
                order_succeeded = order(SIDE_SELL, TRADE_QUANTITY, TRADE_SYMBOL)
                if order_succeeded:
                    in_position = False
        
        balances_history.append({
            'date': candle['t'],
            'balance': current_balance_usdt_btc_eth()
        })

# Establish WebSocket connection for live trading
ws = websocket.WebSocketApp(SOCKET, on_open=on_open, on_close=on_close, on_message=on_message)
ws.run_forever()
        
      
            


# In[ ]:


import websocket
balances_history = []
closes = []
in_position = False


#reset client

for balance in client.get_account()['balances']:
    if balance['asset'] not in ['BTC', 'ETH'] or float(balance['free']) <= 0.00000001 :
        continue
    order_succeeded = False
    while not order_succeeded:
        order_succeeded = order(SIDE_SELL, balance['free'], '{0}USDT'.format(balance['asset']))
    print(balance['asset'])
    

ws = websocket.WebSocketApp(SOCKET, on_open=on_open, on_close=on_close, on_message=on_message)
ws.run_forever()


# In[34]:


balances_history


# In[35]:


import matplotlib.pyplot as plt
dates = [datetime.fromtimestamp(item['Date'] / 1000) for item in balances_history]
balances = [item['balance'] for item in balances_history]
plt.plot(dates, balances)
plt.xlabel('Date')
plt.ylabel('Balance')
plt.title('Balance over Time')
plt.show()


# In[ ]:





# In[ ]:





# In[ ]:




