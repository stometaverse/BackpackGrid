from bpx.bpx import *
from bpx.bpx_pub import *
import random
import string
from loguru import logger
from requests.exceptions import ConnectionError
from urllib3.exceptions import ProtocolError
import time

class SpotGrid:
    def __init__(self):
        self.reset_for_restart()

    def reset_for_restart(self):
        self.symbol = "SOL_USDC"
        self.grid_levels = 20  # Number of grid levels
        self.grid_spread = 0.005  # 0.5% spread between grid levels
        self.quantity = 0.2
        self.price_precision = 2
        self.quantity_precision = 2
        self.strategy_prefix = "1"
        self.grid_orders = {}
        self.bpx = BpxClient()
        self.bpx.init('api_key', 'api_secret')
        self.total_profit = 0

    def get_client_id(self, size=6, chars=string.digits):
        id = ''.join(random.choice(chars) for _ in range(size))
        return int(f"{self.strategy_prefix}{id}")

    def round_to(self, number, precision):
        return float(f'{number:.{precision}f}')

    def get_balance(self):
        b = self.bpx.balances()
        if b:
            s = self.symbol.split("_")
            return float(b.get(s[0], {}).get("available", 0.)), float(b.get(s[1], {}).get("available", 0.))
        return None, None

    def get_current_price(self):
        ticker = self.bpx.ticker(self.symbol)
        return float(ticker['lastPrice']) if ticker else None

    def create_grid(self):
        current_price = self.get_current_price()
        if not current_price:
            logger.error("Failed to get current price")
            return

        self.grid_orders = {}
        upper_price = current_price * (1 + self.grid_spread * self.grid_levels / 2)
        lower_price = current_price / (1 + self.grid_spread * self.grid_levels / 2)

        for i in range(self.grid_levels):
            grid_price = self.round_to(lower_price * (1 + self.grid_spread) ** i, self.price_precision)
            if grid_price < current_price:
                self.place_grid_order("Bid", grid_price)
            elif grid_price > current_price:
                self.place_grid_order("Ask", grid_price)

    def place_grid_order(self, side, price):
        order = self.create_order(self.symbol, side, "Limit", "GTC", self.quantity, price)
        if order:
            self.grid_orders[order['id']] = order
            logger.info(f"Placed {side} order at {price}")

    def create_order(self, symbol, side, order_type, time_in_force, quantity, price):
        try:
            order = self.bpx.exe_order(
                cid=self.get_client_id(),
                symbol=symbol,
                side=side,
                order_type=order_type,
                time_in_force=time_in_force,
                quantity=self.round_to(quantity, self.quantity_precision),
                price=self.round_to(price, self.price_precision)
            )
            return order
        except Exception as e:
            logger.error(f"Error creating order: {e}")
            return None

    def check_and_replace_filled_orders(self):
        for order_id, order in list(self.grid_orders.items()):
            status = self.bpx.get_open_order(self.symbol, order_id)
            if not status:
                filled_price = float(order['price'])
                logger.info(f"Order filled: {order}")
                del self.grid_orders[order_id]

                # Calculate profit/loss
                if order['side'] == "Ask":
                    profit = (filled_price - float(order['price'])) * float(order['quantity'])
                else:
                    profit = (float(order['price']) - filled_price) * float(order['quantity'])
                self.total_profit += profit
                logger.info(f"Profit from this trade: {profit}, Total profit: {self.total_profit}")

                # Place a new opposite order
                new_side = "Ask" if order['side'] == "Bid" else "Bid"
                new_price = self.round_to(filled_price * (1 + self.grid_spread if new_side == "Ask" else 1 - self.grid_spread), self.price_precision)
                self.place_grid_order(new_side, new_price)

    def adjust_grid(self):
        current_price = self.get_current_price()
        if not current_price:
            return

        lower_bound = min(float(order['price']) for order in self.grid_orders.values())
        upper_bound = max(float(order['price']) for order in self.grid_orders.values())

        if current_price < lower_bound * 1.1 or current_price > upper_bound * 0.9:
            logger.info("Price moved significantly. Recreating grid.")
            self.cancel_all_orders()
            self.create_grid()

    def run_grid_strategy(self):
        logger.info("Starting grid strategy")
        self.cancel_all_orders()
        self.create_grid()

        while True:
            try:
                self.check_and_replace_filled_orders()
                self.adjust_grid()
                time.sleep(10)  # Check every 10 seconds
            except (ConnectionError, ProtocolError) as e:
                logger.error(f"Network error: {e}")
                time.sleep(30)  # Wait before retrying
            except Exception as ex:
                logger.error(f"Unexpected error: {ex}")
                time.sleep(60)  # Wait a minute before continuing

    def cancel_all_orders(self):
        open_orders = self.bpx.get_all_open_orders(symbol=self.symbol)
        for order in open_orders:
            try:
                self.bpx.cancel_order(self.symbol, order.get("id"))
                logger.info(f"Cancelled order: {order.get('id')}")
            except Exception as e:
                logger.error(f"Error cancelling order: {e}")

if __name__ == '__main__':
    grid = SpotGrid()
    grid.run_grid_strategy()