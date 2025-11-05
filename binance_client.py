"""
Binance Futures API Client with institutional-grade error handling
"""
import hmac
import hashlib
import time
import requests
from typing import Dict, List, Optional, Any
from urllib.parse import urlencode
import logging
from datetime import datetime
import asyncio
from functools import wraps


class BinanceAPIError(Exception):
    """Custom exception for Binance API errors"""
    def __init__(self, message: str, code: int = None, response: Dict = None):
        self.message = message
        self.code = code
        self.response = response
        super().__init__(self.message)


class RateLimiter:
    """Token bucket rate limiter for API calls"""

    def __init__(self, calls_per_minute: int = 1200):
        self.calls_per_minute = calls_per_minute
        self.tokens = calls_per_minute
        self.last_update = time.time()
        self.lock = asyncio.Lock() if asyncio.iscoroutinefunction(self.__init__) else None

    def consume(self, tokens: int = 1) -> bool:
        """Consume tokens, return True if allowed"""
        now = time.time()
        elapsed = now - self.last_update

        # Refill tokens based on time elapsed
        self.tokens = min(
            self.calls_per_minute,
            self.tokens + (elapsed * self.calls_per_minute / 60)
        )
        self.last_update = now

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def wait_time(self) -> float:
        """Calculate wait time needed for next request"""
        if self.tokens >= 1:
            return 0
        return (1 - self.tokens) * 60 / self.calls_per_minute


def retry_on_failure(max_retries: int = 3, backoff_factor: float = 2.0):
    """Decorator for retrying failed API calls with exponential backoff"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except (requests.exceptions.RequestException, BinanceAPIError) as e:
                    retries += 1
                    if retries >= max_retries:
                        raise
                    wait_time = backoff_factor ** retries
                    logging.warning(f"API call failed: {e}. Retrying in {wait_time}s... (attempt {retries}/{max_retries})")
                    time.sleep(wait_time)
            return None
        return wrapper
    return decorator


class BinanceFuturesClient:
    """Binance Futures API Client with institutional features"""

    BASE_URL = "https://fapi.binance.com"
    TESTNET_URL = "https://testnet.binancefuture.com"

    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = self.TESTNET_URL if testnet else self.BASE_URL
        self.session = requests.Session()
        self.session.headers.update({
            'X-MBX-APIKEY': self.api_key,
            'Content-Type': 'application/json'
        })
        self.rate_limiter = RateLimiter(calls_per_minute=1200)
        self.logger = logging.getLogger(__name__)

    def _generate_signature(self, params: Dict) -> str:
        """Generate HMAC SHA256 signature"""
        query_string = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature

    def _wait_for_rate_limit(self):
        """Wait if rate limit is exceeded"""
        if not self.rate_limiter.consume():
            wait_time = self.rate_limiter.wait_time()
            if wait_time > 0:
                self.logger.warning(f"Rate limit reached, waiting {wait_time:.2f}s")
                time.sleep(wait_time)

    @retry_on_failure(max_retries=3)
    def _request(self, method: str, endpoint: str, signed: bool = False, **kwargs) -> Dict:
        """Make API request with error handling"""
        self._wait_for_rate_limit()

        url = f"{self.base_url}{endpoint}"
        params = kwargs.get('params', {})

        if signed:
            params['timestamp'] = int(time.time() * 1000)
            params['signature'] = self._generate_signature(params)

        try:
            response = self.session.request(method, url, params=params, timeout=30)
            data = response.json()

            if response.status_code != 200:
                error_msg = data.get('msg', 'Unknown error')
                error_code = data.get('code', response.status_code)
                self.logger.error(f"API Error {error_code}: {error_msg}")
                raise BinanceAPIError(error_msg, error_code, data)

            return data

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request failed: {e}")
            raise BinanceAPIError(f"Request failed: {e}")

    # Market Data Endpoints
    def get_exchange_info(self, symbol: str = None) -> Dict:
        """Get exchange information"""
        params = {'symbol': symbol} if symbol else {}
        return self._request('GET', '/fapi/v1/exchangeInfo', params=params)

    def get_ticker_price(self, symbol: str) -> Dict:
        """Get current ticker price"""
        return self._request('GET', '/fapi/v1/ticker/price', params={'symbol': symbol})

    def get_order_book(self, symbol: str, limit: int = 100) -> Dict:
        """Get order book depth"""
        return self._request('GET', '/fapi/v1/depth', params={'symbol': symbol, 'limit': limit})

    def get_klines(self, symbol: str, interval: str, limit: int = 500, start_time: int = None, end_time: int = None) -> List:
        """Get candlestick data"""
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }
        if start_time:
            params['startTime'] = start_time
        if end_time:
            params['endTime'] = end_time
        return self._request('GET', '/fapi/v1/klines', params=params)

    def get_mark_price(self, symbol: str) -> Dict:
        """Get mark price"""
        return self._request('GET', '/fapi/v1/premiumIndex', params={'symbol': symbol})

    # Account Endpoints
    def get_account_info(self) -> Dict:
        """Get account information"""
        return self._request('GET', '/fapi/v2/account', signed=True)

    def get_balance(self) -> List[Dict]:
        """Get account balance"""
        account = self.get_account_info()
        return account.get('assets', [])

    def get_position_info(self, symbol: str = None) -> List[Dict]:
        """Get position information"""
        params = {'symbol': symbol} if symbol else {}
        return self._request('GET', '/fapi/v2/positionRisk', signed=True, params=params)

    # Trading Endpoints
    def set_leverage(self, symbol: str, leverage: int) -> Dict:
        """Set leverage for symbol"""
        params = {'symbol': symbol, 'leverage': leverage}
        return self._request('POST', '/fapi/v1/leverage', signed=True, params=params)

    def set_margin_type(self, symbol: str, margin_type: str) -> Dict:
        """Set margin type (ISOLATED or CROSSED)"""
        params = {'symbol': symbol, 'marginType': margin_type}
        return self._request('POST', '/fapi/v1/marginType', signed=True, params=params)

    def place_order(self, symbol: str, side: str, order_type: str, quantity: float,
                   price: float = None, time_in_force: str = 'GTC',
                   reduce_only: bool = False, stop_price: float = None) -> Dict:
        """Place a new order"""
        params = {
            'symbol': symbol,
            'side': side,  # BUY or SELL
            'type': order_type,  # LIMIT, MARKET, STOP, TAKE_PROFIT
            'quantity': quantity,
            'timeInForce': time_in_force
        }

        if price:
            params['price'] = price
        if reduce_only:
            params['reduceOnly'] = 'true'
        if stop_price:
            params['stopPrice'] = stop_price

        self.logger.info(f"Placing {side} {order_type} order: {quantity} {symbol} @ {price}")
        return self._request('POST', '/fapi/v1/order', signed=True, params=params)

    def cancel_order(self, symbol: str, order_id: int) -> Dict:
        """Cancel an open order"""
        params = {'symbol': symbol, 'orderId': order_id}
        self.logger.info(f"Cancelling order {order_id} for {symbol}")
        return self._request('DELETE', '/fapi/v1/order', signed=True, params=params)

    def cancel_all_orders(self, symbol: str) -> Dict:
        """Cancel all open orders for a symbol"""
        params = {'symbol': symbol}
        self.logger.info(f"Cancelling all orders for {symbol}")
        return self._request('DELETE', '/fapi/v1/allOpenOrders', signed=True, params=params)

    def get_open_orders(self, symbol: str = None) -> List[Dict]:
        """Get all open orders"""
        params = {'symbol': symbol} if symbol else {}
        return self._request('GET', '/fapi/v1/openOrders', signed=True, params=params)

    def get_order(self, symbol: str, order_id: int) -> Dict:
        """Query order status"""
        params = {'symbol': symbol, 'orderId': order_id}
        return self._request('GET', '/fapi/v1/order', signed=True, params=params)

    # Utility Methods
    def get_server_time(self) -> int:
        """Get server time"""
        response = self._request('GET', '/fapi/v1/time')
        return response['serverTime']

    def test_connectivity(self) -> bool:
        """Test API connectivity"""
        try:
            self._request('GET', '/fapi/v1/ping')
            return True
        except:
            return False

    def get_24h_stats(self, symbol: str) -> Dict:
        """Get 24h ticker statistics"""
        return self._request('GET', '/fapi/v1/ticker/24hr', params={'symbol': symbol})

    def close_position(self, symbol: str, position_side: str = None) -> Dict:
        """Close position by placing opposite market order"""
        positions = self.get_position_info(symbol)

        for pos in positions:
            if pos['symbol'] == symbol:
                position_amt = float(pos['positionAmt'])
                if position_amt != 0:
                    side = 'SELL' if position_amt > 0 else 'BUY'
                    quantity = abs(position_amt)

                    self.logger.info(f"Closing position: {side} {quantity} {symbol}")
                    return self.place_order(
                        symbol=symbol,
                        side=side,
                        order_type='MARKET',
                        quantity=quantity,
                        reduce_only=True
                    )

        return {'msg': 'No open position to close'}
