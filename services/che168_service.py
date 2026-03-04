"""
Che168 Service - Direct API Implementation
Business logic layer for Chinese car marketplace integration via direct Che168 API access

Uses Chinese residential proxy for direct API calls instead of BravoMotors proxy dependency.
Implements session bootstrapping, circuit breakers, and static fallback for reliability.
"""

import asyncio
import hashlib
import json
import logging
import time
import random
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List
from urllib.parse import urlencode
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from requests.exceptions import RequestException, Timeout, ConnectionError
from diskcache import Cache

from parsers.che168_parser import Che168Parser
from services.sold_cars_registry import SoldCarsRegistry

logger = logging.getLogger(__name__)

# Known signature error messages from Che168 API
SIGNATURE_ERROR_MESSAGES = ["签名错误", "signature error", "sign error", "invalid sign"]

# Known sold/expired car indicators from Che168 API
SOLD_CAR_INDICATORS = ["已成交", "已下架", "已售出", "车源已售", "已过期"]

# Che168 API Base URLs (direct access)
CHE168_SEARCH_API = "https://api2scsou.che168.com"
CHE168_DETAIL_API = "https://apiuscdt.che168.com"
CHE168_MOBILE_SITE = "https://m.che168.com"

# Static fallback data directory
STATIC_CACHE_DIR = Path(__file__).parent.parent / "Che168"

# Cache TTLs (in seconds) - Extended for better reliability
CACHE_TTL_BRANDS = 86400      # 24 hours
CACHE_TTL_MODELS = 43200      # 12 hours
CACHE_TTL_YEARS = 43200       # 12 hours
CACHE_TTL_SEARCH = 900        # 15 minutes
CACHE_TTL_CAR_DETAIL = 1800   # 30 minutes

# Che168-specific headers for mobile API access
CHE168_MOBILE_HEADERS = {
    'accept': 'application/json, text/plain, */*',
    'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'user-agent': 'Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36',
    'referer': 'https://m.che168.com/',
    'origin': 'https://m.che168.com',
    'sec-ch-ua': '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
    'sec-ch-ua-mobile': '?1',
    'sec-ch-ua-platform': '"Android"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-site',
}

# Alternative headers for desktop access (fallback)
CHE168_DESKTOP_HEADERS = {
    'accept': 'application/json, text/javascript, */*; q=0.01',
    'accept-language': 'zh-CN,zh;q=0.9',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'referer': 'https://www.che168.com/',
    'origin': 'https://www.che168.com',
    'sec-ch-ua': '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-site',
}


class ProxyCircuitBreaker:
    """Per-endpoint circuit breaker for intelligent failover"""

    def __init__(self, name: str, threshold: int = 5, reset_seconds: int = 30):
        self.name = name
        self.failures = 0
        self.threshold = threshold
        self.reset_seconds = reset_seconds
        self.last_failure = 0
        self.state = "closed"  # closed, open, half-open

    def is_available(self) -> bool:
        if self.state == "closed":
            return True
        if time.time() - self.last_failure > self.reset_seconds:
            self.state = "half-open"
            return True
        return False

    def record_success(self):
        self.failures = 0
        self.state = "closed"

    def record_failure(self):
        self.failures += 1
        self.last_failure = time.time()
        if self.failures >= self.threshold:
            self.state = "open"
            logger.warning(f"Circuit breaker '{self.name}' OPENED after {self.failures} failures")

    def get_status(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state,
            "failures": self.failures,
            "threshold": self.threshold,
            "time_until_reset": max(0, int(self.reset_seconds - (time.time() - self.last_failure))) if self.state == "open" else 0
        }


class Che168Service:
    """
    Che168 service for Chinese car marketplace integration via direct API access

    Routes all requests directly to che168.com APIs through Chinese residential proxy with:
    - Session bootstrapping via m.che168.com for cookie authentication
    - Mobile headers for better API access
    - Circuit breakers per endpoint for intelligent failover
    - Static file fallback when API unavailable
    - Extended caching for reliability

    Provides comprehensive functionality for:
    - Car search with filters and pagination
    - Individual car detail retrieval
    - Brand/model/year cascading filters
    - Disk-based caching for performance
    """

    def __init__(self, proxy_client=None):
        self.proxy_client = proxy_client
        self.parser = Che168Parser()

        # Session management
        self.session = requests.Session()

        # Session bootstrapping state (for signature authentication)
        self._session_initialized = False
        self._session_cookies = None
        self._last_session_time = 0
        self._session_ttl = 300  # 5 minutes session validity
        self._device_id = str(uuid.uuid4()).replace('-', '')[:32]

        # Rate limiting
        self.last_request_time = 0
        self.request_count = 0

        # Disk-based cache
        self.cache = Cache('/tmp/che168_cache')

        # Circuit breakers per endpoint type
        self.circuit_breakers = {
            "search": ProxyCircuitBreaker("search", threshold=5, reset_seconds=30),
            "brands": ProxyCircuitBreaker("brands", threshold=3, reset_seconds=60),
            "detail": ProxyCircuitBreaker("detail", threshold=5, reset_seconds=30),
        }

        # Legacy circuit breaker state (for backward compatibility)
        self.circuit_breaker_failures = 0
        self.circuit_breaker_last_reset = time.time()
        self.circuit_breaker_cooldown_until = 0

        # Track which header set works better
        self.use_mobile_headers = True

        # Track consecutive signature errors
        self._signature_error_count = 0
        self._max_signature_errors = 2

        # Playwright availability: None=untested, True=works, False=unavailable
        self._playwright_available = None

        # Sold cars registry
        self.sold_registry = SoldCarsRegistry()

        # Setup session
        self._setup_session()

    def _setup_session(self):
        """Setup session with direct Che168 API requirements"""
        self.session.headers.update(CHE168_MOBILE_HEADERS)

        # Session configuration
        self.session.timeout = (10, 30)

        # Connection pooling with retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"]
        )

        adapter = HTTPAdapter(
            pool_connections=20,
            pool_maxsize=100,
            max_retries=retry_strategy,
            pool_block=False
        )

        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _is_sold_car_response(self, message: str) -> bool:
        """Check if API error message indicates the car has been sold/removed"""
        if not message:
            return False
        return any(indicator in message for indicator in SOLD_CAR_INDICATORS)

    def _get_proxy_config(self) -> Optional[Dict[str, str]]:
        """Get proxy configuration from proxy_client"""
        if not self.proxy_client:
            logger.warning("No proxy client configured - requests will go direct")
            return None

        # Use the proxy client's session proxies if available
        if hasattr(self.proxy_client, 'session') and hasattr(self.proxy_client.session, 'proxies'):
            proxies = self.proxy_client.session.proxies
            if proxies:
                logger.debug(f"Using proxy configuration from proxy_client")
                return proxies

        # If proxy_client has proxy_configs, build proxy URL
        if hasattr(self.proxy_client, 'proxy_configs') and self.proxy_client.proxy_configs:
            try:
                config = self.proxy_client.proxy_configs[0]
                proxy_url = f"http://{config['auth']}@{config['proxy']}"
                return {"http": proxy_url, "https": proxy_url}
            except (KeyError, IndexError) as e:
                logger.warning(f"Failed to build proxy URL from config: {e}")

        return None

    async def _bootstrap_session(self) -> bool:
        """
        Initialize session using Playwright to execute JS and obtain valid cookies.
        Falls back to requests-based approach if Playwright fails.
        Caches Playwright availability to avoid repeated failures.
        """
        await self._rate_limit()

        # Skip Playwright if already known to be unavailable
        if self._playwright_available is False:
            return await self._bootstrap_session_requests()

        try:
            from playwright.async_api import async_playwright

            logger.info("🔄 Bootstrapping session via Playwright (m.che168.com)...")

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent=CHE168_MOBILE_HEADERS['user-agent']
                )
                page = await context.new_page()
                await page.goto(CHE168_MOBILE_SITE + "/", wait_until='networkidle', timeout=15000)

                cookies = await context.cookies()
                for cookie in cookies:
                    self.session.cookies.set(cookie['name'], cookie['value'], domain=cookie.get('domain', ''))

                self._session_cookies = {c['name']: c['value'] for c in cookies}
                self._session_initialized = True
                self._last_session_time = time.time()
                self._signature_error_count = 0

                await browser.close()
                self._playwright_available = True
                logger.info(f"✅ Session bootstrapped with {len(cookies)} cookies: {list(self._session_cookies.keys())}")
                return True

        except Exception as e:
            self._playwright_available = False
            logger.warning(f"⚠️ Playwright unavailable (will use requests fallback): {type(e).__name__}")
            return await self._bootstrap_session_requests()

    async def _bootstrap_session_requests(self) -> bool:
        """
        Fallback: Initialize session by visiting mobile site with requests.
        Used when Playwright is not available.
        """
        try:
            if self._playwright_available is False:
                logger.debug("🔄 Bootstrapping session via requests (Playwright unavailable)...")
            else:
                logger.info("🔄 Bootstrapping session via requests (m.che168.com)...")
            proxies = self._get_proxy_config()

            response = self.session.get(
                CHE168_MOBILE_SITE + "/",
                headers=CHE168_MOBILE_HEADERS,
                proxies=proxies,
                timeout=(10, 30),
                allow_redirects=True
            )

            if response.status_code == 200:
                self.session.cookies.update(response.cookies)
                self._session_cookies = dict(response.cookies)
                self._session_initialized = True
                self._last_session_time = time.time()
                self._signature_error_count = 0
                logger.info(f"✅ Session bootstrapped (requests). Cookies: {list(response.cookies.keys())}")
                return True
            else:
                logger.warning(f"⚠️ Session bootstrap returned status {response.status_code}")

        except Exception as e:
            logger.error(f"❌ Requests session bootstrap failed: {e}")

        return False

    def _is_session_valid(self) -> bool:
        """Check if current session is still valid based on TTL"""
        if not self._session_initialized:
            return False
        return (time.time() - self._last_session_time) < self._session_ttl

    def _is_signature_error(self, response_data: Dict) -> bool:
        """Check if API response indicates a signature error"""
        if not isinstance(response_data, dict):
            return False

        returncode = response_data.get("returncode")
        if returncode not in [0, None, "0"]:
            message = str(response_data.get("message", "")).lower()
            for error_msg in SIGNATURE_ERROR_MESSAGES:
                if error_msg.lower() in message:
                    return True

        return False

    def _get_device_id(self) -> str:
        """Get or generate a persistent device ID"""
        return self._device_id

    def _build_request_params(self, base_params: Dict[str, Any]) -> Dict[str, Any]:
        """Build complete request parameters with all required fields"""
        params = dict(base_params)

        # Required system params
        params['_appid'] = '2sc.m'
        params['v'] = '11.41.5'
        params['deviceid'] = self._get_device_id()
        params['userid'] = '0'
        params['s_pid'] = '0'
        params['s_cid'] = '0'

        # Session-specific params if available
        if self._session_initialized and self._session_cookies:
            session_id = self._session_cookies.get('sessionid', '')
            if session_id:
                params['sessionid'] = session_id

        return params

    def _build_direct_url(self, base_url: str, endpoint_path: str, params: Dict[str, Any] = None) -> str:
        """Build direct Che168 API URL with parameters"""
        full_url = f"{base_url}{endpoint_path}"
        if params:
            param_string = urlencode(params, safe='')
            full_url = f"{full_url}?{param_string}"
        return full_url

    def _get_cache_key(self, prefix: str, params: Dict[str, Any] = None) -> str:
        """Generate a cache key from prefix and parameters"""
        if params:
            param_str = json.dumps(params, sort_keys=True)
            param_hash = hashlib.md5(param_str.encode()).hexdigest()[:12]
            return f"che168:{prefix}:{param_hash}"
        return f"che168:{prefix}"

    async def _rate_limit(self):
        """Rate limiting for Che168 API (200ms between requests)"""
        current_time = time.time()
        min_interval = 0.2

        if current_time - self.last_request_time < min_interval:
            await asyncio.sleep(min_interval - (current_time - self.last_request_time))

        self.last_request_time = time.time()
        self.request_count += 1

        # Add random delay occasionally
        if self.request_count % 20 == 0:
            await asyncio.sleep(random.uniform(0.5, 1.5))

    def _check_circuit_breaker(self, endpoint_type: str = "search") -> bool:
        """Check if circuit breaker allows requests"""
        cb = self.circuit_breakers.get(endpoint_type, self.circuit_breakers["search"])
        return cb.is_available()

    def _record_success(self, endpoint_type: str = "search"):
        """Record successful request for circuit breaker"""
        cb = self.circuit_breakers.get(endpoint_type, self.circuit_breakers["search"])
        cb.record_success()
        self.circuit_breaker_failures = 0

    def _record_failure(self, endpoint_type: str = "search"):
        """Record failed request for circuit breaker"""
        cb = self.circuit_breakers.get(endpoint_type, self.circuit_breakers["search"])
        cb.record_failure()
        self.circuit_breaker_failures += 1

    async def _update_static_fallback(self, data_type: str, data: Dict) -> None:
        """Save successful API responses back to static fallback files to keep them fresh"""
        file_map = {
            'brands': STATIC_CACHE_DIR / 'brands.json',
            'search': STATIC_CACHE_DIR / 'cars.json',
        }
        file_path = file_map.get(data_type)
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                logger.info(f"📦 Updated static fallback for '{data_type}'")
            except Exception as e:
                logger.warning(f"Failed to update fallback for '{data_type}': {e}")

    async def _get_static_fallback(self, data_type: str) -> Optional[Dict]:
        """Load static fallback data when all API attempts fail"""
        file_map = {
            'brands': STATIC_CACHE_DIR / 'brands.json',
            'search': STATIC_CACHE_DIR / 'cars.json',
        }

        file_path = file_map.get(data_type)
        if file_path and file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"📦 Loaded static fallback data for '{data_type}' from {file_path}")
                    return data
            except Exception as e:
                logger.error(f"❌ Failed to load static fallback for '{data_type}': {e}")

        return None

    async def _make_request(
        self,
        base_url: str,
        endpoint_path: str,
        params: Dict = None,
        max_retries: int = 3,
        endpoint_type: str = "search"
    ) -> Dict[str, Any]:
        """
        Make HTTP request directly to Che168 API with proxy support
        """
        await self._rate_limit()

        if params is None:
            params = {}

        # Check if we should skip API and go straight to static fallback
        if self._signature_error_count >= self._max_signature_errors:
            logger.info(f"⏭️ Skipping API due to {self._signature_error_count} signature errors, using static fallback")
            if endpoint_type in ["brands", "search"]:
                fallback_data = await self._get_static_fallback(endpoint_type)
                if fallback_data:
                    return fallback_data

        # Check circuit breaker
        if not self._check_circuit_breaker(endpoint_type):
            logger.warning(f"🔴 Circuit breaker open for {endpoint_type}, trying static fallback")
            if endpoint_type in ["brands", "search"]:
                fallback_data = await self._get_static_fallback(endpoint_type)
                if fallback_data:
                    return fallback_data

            return {
                "returncode": 503,
                "message": "Service temporarily unavailable (circuit breaker open)",
                "result": {},
            }

        # Ensure session is valid before making API request
        if not self._is_session_valid():
            logger.info("🔄 Session expired or not initialized, bootstrapping...")
            await self._bootstrap_session()

        # Build complete request params
        full_params = self._build_request_params(params)

        # Build the direct URL
        url = self._build_direct_url(base_url, endpoint_path, full_params)

        request_start_time = time.time()
        last_exception = None

        # Get proxy configuration
        proxies = self._get_proxy_config()

        for attempt in range(max_retries + 1):
            try:
                # Rotate headers on retry
                if attempt > 0:
                    self.use_mobile_headers = not self.use_mobile_headers
                    headers = CHE168_MOBILE_HEADERS if self.use_mobile_headers else CHE168_DESKTOP_HEADERS
                    self.session.headers.update(headers)

                logger.debug(f"🌐 Making direct request (attempt {attempt + 1}): {endpoint_path}")

                # Make request with proxy
                response = self.session.get(
                    url,
                    proxies=proxies,
                    timeout=(10, 30)
                )
                response.raise_for_status()

                # Parse JSON response
                json_data = response.json()

                # Check for signature error in response
                if self._is_signature_error(json_data):
                    self._signature_error_count += 1
                    logger.warning(f"⚠️ Signature error detected (count: {self._signature_error_count}): {json_data.get('message', 'Unknown')}")

                    # Invalidate session and try to re-bootstrap
                    self._session_initialized = False

                    if attempt < max_retries:
                        logger.info("🔄 Attempting to refresh session...")
                        await self._bootstrap_session()
                        full_params = self._build_request_params(params)
                        url = self._build_direct_url(base_url, endpoint_path, full_params)
                        await asyncio.sleep(1)
                        continue

                    # All retries exhausted, use static fallback
                    if endpoint_type in ["brands", "search"]:
                        fallback_data = await self._get_static_fallback(endpoint_type)
                        if fallback_data:
                            logger.info(f"📦 Using static fallback after signature errors")
                            return fallback_data

                    return json_data

                # Log slow requests
                request_time = time.time() - request_start_time
                if request_time > 5.0:
                    logger.warning(f"⏱️ Slow request detected: {endpoint_path} took {request_time:.2f}s")

                # Record success
                self._record_success(endpoint_type)
                self._signature_error_count = 0

                return json_data

            except RequestException as e:
                last_exception = e
                status_code = getattr(e.response, 'status_code', None) if hasattr(e, 'response') and e.response else None

                logger.warning(f"❌ Request attempt {attempt + 1}/{max_retries + 1} failed: {str(e)}")

                # Record failure
                self._record_failure(endpoint_type)

                # Retry with exponential backoff
                if attempt < max_retries:
                    backoff_time = (2 ** attempt) * 0.5 + random.uniform(0, 0.5)
                    logger.info(f"⏳ Retrying in {backoff_time:.1f}s...")
                    await asyncio.sleep(backoff_time)
                    continue

                # All retries exhausted, try static fallback
                if endpoint_type in ["brands", "search"]:
                    fallback_data = await self._get_static_fallback(endpoint_type)
                    if fallback_data:
                        logger.info(f"📦 Using static fallback after {max_retries + 1} failed attempts")
                        return fallback_data

                return {
                    "returncode": status_code or 1,
                    "message": f"Request failed: {str(e)}",
                    "result": {},
                }

            except Exception as e:
                logger.error(f"❌ Unexpected error in request: {str(e)}")
                if endpoint_type in ["brands", "search"]:
                    fallback_data = await self._get_static_fallback(endpoint_type)
                    if fallback_data:
                        logger.info(f"📦 Using static fallback after unexpected error")
                        return fallback_data

                return {
                    "returncode": 1,
                    "message": f"Unexpected error: {str(e)}",
                    "result": {},
                }

        return {
            "returncode": 1,
            "message": f"Request failed after {max_retries + 1} attempts: {str(last_exception)}",
            "result": {},
        }

    async def search_cars(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Search cars with specified filters"""
        try:
            # Build search parameters
            params = {
                "_appid": "2sc.m",
                "pageindex": str(filters.get("pageindex", 1)),
                "pagesize": str(filters.get("pagesize", 20)),
                "pvareaid": "111478",
                "scene_no": "12",
                "sort": str(filters.get("sort", 0)),
            }

            # Add optional filters
            if filters.get("brandid"):
                params["brandid"] = str(filters["brandid"])
            if filters.get("seriesid"):
                params["seriesid"] = str(filters["seriesid"])
            if filters.get("seriesyearid"):
                params["seriesyearid"] = str(filters["seriesyearid"])
            if filters.get("specid"):
                params["specid"] = str(filters["specid"])
            if filters.get("service"):
                params["service"] = str(filters["service"])
            if filters.get("price"):
                params["price"] = str(filters["price"])
            if filters.get("agerange"):
                params["agerange"] = str(filters["agerange"])
            if filters.get("mileage"):
                params["mileage"] = str(filters["mileage"])
            if filters.get("fueltype"):
                params["fueltype"] = str(filters["fueltype"])
            if filters.get("displacement"):
                params["displacement"] = str(filters["displacement"])

            logger.info(f"🔍 Che168 Search: Calling direct API with params: {list(params.keys())}")

            # Check cache first (only for non-page-1 requests)
            cache_key = self._get_cache_key("search", params)
            pageindex = int(params.get("pageindex", 1))
            if pageindex > 1:
                cached = self.cache.get(cache_key)
                if cached:
                    logger.debug(f"📋 Cache hit for search: {cache_key}")
                    return cached

            # Make request
            json_data = await self._make_request(
                CHE168_SEARCH_API,
                "/api/v11/search",
                params,
                endpoint_type="search"
            )

            logger.info(f"🔍 Che168 Search: API Response - returncode: {json_data.get('returncode')}, message: {json_data.get('message')}")

            result = self.parser.parse_car_search_response(json_data)

            # Filter out known sold cars from search results
            if result.get("success") and result.get("result", {}).get("carlist"):
                carlist = result["result"]["carlist"]
                filtered_carlist, removed_count = self.sold_registry.filter_sold(carlist)
                if removed_count > 0:
                    result["result"]["carlist"] = filtered_carlist
                    result["result"]["filtered_sold_count"] = removed_count
                    logger.info(f"🚫 Filtered {removed_count} sold cars from search results")

            # Cache successful results
            if result.get("success"):
                self.cache.set(cache_key, result, expire=CACHE_TTL_SEARCH)
                # Update static fallback with fresh data
                await self._update_static_fallback("search", json_data)

            return result

        except Exception as e:
            logger.error(f"❌ Error in search_cars: {str(e)}")

            # Try static fallback on exception
            try:
                fallback_data = await self._get_static_fallback("search")
                if fallback_data:
                    logger.info("📦 Using static fallback for search due to exception")
                    return self.parser.parse_car_search_response(fallback_data)
            except Exception as fallback_error:
                logger.error(f"❌ Static fallback also failed: {fallback_error}")

            return {
                "returncode": 1,
                "message": f"Service error: {str(e)}",
                "result": {
                    "carlist": [],
                    "totalcount": 0,
                    "pageindex": filters.get("pageindex", 1),
                    "pagesize": filters.get("pagesize", 20),
                    "pagecount": 0,
                    "queryid": "",
                    "service": [],
                    "filters": []
                },
                "success": False
            }

    async def get_brands(self) -> Dict[str, Any]:
        """Get all available car brands from Che168"""
        try:
            # Check cache first
            cache_key = self._get_cache_key("brands")
            cached = self.cache.get(cache_key)
            if cached:
                logger.debug("📋 Cache hit for brands")
                return cached

            params = {
                "_appid": "2sc.m",
                "cid": "0",
                "pid": "0",
                "isenergy": "0",
                "s_pid": "0",
                "s_cid": "0",
            }

            json_data = await self._make_request(
                CHE168_SEARCH_API,
                "/api/v2/getbrands",
                params,
                endpoint_type="brands"
            )
            result = self.parser.parse_brands_response(json_data)

            # Cache successful results
            if result.get("returncode") == 0:
                self.cache.set(cache_key, result, expire=CACHE_TTL_BRANDS)
                # Update static fallback with fresh data
                await self._update_static_fallback("brands", json_data)

            return result

        except Exception as e:
            logger.error(f"❌ Error in get_brands: {str(e)}")

            # Try static fallback
            try:
                fallback_data = await self._get_static_fallback("brands")
                if fallback_data:
                    logger.info("📦 Using static fallback for brands")
                    return self.parser.parse_brands_response(fallback_data)
            except Exception as fallback_error:
                logger.error(f"❌ Static fallback also failed for brands: {fallback_error}")

            return {
                "returncode": -1,
                "message": f"Service error: {str(e)}",
                "result": {"hotbrand": [], "brands": []},
                "success": False
            }

    async def get_models(self, brand_id: int) -> Dict[str, Any]:
        """Get available models for a specific brand"""
        try:
            # Check cache first
            cache_key = self._get_cache_key("models", {"brand_id": brand_id})
            cached = self.cache.get(cache_key)
            if cached:
                logger.debug(f"📋 Cache hit for models: brand_id={brand_id}")
                return cached

            params = {
                "_appid": "2sc.m",
                "pageindex": "1",
                "pagesize": "1",
                "brandid": str(brand_id),
                "pvareaid": "111478",
                "scene_no": "12",
            }

            raw_response = await self._make_request(
                CHE168_SEARCH_API,
                "/api/v11/search",
                params,
                endpoint_type="search"
            )

            if raw_response.get("returncode") != 0:
                return {
                    "returncode": raw_response.get("returncode", -1),
                    "message": raw_response.get('message', 'Unknown error'),
                    "result": {},
                    "success": False
                }

            result = self.parser.parse_car_search_response(raw_response)

            # Extract models from filters array
            models = []
            if result.get("result", {}).get("filters"):
                for filter_item in result["result"]["filters"]:
                    if filter_item.get("key") == "seriesid":
                        models.append({
                            "id": int(filter_item.get("value", 0)),
                            "name": filter_item.get("title", ""),
                            "value": filter_item.get("value", ""),
                            "title": filter_item.get("title", ""),
                        })

            # Add models to result
            if "result" in result and isinstance(result["result"], dict):
                result["result"]["models"] = models
                result["result"]["series"] = models

            # Cache successful results
            if result.get("success"):
                self.cache.set(cache_key, result, expire=CACHE_TTL_MODELS)

            logger.info(f"✅ Successfully fetched {len(models)} models for brand {brand_id}")
            return result

        except Exception as e:
            logger.error(f"❌ Error in get_models for brand {brand_id}: {str(e)}")
            return {
                "returncode": 1,
                "message": f"Service error: {str(e)}",
                "result": {},
                "success": False
            }

    async def get_years(self, brand_id: int, series_id: int) -> Dict[str, Any]:
        """Get available years for a specific brand and model"""
        try:
            # Check cache first
            cache_key = self._get_cache_key("years", {"brand_id": brand_id, "series_id": series_id})
            cached = self.cache.get(cache_key)
            if cached:
                logger.debug(f"📋 Cache hit for years: brand_id={brand_id}, series_id={series_id}")
                return cached

            params = {
                "_appid": "2sc.m",
                "pageindex": "1",
                "pagesize": "1",
                "brandid": str(brand_id),
                "seriesid": str(series_id),
                "pvareaid": "111478",
                "scene_no": "12",
            }

            raw_response = await self._make_request(
                CHE168_SEARCH_API,
                "/api/v11/search",
                params,
                endpoint_type="search"
            )

            if raw_response.get("returncode") != 0:
                return {
                    "returncode": raw_response.get("returncode", -1),
                    "message": raw_response.get('message', 'Unknown error'),
                    "result": {},
                    "success": False
                }

            result = self.parser.parse_car_search_response(raw_response)

            # Extract years from filters array
            years = []
            if result.get("result", {}).get("filters"):
                for filter_item in result["result"]["filters"]:
                    if filter_item.get("key") == "seriesyearid":
                        years.append({
                            "id": int(filter_item.get("value", 0)),
                            "name": filter_item.get("title", ""),
                            "value": filter_item.get("value", ""),
                            "title": filter_item.get("title", ""),
                        })

            # Add years to result
            if "result" in result and isinstance(result["result"], dict):
                result["result"]["years"] = years

            # Cache successful results
            if result.get("success"):
                self.cache.set(cache_key, result, expire=CACHE_TTL_YEARS)

            logger.info(f"✅ Successfully fetched {len(years)} years for brand {brand_id}, series {series_id}")
            return result

        except Exception as e:
            logger.error(f"❌ Error in get_years for brand {brand_id}, series {series_id}: {str(e)}")
            return {
                "returncode": 1,
                "message": f"Service error: {str(e)}",
                "result": {},
                "success": False
            }

    async def get_car_detail(self, info_id: int) -> Dict[str, Any]:
        """Get detailed information for a specific car"""
        try:
            # Check cache first
            cache_key = self._get_cache_key("car_detail", {"info_id": info_id})
            cached = self.cache.get(cache_key)
            if cached:
                logger.debug(f"📋 Cache hit for car detail: info_id={info_id}")
                return cached

            # Fetch car info and params in parallel
            car_info_task = self.get_car_info(info_id)
            car_params_task = self.get_car_params(info_id)

            car_info_response, car_params_response = await asyncio.gather(
                car_info_task,
                car_params_task,
                return_exceptions=True
            )

            # Handle exceptions
            if isinstance(car_info_response, Exception):
                logger.error(f"❌ Error fetching car info for {info_id}: {str(car_info_response)}")
                return {
                    "returncode": 1,
                    "message": f"Failed to fetch car info: {str(car_info_response)}",
                    "result": {
                        "infoid": info_id,
                        "title": None,
                        "price": None,
                        "year": None,
                        "mileage": None,
                        "location": None,
                        "images": [],
                        "description": "",
                        "params": {},
                        "seller_info": {}
                    }
                }

            if isinstance(car_params_response, Exception):
                logger.error(f"❌ Error fetching car params for {info_id}: {str(car_params_response)}")
                car_params_response = {
                    "returncode": 0,
                    "message": "Params not available",
                    "result": []
                }

            # Check if car info is valid
            if car_info_response.get("returncode") != 0:
                return {
                    "returncode": 1,
                    "message": car_info_response.get("message", "Car info not found"),
                    "sold": car_info_response.get("sold", False),
                    "result": {
                        "infoid": info_id,
                        "title": None,
                        "price": None,
                        "year": None,
                        "mileage": None,
                        "location": None,
                        "images": [],
                        "description": "",
                        "params": {},
                        "seller_info": {}
                    }
                }

            # Build car object from car_info data
            info_data = car_info_response.get("result", {})
            if info_data:
                pic_list = info_data.get('picList', [])
                image_url = pic_list[0] if pic_list else info_data.get('imageurl', '')

                car_object = {
                    "infoid": info_data.get('infoid', info_id),
                    "carname": info_data.get('carname', ''),
                    "cname": info_data.get('cname', ''),
                    "dealerid": info_data.get('dealerid', 0),
                    "mileage": str(info_data.get('mileage', '')),
                    "cityid": info_data.get('cityid', 0),
                    "seriesid": info_data.get('seriesid', 0),
                    "specid": info_data.get('specid', 0),
                    "sname": info_data.get('sname', ''),
                    "syname": info_data.get('syname', ''),
                    "price": str(info_data.get('price', '')),
                    "saveprice": str(info_data.get('saveprice', '')),
                    "discount": str(info_data.get('discount', '')),
                    "firstregyear": str(info_data.get('firstregyear', '')),
                    "imageurl": image_url,
                    "displacement": info_data.get('displacement', ''),
                    "environmental": info_data.get('environmental', ''),
                    "brandname": info_data.get('brandname', ''),
                    "seriesname": info_data.get('seriesname', ''),
                    "countyname": info_data.get('countyname', ''),
                    "firstregdate": info_data.get('firstregdate', ''),
                    "picList": pic_list,
                    "gearbox": info_data.get('gearbox', ''),
                    "colorname": info_data.get('colorname', ''),
                    "transfercount": info_data.get('transfercount', 0),
                    "remark": info_data.get('remark', ''),
                    "guidanceprice": info_data.get('guidanceprice', 0),
                    "engine": info_data.get('engine', ''),
                    "vincode": info_data.get('vincode', ''),
                }

                # Add parameter sections
                param_sections = []
                if car_params_response.get("returncode") == 0 and car_params_response.get("result"):
                    param_sections = car_params_response["result"]

                result = {
                    "returncode": 0,
                    "message": "Success",
                    "result": {
                        **car_object,
                        "params": {"params_list": param_sections},
                    }
                }

                # Cache successful results
                self.cache.set(cache_key, result, expire=CACHE_TTL_CAR_DETAIL)

                return result
            else:
                return {
                    "returncode": 1,
                    "message": "No car details found",
                    "result": {
                        "infoid": info_id,
                        "title": None,
                        "price": None,
                        "year": None,
                        "mileage": None,
                        "location": None,
                        "images": [],
                        "description": "",
                        "params": {},
                        "seller_info": {}
                    }
                }

        except Exception as e:
            logger.error(f"❌ Error in get_car_detail for {info_id}: {str(e)}")
            return {
                "returncode": 1,
                "message": f"Service error: {str(e)}",
                "result": {
                    "infoid": info_id,
                    "title": None,
                    "price": None,
                    "year": None,
                    "mileage": None,
                    "location": None,
                    "images": [],
                    "description": "",
                    "params": {},
                    "seller_info": {}
                }
            }

    async def get_car_info(self, info_id: int) -> Dict[str, Any]:
        """Get basic car information using Che168 getcarinfo API"""
        try:
            params = {
                "infoid": str(info_id),
                "_appid": "2sc.m"
            }

            json_data = await self._make_request(
                CHE168_DETAIL_API,
                "/apic/v2/car/getcarinfo",
                params,
                endpoint_type="detail"
            )

            if json_data.get("returncode") == 0 and "result" in json_data:
                return {
                    "returncode": json_data.get("returncode", 0),
                    "message": json_data.get("message", "Success"),
                    "result": json_data["result"]
                }
            else:
                original_message = json_data.get("message", "Failed to get car info")
                is_sold = self._is_sold_car_response(original_message)
                if is_sold:
                    self.sold_registry.mark_sold(info_id, source="car_info", message=original_message)
                return {
                    "returncode": json_data.get("returncode", -1),
                    "message": original_message,
                    "sold": is_sold,
                    "result": {}
                }

        except Exception as e:
            logger.error(f"❌ Error in get_car_info for {info_id}: {str(e)}")
            return {
                "returncode": -1,
                "message": f"Service error: {str(e)}",
                "sold": False,
                "result": {}
            }

    async def get_car_params(self, info_id: int) -> Dict[str, Any]:
        """Get detailed car parameters using Che168 getparamtypeitems API"""
        try:
            params = {
                "infoid": str(info_id),
                "_appid": "2sc.m"
            }

            json_data = await self._make_request(
                CHE168_DETAIL_API,
                "/api/v1/car/getparamtypeitems",
                params,
                endpoint_type="detail"
            )

            if json_data.get("returncode") == 0 and "result" in json_data:
                return {
                    "returncode": json_data.get("returncode", 0),
                    "message": json_data.get("message", "Success"),
                    "result": json_data["result"]
                }
            else:
                original_message = json_data.get("message", "Failed to get car params")
                is_sold = self._is_sold_car_response(original_message)
                if is_sold:
                    self.sold_registry.mark_sold(info_id, source="car_params", message=original_message)
                return {
                    "returncode": json_data.get("returncode", -1),
                    "message": original_message,
                    "sold": is_sold,
                    "result": []
                }

        except Exception as e:
            logger.error(f"❌ Error in get_car_params for {info_id}: {str(e)}")
            return {
                "returncode": -1,
                "message": f"Service error: {str(e)}",
                "sold": False,
                "result": []
            }

    async def get_car_analysis(self, info_id: int) -> Dict[str, Any]:
        """Get car analysis and evaluation (placeholder)"""
        logger.info(f"Car analysis not available for {info_id} - endpoint does not exist")
        return {
            "returncode": 0,
            "message": "Analysis data not available for this vehicle",
            "result": {}
        }

    async def get_filters(self) -> Dict[str, Any]:
        """Get available filter options"""
        try:
            brands_result = await self.get_brands()

            if brands_result.get("returncode") != 0:
                return {
                    "success": False,
                    "brands": [],
                    "price_ranges": [],
                    "age_ranges": [],
                    "mileage_ranges": [],
                    "fuel_types": [],
                    "transmissions": [],
                    "displacements": []
                }

            all_brands = []
            result_data = brands_result.get("result", {})
            for brand_group in result_data.values():
                if isinstance(brand_group, list):
                    all_brands.extend(brand_group)

            return self.parser.create_filters_response(all_brands)

        except Exception as e:
            logger.error(f"❌ Error in get_filters: {str(e)}")
            return {
                "success": False,
                "brands": [],
                "price_ranges": [],
                "age_ranges": [],
                "mileage_ranges": [],
                "fuel_types": [],
                "transmissions": [],
                "displacements": []
            }

    def get_session_info(self) -> Dict[str, Any]:
        """Get current session information including cache statistics"""
        circuit_breaker_statuses = {
            name: cb.get_status()
            for name, cb in self.circuit_breakers.items()
        }

        session_time_remaining = 0
        if self._session_initialized:
            elapsed = time.time() - self._last_session_time
            session_time_remaining = max(0, int(self._session_ttl - elapsed))

        return {
            "api_mode": "direct",
            "search_api": CHE168_SEARCH_API,
            "detail_api": CHE168_DETAIL_API,
            "request_count": self.request_count,
            "last_request": self.last_request_time,
            "proxy_enabled": self.proxy_client is not None,
            "header_mode": "mobile" if self.use_mobile_headers else "desktop",
            "cache_stats": {
                "size": len(self.cache),
                "volume": self.cache.volume(),
            },
            "session_bootstrap": {
                "initialized": self._session_initialized,
                "valid": self._is_session_valid(),
                "time_remaining_seconds": session_time_remaining,
                "device_id": self._device_id[:8] + "...",
                "cookies_count": len(self._session_cookies) if self._session_cookies else 0,
                "signature_errors": self._signature_error_count,
                "using_static_fallback": self._signature_error_count >= self._max_signature_errors,
            },
            "circuit_breakers": circuit_breaker_statuses,
            "circuit_breaker": {
                "failures": self.circuit_breaker_failures,
                "is_open": any(cb.state == "open" for cb in self.circuit_breakers.values()),
                "cooldown_remaining": 0
            },
            "static_fallback_available": {
                "brands": (STATIC_CACHE_DIR / "brands.json").exists(),
                "search": (STATIC_CACHE_DIR / "cars.json").exists(),
            }
        }

    def clear_cache(self):
        """Clear all cached data"""
        self.cache.clear()
        logger.info("🗑️ Cache cleared")

    def reset_circuit_breakers(self):
        """Reset all circuit breakers to closed state"""
        for name, cb in self.circuit_breakers.items():
            cb.failures = 0
            cb.state = "closed"
            cb.last_failure = 0
        self.circuit_breaker_failures = 0
        logger.info("🔄 All circuit breakers reset")

    def reset_session(self):
        """Reset session state to force re-bootstrap"""
        self._session_initialized = False
        self._session_cookies = None
        self._last_session_time = 0
        self._signature_error_count = 0
        logger.info("🔄 Session state reset - will re-bootstrap on next request")

    def reset_all(self):
        """Reset all state: circuit breakers, session, and signature errors"""
        self.reset_circuit_breakers()
        self.reset_session()
        self.clear_cache()
        logger.info("🔄 All service state reset")

    def health_check(self) -> Dict[str, Any]:
        """Health check for the service"""
        return {
            "returncode": 0,
            "message": "Health check completed",
            "result": {
                "status": "healthy",
                "api_mode": "direct",
                "proxy_enabled": self.proxy_client is not None,
                "request_count": self.request_count,
                "cache_size": len(self.cache),
                "session_initialized": self._session_initialized,
                "circuit_breaker_open": any(cb.state == "open" for cb in self.circuit_breakers.values()),
                "static_fallback_available": {
                    "brands": (STATIC_CACHE_DIR / "brands.json").exists(),
                    "search": (STATIC_CACHE_DIR / "cars.json").exists(),
                }
            }
        }
