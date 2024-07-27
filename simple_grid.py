from bpx.bpx import *
from bpx.bpx_pub import *
import random
import string
from loguru import logger
from requests.exceptions import ConnectionError
from urllib3.exceptions import ProtocolError

class SpotGrid:
    def __init__(self):
        self.reset_for_restart()

    def reset_for_restart(self):
        self.symbol = "SOL_USDC"
        self.max_price = 240  # 网格上界
        self.min_price = 140  # 网格下届
        self.gap_percent = 0.001  # 等比网格，比率
        self.price_precision = 2  # 价格精度，价格最多有几位小数
        self.quantity = 0.2  # 交易数量，每次下单数量
        self.quantity_precision = 2  # 下单量精度，下单量最多几位小数

        self.depth = None  # 深度数据
        self.strategy_prefix = "1"  # 策略唯一编号，取值保守的话可以1~40，保证每个策略这个不同就行，这样可以运行多个网格

        self.buy_order = None
        self.sell_order = None
        self.bpx = BpxClient()
        self.bpx.init('api_key', 'api_secret')

    # 生成client_id
    def get_client_id(self, size=6, chars=string.digits):
        id = ''.join(random.choice(chars) for _ in range(size))
        return int(f"{self.strategy_prefix}{id}")

    def get_open_orders(self):
        open_orders = self.bpx.get_all_open_orders(symbol=self.symbol)
        relevant_orders = []  # 存储与策略前缀匹配的订单
        for o in open_orders:
            # Assuming orders without a clientId are still relevant
            if o.get("clientId") is None or str(o.get("clientId", "")).startswith(self.strategy_prefix):
                relevant_orders.append(o)  # 添加到列表中
                if o.get("side") == "Bid":
                    self.buy_order = o
                    logger.info(f"已存在买单 {self.buy_order}")
                elif o.get("side") == "Ask":
                    self.sell_order = o
                    logger.info(f"已存在卖单 {self.sell_order}")
        return relevant_orders  # 返回与策略前缀匹配的所有订单

    def get_bid_ask_price(self):
        self.depth = depth(self.symbol)
        if self.depth:
            return float(self.depth['bids'][-1][0]), float(self.depth['asks'][0][0])
        else:
            return None, None

    def round_to(self, number, precision):
        return float(f'{number:.{precision}f}')

    def getOrderInfo(self, orderId):
        orders = self.bpx.get_history_orders(self.symbol)  # 获取历史订单
        for o in orders:
            if o.get("id") == orderId:
                return o
        return None

    def get_balance(self):
        b = self.bpx.balances()
        if b:
            s = self.symbol.split("_")
            b1 = float(b.get(s[0], {}).get("available", 0.))
            b2 = float(b.get(s[1], {}).get("available", 0.))
            return b1, b2
        else:
            return None, None

    # 创建订单
    def create_order(self, symbol, side, orderType, timeInForce, quantity, price):
        # 获取当前余额
        b1, b2 = self.get_balance()  # 假设b1为持仓量，b2为资金量

        if price < self.min_price or price > self.max_price:
            logger.info(f"当前价格{price}不在网格下单范围内({self.min_price} ~ {self.max_price})，不下单")
            return None
        bid_price, ask_price = self.get_bid_ask_price()
        # 检查是否为卖单且余额不足
        if side == "Ask" and b1 < quantity:
            logger.error("卖单余额不足，尝试反向买入一半资产...")
            # 改为买入操作
            side = "Bid"
            price = self.round_to(ask_price * (1 + float(self.gap_percent)), self.price_precision)
            quantity = b2 / (2 * price)
            quantity = self.round_to(float(quantity), self.quantity_precision)

        # 检查是否为买单且资金不足
        elif side == "Bid" and b2 < quantity * price:
            logger.error("买单余额不足，尝试反向卖出一半资产...")
            # 改为卖出操作
            side = "Ask"
            price = self.round_to(bid_price * (1 - float(self.gap_percent)), self.price_precision)
            quantity = b1 / 2
            quantity = self.round_to(float(quantity), self.quantity_precision)

        # 执行订单
        order_result = self.bpx.exe_order(cid=self.get_client_id(), symbol=symbol, side=side, order_type=orderType,
                                          time_in_force=timeInForce, quantity=quantity, price=price)
        # if order_result:
        #     logger.info(f"成功创建订单: {order_result}")
        # else:
        #     logger.error("创建订单失败")
        return order_result

    def check_and_create_orders(self, bid_price, ask_price, quantity):
        if not self.buy_order and bid_price > 0:
            buy_price = self.round_to(bid_price + 0.02, self.price_precision)
            self.buy_order = self.create_order(symbol=self.symbol, side="Bid", orderType="Limit",
                                               timeInForce="GTC", quantity=quantity, price=buy_price)
            if self.buy_order:
                logger.info(f"创建新买单: {self.buy_order}")

        if not self.sell_order and ask_price > 0:
            sell_price = self.round_to(ask_price - 0.02, self.price_precision)
            self.sell_order = self.create_order(symbol=self.symbol, side="Ask", orderType="Limit",
                                                timeInForce="GTC", quantity=quantity, price=sell_price)
            if self.sell_order:
                logger.info(f"创建新卖单: {self.sell_order}")

    def check_and_buy_order(self, bid_price, ask_price, quantity):
        if not self.buy_order and bid_price > 0:
            buy_price = self.round_to(bid_price + 0.02, self.price_precision)
            self.buy_order = self.create_order(symbol=self.symbol, side="Bid", orderType="Limit",
                                               timeInForce="GTC", quantity=quantity, price=buy_price)
            if self.buy_order:
                logger.info(f"创建新买单: {self.buy_order}")

    def check_and_sell_order(self, bid_price, ask_price, quantity):
        if not self.sell_order and ask_price > 0:
            sell_price = self.round_to(ask_price - 0.02, self.price_precision)
            self.sell_order = self.create_order(symbol=self.symbol, side="Ask", orderType="Limit",
                                                timeInForce="GTC", quantity=quantity, price=sell_price)
            if self.sell_order:
                logger.info(f"创建新卖单: {self.sell_order}")

    def check_order_status(self):
        # 检查买单状态
        if self.buy_order:
            check_order = self.bpx.get_open_order(self.symbol, self.buy_order.get("id"))
            if not check_order:  # 订单可能已成交或被取消
                check_order = self.getOrderInfo(self.buy_order.get("id"))
            if check_order and check_order.get('status') == "Filled":
                logger.info(f"买单成交: {check_order}")
                self.buy_order = None
                # 可在此处根据成交信息创建新的卖单

        # 检查卖单状态
        if self.sell_order:
            check_order = self.bpx.get_open_order(self.symbol, self.sell_order.get("id"))
            if not check_order:  # 订单可能已成交或被取消
                check_order = self.getOrderInfo(self.sell_order.get("id"))
            if check_order and check_order.get('status') == "Filled":
                logger.info(f"卖单成交: {check_order}")
                self.sell_order = None
                # 可在此处根据成交信息创建新的买单

    def cancel_all_orders(self):
        open_orders = self.get_open_orders()  # 假设这个方法返回所有开放的订单列表
        for order in open_orders:
            try:
                cancel_result = self.bpx.cancel_order(self.symbol, order.get("id"))
                if cancel_result:
                    logger.info(f"已撤销订单: {order.get('id')}")
                else:
                    logger.warning(f"撤销订单失败: {order.get('id')}")
            except Exception as e:
                logger.error(f"撤销订单时发生异常: {e}")


    # def get_open_orders(self):
    #     orders = self.bpx.getAllOpenOrders(symbol=self.symbol)
    #     for o in orders:
    #         if str(o.get("clientId", "")).startswith(self.strategy_prefix) and o.get("side") == "Bid":
    #             self.buy_order = o
    #             logger.info(f"已存在买单 {self.buy_order}")
    #         elif str(o.get("clientId", "")).startswith(self.strategy_prefix) and o.get("side") == "Ask":
    #             self.sell_order = o
    #             logger.info(f"已存在卖单 {self.sell_order}")

    def start_grid(self):
        start_time = time.time()  # 记录启动时间
        max_runtime = 15  # 最大运行时间，600秒等于10分钟
        retry_delay = 10  # 遇到连接异常时的重试延迟（秒）
        # self.get_open_orders()  # 如果程序挂了，重启恢复
        quantity = self.round_to(float(self.quantity), self.quantity_precision)
        logger.info(f"订单下单量调整为{quantity}")
        self.cancel_all_orders()  # 检查并撤销所有现有的买卖订单

        while True:
            current_time = time.time()
            if current_time - start_time >= max_runtime:
                logger.info(f"达到最大运行时间，重置程序以重新运行。")
                break  # 退出循环，而不是调用self.start_grid()
            try:
                s = status()  # 获取系统状态
                if s and s.get('status') != "Ok":
                    logger.info("系统维护中...")
                    time.sleep(10)
                    continue
                bid_price, ask_price = self.get_bid_ask_price()

                # 检查买单和卖单，尝试创建订单
                self.check_and_create_orders(bid_price, ask_price, quantity)
                time.sleep(2)  # 循环检测间隔
                # 检查订单状态，处理成交或取消的订单
                # self.check_order_status()


                time.sleep(5)  # 循环检测间隔
            except (ConnectionError, ProtocolError) as e:
                logger.error(f"网络连接异常: {e}")
                logger.info(f"将在{retry_delay}秒后重试...")
                time.sleep(retry_delay)  # 在重试之前等待
                self.start_grid()  # 递归调用以重新启动网格
            except Exception as ex:
                logger.error(f"发生异常: {ex}")
                break  # 遇到非网络相关异常时退出循环


if __name__ == '__main__':
    while True:
        grid = SpotGrid()  # 创建新实例
        grid.start_grid()  # 执行主逻辑
        grid.reset_for_restart()  # 重置状态，如果需要  # 在每次循环结束时重置状态，为下一轮运行做准备

