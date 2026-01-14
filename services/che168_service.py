"""
Che168 Service - BravoMotors Proxy Implementation
Business logic layer for Chinese car marketplace integration via bravomotorrs.com proxy
"""

import asyncio
import hashlib
import json
import logging
import time
import random
from typing import Dict, Any, Optional, List
from urllib.parse import urlencode, quote
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from requests.exceptions import RequestException, Timeout, ConnectionError
from diskcache import Cache

from parsers.che168_parser import Che168Parser

logger = logging.getLogger(__name__)

# BravoMotors Proxy Configuration
BRAVOMOTORS_PROXY_URL = "https://bravomotorrs.com/api/che168/data"

# Che168 API Base URLs (used to construct proxy URLs)
CHE168_SEARCH_API = "https://api2scsou.che168.com"
CHE168_DETAIL_API = "https://apiuscdt.che168.com"

# Cache TTLs (in seconds)
CACHE_TTL_BRANDS = 3600      # 1 hour
CACHE_TTL_MODELS = 1800      # 30 minutes
CACHE_TTL_YEARS = 1800       # 30 minutes
CACHE_TTL_SEARCH = 300       # 5 minutes
CACHE_TTL_CAR_DETAIL = 600   # 10 minutes


class Che168Service:
    """
    Che168 service for Chinese car marketplace integration via BravoMotors proxy

    Routes all requests through bravomotorrs.com/api/che168/data which handles:
    - Request forwarding to che168.com
    - Authentication and session management
    - Rate limiting and anti-bot measures

    Provides comprehensive functionality for:
    - Car search with filters and pagination
    - Individual car detail retrieval
    - Brand/model/year cascading filters
    - Disk-based caching for performance
    """

    def __init__(self, proxy_client=None):
        self.proxy_client = proxy_client  # Not used with BravoMotors proxy
        self.parser = Che168Parser()

        # Session management
        self.session = requests.Session()

        # Rate limiting
        self.last_request_time = 0
        self.request_count = 0

        # Disk-based cache
        self.cache = Cache('/tmp/che168_cache')

        # Circuit breaker state
        self.circuit_breaker_failures = 0
        self.circuit_breaker_last_reset = time.time()
        self.circuit_breaker_cooldown_until = 0

        # Setup session
        self._setup_session()

    def _setup_session(self):
        """Setup session with BravoMotors proxy requirements"""
        # Headers matching the BravoMotors proxy pattern
        self.session.headers.update({
            'accept': 'application/json',
            'accept-language': 'en,ru;q=0.9,en-CA;q=0.8,la;q=0.7,fr;q=0.6,ko;q=0.5',
            'content-type': 'application/json',
            'priority': 'u=1, i',
            'referer': 'https://bravomotorrs.com/catalog/cn',
            'sec-ch-ua': '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
        })

        # Session configuration
        self.session.timeout = (10, 30)  # connect, read timeout

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

    def _build_proxy_url(self, original_url: str, params: Dict[str, Any] = None) -> str:
        """
        Build bravomotorrs.com proxy URL

        Args:
            original_url: The original che168 API URL (base only, without params)
            params: Query parameters to append

        Returns:
            Proxy URL with encoded che168 URL as parameter
        """
        # Build the full che168 URL with params
        if params:
            param_string = urlencode(params, safe='')
            full_url = f"{original_url}?{param_string}"
        else:
            full_url = original_url

        # URL encode the full che168 URL and wrap with proxy
        encoded_url = quote(full_url, safe='')
        return f"{BRAVOMOTORS_PROXY_URL}?url={encoded_url}"

    def _get_cache_key(self, prefix: str, params: Dict[str, Any] = None) -> str:
        """Generate a cache key from prefix and parameters"""
        if params:
            # Create deterministic hash of params
            param_str = json.dumps(params, sort_keys=True)
            param_hash = hashlib.md5(param_str.encode()).hexdigest()[:12]
            return f"che168:{prefix}:{param_hash}"
        return f"che168:{prefix}"

    async def _rate_limit(self):
        """Rate limiting for BravoMotors proxy (200ms between requests)"""
        current_time = time.time()
        min_interval = 0.2  # 200ms between requests

        if current_time - self.last_request_time < min_interval:
            await asyncio.sleep(min_interval - (current_time - self.last_request_time))

        self.last_request_time = time.time()
        self.request_count += 1

        # Add random delay occasionally to appear more human-like
        if self.request_count % 20 == 0:
            await asyncio.sleep(random.uniform(0.5, 1.5))

    def _check_circuit_breaker(self) -> bool:
        """
        Check if circuit breaker is open (requests should be blocked)

        Returns:
            True if requests are allowed, False if circuit is open
        """
        current_time = time.time()

        # Reset failure counter every 60 seconds
        if current_time - self.circuit_breaker_last_reset > 60:
            self.circuit_breaker_failures = 0
            self.circuit_breaker_last_reset = current_time

        # Check if in cooldown period
        if current_time < self.circuit_breaker_cooldown_until:
            remaining = int(self.circuit_breaker_cooldown_until - current_time)
            logger.warning(f"Circuit breaker is OPEN - cooldown for {remaining}s more")
            return False

        return True

    async def _make_request(
        self,
        base_url: str,
        endpoint_path: str,
        params: Dict = None,
        max_retries: int = 2
    ) -> Dict[str, Any]:
        """
        Make HTTP request through BravoMotors proxy

        Args:
            base_url: Che168 API base URL (e.g., CHE168_SEARCH_API or CHE168_DETAIL_API)
            endpoint_path: API endpoint path (e.g., "/api/v11/search")
            params: Query parameters
            max_retries: Maximum retry attempts

        Returns:
            JSON response data
        """
        await self._rate_limit()

        if params is None:
            params = {}

        # Build the original che168 URL
        original_url = f"{base_url}{endpoint_path}"

        # Build proxy URL
        proxy_url = self._build_proxy_url(original_url, params)

        # Check circuit breaker
        if not self._check_circuit_breaker():
            return {
                "returncode": 503,
                "message": "Service temporarily unavailable (circuit breaker open)",
                "result": {},
            }

        request_start_time = time.time()
        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                logger.debug(f"Making proxy request (attempt {attempt + 1}): {endpoint_path}")
                response = self.session.get(proxy_url, timeout=(10, 30))
                response.raise_for_status()

                # Parse JSON response
                json_data = response.json()

                # Log slow requests
                request_time = time.time() - request_start_time
                if request_time > 5.0:
                    logger.warning(f"Slow request detected: {endpoint_path} took {request_time:.2f}s")

                # Reset circuit breaker on success
                self.circuit_breaker_failures = 0

                return json_data

            except RequestException as e:
                last_exception = e
                status_code = getattr(e.response, 'status_code', None) if hasattr(e, 'response') and e.response else None

                logger.warning(f"Request attempt {attempt + 1}/{max_retries + 1} failed: {str(e)}")

                # Update circuit breaker
                self.circuit_breaker_failures += 1
                if self.circuit_breaker_failures >= 10:
                    self.circuit_breaker_cooldown_until = time.time() + 10
                    logger.error(f"Circuit breaker OPENED - too many failures ({self.circuit_breaker_failures})")

                # Retry with exponential backoff
                if attempt < max_retries:
                    backoff_time = (2 ** attempt) * 0.5 + random.uniform(0, 0.5)
                    logger.info(f"Retrying in {backoff_time:.1f}s...")
                    await asyncio.sleep(backoff_time)
                    continue

                return {
                    "returncode": status_code or 1,
                    "message": f"Request failed: {str(e)}",
                    "result": {},
                }

            except Exception as e:
                logger.error(f"Unexpected error in request: {str(e)}")
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
        """
        Search cars with specified filters

        Args:
            filters: Search filter parameters

        Returns:
            Dictionary with search results
        """
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

            logger.info(f"🔍 Che168 Search: Calling via BravoMotors proxy with params: {list(params.keys())}")

            # Check cache first (only for non-page-1 requests to ensure fresh data on initial load)
            cache_key = self._get_cache_key("search", params)
            pageindex = int(params.get("pageindex", 1))
            if pageindex > 1:
                cached = self.cache.get(cache_key)
                if cached:
                    logger.debug(f"Cache hit for search: {cache_key}")
                    return cached

            # Make request through proxy
            json_data = await self._make_request(
                CHE168_SEARCH_API,
                "/api/v11/search",
                params
            )

            logger.info(f"🔍 Che168 Search: API Response - returncode: {json_data.get('returncode')}, message: {json_data.get('message')}")

            result = self.parser.parse_car_search_response(json_data)

            # Cache successful results
            if result.get("success"):
                self.cache.set(cache_key, result, expire=CACHE_TTL_SEARCH)

            return result

        except Exception as e:
            logger.error(f"Error in search_cars: {str(e)}")
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
        """
        Get all available car brands from Che168

        Returns:
            Dictionary with all available brands
        """
        try:
            # Check cache first
            cache_key = self._get_cache_key("brands")
            cached = self.cache.get(cache_key)
            if cached:
                logger.debug("Cache hit for brands")
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
                params
            )
            result = self.parser.parse_brands_response(json_data)

            # Cache successful results
            if result.get("returncode") == 0:
                self.cache.set(cache_key, result, expire=CACHE_TTL_BRANDS)

            return result

        except Exception as e:
            logger.error(f"Error in get_brands: {str(e)}")
            return {
                "returncode": -1,
                "message": f"Service error: {str(e)}",
                "result": {"hotbrand": [], "brands": []},
                "success": False
            }

    async def get_models(self, brand_id: int) -> Dict[str, Any]:
        """
        Get available models for a specific brand

        Args:
            brand_id: Brand ID to get models for

        Returns:
            Dictionary with search results containing model filters
        """
        try:
            # Check cache first
            cache_key = self._get_cache_key("models", {"brand_id": brand_id})
            cached = self.cache.get(cache_key)
            if cached:
                logger.debug(f"Cache hit for models: brand_id={brand_id}")
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
                params
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

            logger.info(f"Successfully fetched {len(models)} models for brand {brand_id}")
            return result

        except Exception as e:
            logger.error(f"Error in get_models for brand {brand_id}: {str(e)}")
            return {
                "returncode": 1,
                "message": f"Service error: {str(e)}",
                "result": {},
                "success": False
            }

    async def get_years(self, brand_id: int, series_id: int) -> Dict[str, Any]:
        """
        Get available years for a specific brand and model

        Args:
            brand_id: Brand ID
            series_id: Series (model) ID

        Returns:
            Dictionary with search results containing year filters
        """
        try:
            # Check cache first
            cache_key = self._get_cache_key("years", {"brand_id": brand_id, "series_id": series_id})
            cached = self.cache.get(cache_key)
            if cached:
                logger.debug(f"Cache hit for years: brand_id={brand_id}, series_id={series_id}")
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
                params
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

            logger.info(f"Successfully fetched {len(years)} years for brand {brand_id}, series {series_id}")
            return result

        except Exception as e:
            logger.error(f"Error in get_years for brand {brand_id}, series {series_id}: {str(e)}")
            return {
                "returncode": 1,
                "message": f"Service error: {str(e)}",
                "result": {},
                "success": False
            }

    async def get_car_detail(self, info_id: int) -> Dict[str, Any]:
        """
        Get detailed information for a specific car

        Fetches both car info and params in parallel for better performance.

        Args:
            info_id: Car listing ID

        Returns:
            Dictionary with car details
        """
        try:
            # Check cache first
            cache_key = self._get_cache_key("car_detail", {"info_id": info_id})
            cached = self.cache.get(cache_key)
            if cached:
                logger.debug(f"Cache hit for car detail: info_id={info_id}")
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
                logger.error(f"Error fetching car info for {info_id}: {str(car_info_response)}")
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
                logger.error(f"Error fetching car params for {info_id}: {str(car_params_response)}")
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
                # Extract image URLs from picList
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
            logger.error(f"Error in get_car_detail for {info_id}: {str(e)}")
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
        """
        Get basic car information using Che168 getcarinfo API

        Args:
            info_id: Car listing ID

        Returns:
            Dictionary with basic car information
        """
        try:
            params = {
                "infoid": str(info_id),
                "_appid": "2sc.m"
            }

            json_data = await self._make_request(
                CHE168_DETAIL_API,
                "/apic/v2/car/getcarinfo",
                params
            )

            if json_data.get("returncode") == 0 and "result" in json_data:
                return {
                    "returncode": json_data.get("returncode", 0),
                    "message": json_data.get("message", "Success"),
                    "result": json_data["result"]
                }
            else:
                return {
                    "returncode": json_data.get("returncode", -1),
                    "message": json_data.get("message", "Failed to get car info"),
                    "result": {}
                }

        except Exception as e:
            logger.error(f"Error in get_car_info for {info_id}: {str(e)}")
            return {
                "returncode": -1,
                "message": f"Service error: {str(e)}",
                "result": {}
            }

    async def get_car_params(self, info_id: int) -> Dict[str, Any]:
        """
        Get detailed car parameters using Che168 getparamtypeitems API

        Args:
            info_id: Car listing ID

        Returns:
            Dictionary with car specifications
        """
        try:
            params = {
                "infoid": str(info_id),
                "_appid": "2sc.m"
            }

            json_data = await self._make_request(
                CHE168_DETAIL_API,
                "/api/v1/car/getparamtypeitems",
                params
            )

            if json_data.get("returncode") == 0 and "result" in json_data:
                return {
                    "returncode": json_data.get("returncode", 0),
                    "message": json_data.get("message", "Success"),
                    "result": json_data["result"]
                }
            else:
                return {
                    "returncode": json_data.get("returncode", -1),
                    "message": json_data.get("message", "Failed to get car params"),
                    "result": []
                }

        except Exception as e:
            logger.error(f"Error in get_car_params for {info_id}: {str(e)}")
            return {
                "returncode": -1,
                "message": f"Service error: {str(e)}",
                "result": []
            }

    async def get_car_analysis(self, info_id: int) -> Dict[str, Any]:
        """
        Get car analysis and evaluation (placeholder - not available on Che168 API)

        Args:
            info_id: Car listing ID

        Returns:
            Dictionary indicating analysis is not available
        """
        logger.info(f"Car analysis not available for {info_id} - endpoint does not exist")
        return {
            "returncode": 0,
            "message": "Analysis data not available for this vehicle",
            "result": {}
        }

    async def get_filters(self) -> Dict[str, Any]:
        """
        Get available filter options

        Returns:
            Dictionary with available filters
        """
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
            logger.error(f"Error in get_filters: {str(e)}")
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
        return {
            "proxy_url": BRAVOMOTORS_PROXY_URL,
            "request_count": self.request_count,
            "last_request": self.last_request_time,
            "cache_stats": {
                "size": len(self.cache),
                "volume": self.cache.volume(),
            },
            "circuit_breaker": {
                "failures": self.circuit_breaker_failures,
                "is_open": time.time() < self.circuit_breaker_cooldown_until,
                "cooldown_remaining": max(0, int(self.circuit_breaker_cooldown_until - time.time()))
            }
        }

    def clear_cache(self):
        """Clear all cached data"""
        self.cache.clear()
        logger.info("Cache cleared")

    def health_check(self) -> Dict[str, Any]:
        """Health check for the service"""
        return {
            "returncode": 0,
            "message": "Health check completed",
            "result": {
                "status": "healthy",
                "proxy_url": BRAVOMOTORS_PROXY_URL,
                "request_count": self.request_count,
                "cache_size": len(self.cache),
                "circuit_breaker_open": time.time() < self.circuit_breaker_cooldown_until
            }
        }
