import base64
import json
import time
import requests
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from loguru import logger
from urllib.parse import urlencode

class BpxClient:
    url = 'https://api.backpack.exchange/'
    private_key: ed25519.Ed25519PrivateKey

    def __init__(self):
        self.debug = False
        self.proxies = {
            'http': '',
            'https': ''
        }
        self.api_key = ''
        self.api_secret = ''
        self.window = 5000

    def init(self, api_key, api_secret):
        self.api_key = api_key
        self.api_secret = api_secret
        self.private_key = ed25519.Ed25519PrivateKey.from_private_bytes(
            base64.b64decode(api_secret)
        )
        self.verifying_key = self.private_key.public_key()
        self.verifying_key_b64 = base64.b64encode(
            self.verifying_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw
            )
        ).decode()

    # capital
    def balances(self):
        while True:
            res = requests.get(url=f'{self.url}api/v1/capital', proxies=self.proxies,
                                headers=self.sign('balanceQuery', {}))
            if str(res.status_code) == "200":
                return res.json()
            else:
                logger.error(f"查询余额失败，重试...{res.text}")
                time.sleep(5)
                continue
        
    def deposits(self):
        return requests.get(url=f'{self.url}wapi/v1/capital/deposits', proxies=self.proxies,
                            headers=self.sign('depositQueryAll', {})).json()

    def deposit_address(self, chain: str):
        params = {'blockchain': chain}
        return requests.get(url=f'{self.url}wapi/v1/capital/deposit/address', proxies=self.proxies, params=params,
                            headers=self.sign('depositAddressQuery', params)).json()

    def withdrawals(self, limit: int, offset: int):
        params = {'limit': limit, 'offset': offset}
        return requests.get(url=f'{self.url}wapi/v1/capital/withdrawals', proxies=self.proxies, params=params,
                            headers=self.sign('withdrawalQueryAll', params)).json()

    # history

    def order_history_query(self, symbol: str, limit: int, offset: int):
        params = {'symbol': symbol, 'limit': limit, 'offset': offset}
        return requests.get(url=f'{self.url}wapi/v1/history/orders', proxies=self.proxies, params=params,
                            headers=self.sign('orderHistoryQueryAll', params)).json()

    def fill_history_query(self, symbol: str, limit: int, offset: int):
        params = {'limit': limit, 'offset': offset}
        if len(symbol) > 0:
            params['symbol'] = symbol
        return requests.get(url=f'{self.url}wapi/v1/history/fills', proxies=self.proxies, params=params,
                            headers=self.sign('fillHistoryQueryAll', params)).json()
    
    # order

    def exe_order(self, cid, symbol, side, order_type, time_in_force, quantity, price):
        params = {
            'clientId': cid,
            'symbol': symbol,
            'side': side,
            'orderType': order_type,
            'timeInForce': time_in_force,
            'quantity': quantity,
            'price': price
        }
        retry_limit = 5  # 最大重试次数
        retry_count = 0  # 当前重试计数
        while True:
            try:
                res = requests.post(url=f'{self.url}api/v1/order', proxies=self.proxies, data=json.dumps(params),
                                    headers=self.sign('orderExecute', params))
                if str(res.status_code) == "200":
                    return res.json()
                elif str(res.status_code) == "202":  # 订单提交了，但是未执行
                    o = res.json()
                    return {
                        'clientId': cid,
                        'createdAt': None,
                        'executedQuantity': '0',
                        'executedQuoteQuantity': '0',
                        'id': o.get("id"),
                        'orderType': order_type,
                        'postOnly': False,
                        'price': str(price),
                        'quantity': str(quantity),
                        'selfTradePrevention': 'RejectTaker',
                        'side': side,
                        'status': 'New',
                        'symbol': symbol,
                        'timeInForce': time_in_force,
                        'triggerPrice': None
                    }
                else:
                    error_message = res.text  # 假设错误信息在响应文本中
                    # 检查是否达到重试次数限制
                    if retry_count >= retry_limit:
                        logger.error(f"达到最大重试次数 {retry_limit}，将退出循环。")
                        break  # 跳出循环
                    # 判断是否为特定错误信息
                    if "Invalid signature" in error_message or "Request has expired" in error_message:
                        retry_count += 1  # 增加重试计数
                        logger.error(f"特定错误，重试次数 {retry_count}/{retry_limit}: {error_message}")
                        time.sleep(5)
                        continue  # 重试
                    else:
                        retry_count += 1  # 增加重试计数
                        logger.error(f"订单提交失败，重试次数 {retry_count}/{retry_limit}: {error_message}")
                        time.sleep(5)
                        continue  # 重试
            except Exception as e:
                print(e)
                continue

    # 获取挂单信息
    def get_open_order(self, symbol, order_id):
        params = {
            'symbol': symbol,
            'orderId': order_id,
        }
        max_retries = 5  # 最大重试次数
        attempt_count = 0  # 当前尝试次数
        retry_delay = 1  # 初始重试延迟（秒）

        while attempt_count < max_retries:
            try:
                res = requests.get(url=f'{self.url}api/v1/order', proxies=self.proxies, params=params,
                                   headers=self.sign('orderQuery', params))
                if res.status_code == 200:
                    return res.json()  # 成功获取订单
                elif res.status_code == 404:  # 订单不存在
                    return None
                else:
                    logger.error(f"订单查询失败, 状态码 {res.status_code}: {res.text}，重试 #{attempt_count + 1}")
                    attempt_count += 1  # 增加尝试次数
                    time.sleep(retry_delay)
                    retry_delay *= 2  # 指数退避
            except Exception as ex:
                logger.error(f"查询订单时出现异常: {ex}")
                attempt_count += 1
                time.sleep(retry_delay)
                retry_delay *= 2

            if attempt_count >= max_retries:
                logger.error("达到最大重试次数，停止查询")
                break  # 达到最大重试次数或遇到特定错误时跳出循环

        if attempt_count == max_retries:
            logger.error("订单查询失败，已达最大重试次数")
            return {'error': '查询失败，已达最大重试次数'}  # 或其他指示失败的消息

    # 取消未完成订单
    def cancel_order(self, symbol, order_id):
        params = {
            'symbol': symbol,
            'orderId': order_id,
        }
        max_retries = 5  # 最大重试次数
        attempt_count = 0  # 当前尝试次数

        while attempt_count < max_retries:
            try:
                res = requests.delete(url=f'{self.url}api/v1/order', proxies=self.proxies, data=json.dumps(params),
                                      headers=self.sign('orderCancel', params))
                if res.status_code == 200:
                    return res.json()  # 成功取消
                elif res.status_code == 202:  # 订单取消了，但是未执行
                    return {'id': order_id, 'status': 'pending'}
                else:
                    error_message = res.text
                    if "Order not found" in error_message:
                        logger.error("订单取消失败: 订单未找到，无需重试")
                        return {'id': order_id, 'status': 'not_found'}
                    logger.error(f"订单取消失败: {error_message}，重试")
                    attempt_count += 1  # 增加尝试次数
                    time.sleep(5)
            except Exception as ex:
                logger.error(f"尝试取消订单时出现异常: {ex}")
                attempt_count += 1  # 异常情况下也增加尝试次数
                time.sleep(5)

        logger.error(f"达到最大重试次数，取消订单失败: {order_id}")
        return {'id': order_id, 'status': 'failed'}  # 在这里可以选择返回一个指示失败的消息或None

    # 获取所有未完成订单
    def get_all_open_orders(self, symbol=None):
        params = {}
        if symbol:
            params = {'symbol': symbol}

        return requests.get(url=f'{self.url}api/v1/orders', proxies=self.proxies, params=params,
                             headers=self.sign('orderQueryAll', params)).json()
    
    # 取消所有未完成订单
    def cancel_all_open_orders(self, symbol):
        params = {'symbol': symbol}
        return requests.delete(url=f'{self.url}api/v1/orders', proxies=self.proxies, data=json.dumps(params),
                             headers=self.sign('orderCancelAll', params)).json()
    
    # 获取历史订单
    def get_history_orders(self, symbol):
        params = {'symbol': symbol}
        return requests.get(url=f'{self.url}wapi/v1/history/orders', proxies=self.proxies, params=params,
                             headers=self.sign('orderHistoryQueryAll', params)).json()
    
    # 获取历史成交订单
    def get_history_filled_orders(self, symbol=None):
        params = {'symbol': symbol}
        return requests.get(url=f'{self.url}wapi/v1/history/fills', proxies=self.proxies, params=params,
                             headers=self.sign('fillHistoryQueryAll', params)).json()
    
    def sign(self, instruction: str, params: dict = None):
        timestamp = str(int(time.time() * 1000))
        window = '5000'

        body = {
            'instruction': instruction,
            **dict(sorted((params or {}).items())),
            'timestamp': timestamp,
            'window': window,
        }
        message = urlencode(body)
        signature = self.private_key.sign(message.encode())
        signature_b64 = base64.b64encode(signature).decode()

        return {
            'X-API-KEY': self.verifying_key_b64,
            'X-TIMESTAMP': timestamp,
            'X-WINDOW': window,
            'Content-Type': 'application/json',
            'X-SIGNATURE': signature_b64
        }
