import requests
import time
from loguru import logger
import datetime

BP_BASE_URL = ' https://api.backpack.exchange/'

# Markets
def assets():
    return requests.get(url=f'{BP_BASE_URL}api/v1/assets').json()


def markets():
    return requests.get(url=f'{BP_BASE_URL}api/v1/markets').json()


def ticker(symbol: str):
    return requests.get(url=f'{BP_BASE_URL}api/v1/ticker?symbol={symbol}').json()


def depth(symbol: str):
    while True:
        res = requests.get(url=f'{BP_BASE_URL}api/v1/depth?symbol={symbol}')
        if str(res.status_code) == "200":
            return res.json()
        else:
            logger.error(f"获取深度数据失败: {res.text}, 重试")
            time.sleep(2)


def klines(symbol: str, interval: str, start_time: int = 0, end_time: int = 0):
    url = f'{BP_BASE_URL}api/v1/klines'

    params = {'symbol': symbol, 'interval': interval}

    if start_time > 0:
        params['startTime'] = start_time
    if end_time > 0:
        params['endTime'] = end_time

    response = requests.get(url, params=params)
    if response.status_code != 200:
        print(f'Error: {response.status_code}')
        print(f'Response: {response.text}')
        return None
    return response.json()


# System
def status():
    return requests.get(url=f'{BP_BASE_URL}api/v1/status').json()


def ping():
    return requests.get(url=f'{BP_BASE_URL}api/v1/ping').text


def time():
    return requests.get(url=f'{BP_BASE_URL}api/v1/time').text


# Trades
def recent_trades(symbol: str, limit: int = 100):
    return requests.get(url=f'{BP_BASE_URL}api/v1/trades?symbol={symbol}&limit={limit}').json()


def history_trades(symbol: str, limit: int = 100, offset: int = 0):
    return requests.get(url=f'{BP_BASE_URL}api/v1/trades/history?symbol={symbol}&limit={limit}&offset={offset}').json()


if __name__ == '__main__':
    # print(Assets())
    logger.info(markets())
    # print(Ticker('SOL_USDC'))
    # print(Depth('SOL_USDC'))
    start_time = int((datetime.datetime.now() - datetime.timedelta(minutes=10)).timestamp())

    kline = (klines('SOL_USDC', '1m', start_time))
    print("result is:")
    print(kline)
    # print(Status())
    # print(Ping())
    # print(Time())
    # print(recentTrades('SOL_USDC', 10))
    # print(historyTrades('SOL_USDC', 10))
    pass
