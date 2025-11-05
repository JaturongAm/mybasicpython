"""
Unit tests for Binance Futures API client
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import time
import requests
from binance_client import (
    BinanceFuturesClient,
    BinanceAPIError,
    RateLimiter,
    retry_on_failure
)


class TestRateLimiter:
    """Test rate limiter functionality"""

    def test_rate_limiter_creation(self):
        """Test rate limiter initialization"""
        limiter = RateLimiter(calls_per_minute=1200)
        assert limiter.calls_per_minute == 1200
        assert limiter.tokens == 1200

    def test_rate_limiter_consume_success(self):
        """Test successful token consumption"""
        limiter = RateLimiter(calls_per_minute=1200)
        assert limiter.consume(1) is True
        assert limiter.tokens == 1199

    def test_rate_limiter_consume_failure(self):
        """Test token consumption when insufficient tokens"""
        limiter = RateLimiter(calls_per_minute=10)
        limiter.tokens = 0
        assert limiter.consume(1) is False

    def test_rate_limiter_refill(self):
        """Test token refill over time"""
        limiter = RateLimiter(calls_per_minute=60)
        limiter.tokens = 0
        limiter.last_update = time.time() - 1  # 1 second ago

        # After 1 second, should refill 1 token
        consumed = limiter.consume(1)
        assert consumed is True

    def test_rate_limiter_wait_time(self):
        """Test wait time calculation"""
        limiter = RateLimiter(calls_per_minute=60)
        limiter.tokens = 0.5

        wait_time = limiter.wait_time()
        assert wait_time > 0
        assert wait_time < 1  # Should be less than 1 second


class TestBinanceFuturesClient:
    """Test Binance Futures API client"""

    def test_client_creation(self, api_config):
        """Test client initialization"""
        client = BinanceFuturesClient(
            api_key=api_config.api_key,
            api_secret=api_config.api_secret,
            testnet=api_config.testnet
        )

        assert client.api_key == api_config.api_key
        assert client.base_url == BinanceFuturesClient.TESTNET_URL
        assert isinstance(client.rate_limiter, RateLimiter)

    def test_client_production_url(self, api_config):
        """Test client uses production URL when testnet=False"""
        client = BinanceFuturesClient(
            api_key=api_config.api_key,
            api_secret=api_config.api_secret,
            testnet=False
        )

        assert client.base_url == BinanceFuturesClient.BASE_URL

    def test_generate_signature(self, mock_binance_client):
        """Test HMAC signature generation"""
        params = {'symbol': 'BTCUSDT', 'timestamp': 1609459200000}
        signature = mock_binance_client._generate_signature(params)

        assert isinstance(signature, str)
        assert len(signature) == 64  # SHA256 hex digest length

    def test_request_success(self, mock_binance_client, binance_test_responses):
        """Test successful API request"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value=binance_test_responses['ticker_price'])
        mock_binance_client.session.request = Mock(return_value=mock_response)

        result = mock_binance_client._request('GET', '/fapi/v1/ticker/price')

        assert result['symbol'] == 'BTCUSDT'
        assert 'price' in result

    def test_request_api_error(self, mock_binance_client):
        """Test API request with error response"""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json = Mock(return_value={'code': -1000, 'msg': 'Invalid request'})
        mock_binance_client.session.request = Mock(return_value=mock_response)

        with pytest.raises(BinanceAPIError) as exc_info:
            mock_binance_client._request('GET', '/fapi/v1/test')

        assert exc_info.value.code == -1000
        assert 'Invalid request' in exc_info.value.message

    def test_request_network_error(self, mock_binance_client):
        """Test API request with network error"""
        mock_binance_client.session.request = Mock(side_effect=requests.exceptions.ConnectionError("Network error"))

        with pytest.raises(BinanceAPIError):
            mock_binance_client._request('GET', '/fapi/v1/test')

    def test_get_ticker_price(self, mock_binance_client, binance_test_responses):
        """Test get ticker price"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value=binance_test_responses['ticker_price'])
        mock_binance_client.session.request = Mock(return_value=mock_response)

        result = mock_binance_client.get_ticker_price('BTCUSDT')

        assert result['symbol'] == 'BTCUSDT'
        assert result['price'] == '40000.00'

    def test_get_account_info(self, mock_binance_client, binance_test_responses):
        """Test get account info"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value=binance_test_responses['account_info'])
        mock_binance_client.session.request = Mock(return_value=mock_response)

        result = mock_binance_client.get_account_info()

        assert 'assets' in result
        assert result['assets'][0]['asset'] == 'USDT'

    def test_get_balance(self, mock_binance_client, binance_test_responses):
        """Test get balance"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value=binance_test_responses['account_info'])
        mock_binance_client.session.request = Mock(return_value=mock_response)

        result = mock_binance_client.get_balance()

        assert len(result) > 0
        assert result[0]['asset'] == 'USDT'

    def test_place_order(self, mock_binance_client, binance_test_responses):
        """Test place order"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value=binance_test_responses['order_response'])
        mock_binance_client.session.request = Mock(return_value=mock_response)

        result = mock_binance_client.place_order(
            symbol='BTCUSDT',
            side='BUY',
            order_type='LIMIT',
            quantity=0.001,
            price=40000.0
        )

        assert result['orderId'] == 12345
        assert result['symbol'] == 'BTCUSDT'
        assert result['side'] == 'BUY'

    def test_cancel_order(self, mock_binance_client):
        """Test cancel order"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value={'orderId': 12345, 'status': 'CANCELED'})
        mock_binance_client.session.request = Mock(return_value=mock_response)

        result = mock_binance_client.cancel_order('BTCUSDT', 12345)

        assert result['orderId'] == 12345
        assert result['status'] == 'CANCELED'

    def test_set_leverage(self, mock_binance_client):
        """Test set leverage"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value={'leverage': 5, 'symbol': 'BTCUSDT'})
        mock_binance_client.session.request = Mock(return_value=mock_response)

        result = mock_binance_client.set_leverage('BTCUSDT', 5)

        assert result['leverage'] == 5
        assert result['symbol'] == 'BTCUSDT'

    def test_get_klines(self, mock_binance_client, binance_test_responses):
        """Test get klines"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value=binance_test_responses['klines'])
        mock_binance_client.session.request = Mock(return_value=mock_response)

        result = mock_binance_client.get_klines('BTCUSDT', '1h', limit=3)

        assert len(result) == 3
        assert isinstance(result[0], list)

    def test_test_connectivity(self, mock_binance_client):
        """Test connectivity check"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value={})
        mock_binance_client.session.request = Mock(return_value=mock_response)

        result = mock_binance_client.test_connectivity()

        assert result is True

    def test_test_connectivity_failure(self, mock_binance_client):
        """Test connectivity check failure"""
        mock_binance_client.session.request = Mock(side_effect=Exception("Connection failed"))

        result = mock_binance_client.test_connectivity()

        assert result is False


class TestRetryDecorator:
    """Test retry decorator functionality"""

    def test_retry_success_first_attempt(self):
        """Test function succeeds on first attempt"""
        @retry_on_failure(max_retries=3)
        def success_func():
            return "success"

        result = success_func()
        assert result == "success"

    def test_retry_success_after_failures(self):
        """Test function succeeds after retries"""
        call_count = [0]

        @retry_on_failure(max_retries=3)
        def eventually_success():
            call_count[0] += 1
            if call_count[0] < 3:
                raise BinanceAPIError("Temporary error")
            return "success"

        result = eventually_success()
        assert result == "success"
        assert call_count[0] == 3

    def test_retry_max_retries_exceeded(self):
        """Test function fails after max retries"""
        @retry_on_failure(max_retries=2)
        def always_fails():
            raise BinanceAPIError("Permanent error")

        with pytest.raises(BinanceAPIError):
            always_fails()

    @patch('time.sleep')
    def test_retry_backoff(self, mock_sleep):
        """Test exponential backoff"""
        call_count = [0]

        @retry_on_failure(max_retries=3, backoff_factor=2.0)
        def failing_func():
            call_count[0] += 1
            if call_count[0] < 3:
                raise requests.exceptions.RequestException("Error")
            return "success"

        result = failing_func()

        assert result == "success"
        # Should have called sleep with exponential backoff
        assert mock_sleep.call_count == 2


class TestBinanceAPIError:
    """Test custom exception"""

    def test_api_error_creation(self):
        """Test API error initialization"""
        error = BinanceAPIError("Test error", code=-1000, response={'msg': 'test'})

        assert error.message == "Test error"
        assert error.code == -1000
        assert error.response == {'msg': 'test'}

    def test_api_error_string_representation(self):
        """Test API error string representation"""
        error = BinanceAPIError("Test error")
        assert str(error) == "Test error"


@pytest.mark.parametrize("side,order_type,expected", [
    ('BUY', 'LIMIT', True),
    ('SELL', 'LIMIT', True),
    ('BUY', 'MARKET', True),
    ('SELL', 'MARKET', True),
])
def test_order_types(mock_binance_client, binance_test_responses, side, order_type, expected):
    """Test various order types"""
    response_data = binance_test_responses['order_response'].copy()
    response_data['side'] = side
    response_data['type'] = order_type

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json = Mock(return_value=response_data)
    mock_binance_client.session.request = Mock(return_value=mock_response)

    result = mock_binance_client.place_order(
        symbol='BTCUSDT',
        side=side,
        order_type=order_type,
        quantity=0.001,
        price=40000.0 if order_type == 'LIMIT' else None
    )

    assert result['side'] == side
    assert result['type'] == order_type
