"""
Che168 Service
Business logic layer for Chinese car marketplace integration
"""

import json
import logging
import time
import random
import hashlib
from typing import Dict, Any, Optional, List
from urllib.parse import urlencode
import requests
from requests.exceptions import RequestException, Timeout

from parsers.che168_parser import Che168Parser

logger = logging.getLogger(__name__)


class Che168Service:
    """
    Che168 service for Chinese car marketplace integration

    Provides comprehensive functionality for:
    - Car search with filters and pagination
    - Individual car detail retrieval
    - Service filter options
    - Session management with Chinese site requirements
    - Request signing for API authentication
    """

    def __init__(self, proxy_client=None):
        self.proxy_client = proxy_client
        self.parser = Che168Parser()
        self.base_url = "https://api2scsou.che168.com"
        self.mobile_url = "https://m.che168.com"

        # Session management
        self.session = requests.Session()

        # Rate limiting
        self.last_request_time = 0
        self.request_count = 0

        # Cache for session persistence
        self.session_cookies = {}
        self.device_id = "e51c9bd2-efd9-4aaa-b0bd-4f0fd92d9f84"

        # Caches for models and years (30 minute TTL)
        self.models_cache = {}
        self.years_cache = {}

        # Setup session after device_id is defined
        self._setup_session()

    def _setup_session(self):
        """Setup session with Chinese site requirements"""
        # Chinese site specific headers
        self.session.headers.update(
            {
                "accept": "*/*",
                "accept-language": "en,ru;q=0.9,en-CA;q=0.8,la;q=0.7,fr;q=0.6,ko;q=0.5",
                "origin": "https://m.che168.com",
                "priority": "u=1, i",
                "referer": "https://m.che168.com/",
                "sec-ch-ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"macOS"',
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-site",
                "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
            }
        )

        # Set up cookies
        cookies = {
            "fvlid": "175765024666870S5QR2lY0E5",
            "sessionid": self.device_id,
            "sessionip": "1.228.56.78",
            "area": "0",
            "che_sessionid": "65845ADD-8F0D-498F-A254-8B7B4EC47F01%7C%7C2025-09-12+12%3A10%3A47.942%7C%7Cwww.google.com",
            "Hm_lvt_d381ec2f88158113b9b76f14c497ed48": "1757650247,1757841415",
            "HMACCOUNT": "7D5AA048D6828FA7",
            "userarea": "0",
            "listuserarea": "0",
            "sessionvisit": "0e9b80a5-c2ff-4ba7-baf8-79a0256f24ee",
            "sessionvisitInfo": f"{self.device_id}||0",
            "che_sessionvid": "140239D5-014C-434E-ABFF-82B91E2B6D77",
        }

        for name, value in cookies.items():
            self.session.cookies.set(name, value)

        # Setup proxy if available - but skip for Chinese sites as they may not be compatible
        # Chinese sites like Che168 are often accessible without proxy and may have issues with Korean proxies
        # if self.proxy_client and hasattr(self.proxy_client, 'session') and hasattr(self.proxy_client.session, 'proxies'):
        #     self.session.proxies = self.proxy_client.session.proxies

    def _rate_limit(self):
        """Rate limiting to avoid being blocked"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < 1.0:  # Minimum 1 second between requests
            sleep_time = 1.0 - time_since_last + random.uniform(0.1, 0.3)
            time.sleep(sleep_time)

        self.last_request_time = time.time()
        self.request_count += 1

    def _generate_sign(self, params: Dict[str, Any]) -> str:
        """Generate signature for API requests based on lipanauto implementation"""
        try:
            # Filter and sort parameters (excluding _sign if present)
            filtered_params = {k: v for k, v in params.items() if k != "_sign" and v is not None}
            sorted_params = sorted(filtered_params.items())

            # Create parameter string
            param_string = "&".join([f"{k}={v}" for k, v in sorted_params])

            # Generate MD5 signature
            sign = hashlib.md5(param_string.encode()).hexdigest()
            return sign
        except Exception as e:
            logger.warning(f"Failed to generate sign: {str(e)}")
            # Fallback to example sign from lipanauto
            return "1af9c29a34a656070bfa923b31e570eb"

    def _make_request(
        self, url: str, params: Dict = None, use_proxy: bool = False
    ) -> Dict[str, Any]:
        """
        Make HTTP request with error handling and retry logic

        Args:
            url: Target URL
            params: Query parameters
            use_proxy: Whether to use proxy client

        Returns:
            JSON response data
        """
        self._rate_limit()

        if params is None:
            params = {}

        # Add required parameters
        params.update({
            "deviceid": self.device_id,
            "userid": "0",
            "s_pid": "0",
            "s_cid": "0",
            "_appid": "2sc.m",
            "v": "11.41.5",
        })

        # Generate signature
        params["_sign"] = self._generate_sign(params)

        # Log final parameters being sent to Che168 API
        logger.info(f"🔍 Request: Final params with signature: {list(params.keys())}")
        logger.info(f"🔍 Request: Total param count: {len(params)}, _sign: {params['_sign'][:16]}...")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                if use_proxy and self.proxy_client:
                    # Use proxy client if available
                    response = self.proxy_client.session.get(url, params=params)
                else:
                    # Use regular session
                    response = self.session.get(url, params=params)

                response.raise_for_status()

                # Parse JSON response
                json_data = response.json()
                return json_data

            except RequestException as e:
                logger.warning(f"Request attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_retries - 1:
                    # Exponential backoff
                    await_time = 2 ** attempt
                    time.sleep(await_time + random.uniform(0, 1))
                    continue
                else:
                    return {
                        "returncode": 1,
                        "message": f"Request failed after {max_retries} attempts: {str(e)}",
                        "result": {},
                    }

            except Exception as e:
                logger.error(f"Unexpected error in request: {str(e)}")
                return {
                    "returncode": 1,
                    "message": f"Unexpected error: {str(e)}",
                    "result": {},
                }

    def search_cars(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Search cars with specified filters

        Args:
            filters: Search filter parameters

        Returns:
            Dictionary with search results
        """
        try:
            url = f"{self.base_url}/api/v11/search"

            # Use MINIMAL parameters to isolate issue
            # Only include essential parameters
            params = {
                "pageindex": str(filters.get("pageindex", 1)),
                "pagesize": str(filters.get("pagesize", 20)),
                "pageid": f"{int(time.time())}_4145",
            }

            # Add optional filters only if provided
            if filters.get("brandid"):
                params["brandid"] = str(filters["brandid"])
            if filters.get("seriesid"):
                params["seriesid"] = str(filters["seriesid"])
            if filters.get("seriesyearid"):
                params["seriesyearid"] = str(filters["seriesyearid"])
            if filters.get("specid"):
                params["specid"] = str(filters["specid"])
            if filters.get("sort"):
                params["sort"] = str(filters["sort"])

            # Add service filter if explicitly provided
            if filters.get("service"):
                params["service"] = str(filters["service"])

            logger.info(f"🔍 Service: Calling Che168 API with MINIMAL params (before adding required fields): {list(params.keys())}")
            logger.info(f"🔍 Service: pageindex={params['pageindex']}, pagesize={params['pagesize']}, brandid={params.get('brandid', 'none')}, service={params.get('service', 'none')}")
            logger.info(f"🔍 Service: Full params dict: {params}")

            json_data = self._make_request(url, params)

            # Log the actual request that was made (after _make_request adds required params)
            logger.info(f"🔍 Service: Request completed to: {url}")

            logger.info(f"🔍 Service: API Response - returncode: {json_data.get('returncode')}, message: {json_data.get('message')}")

            result = self.parser.parse_car_search_response(json_data)

            return result

        except Exception as e:
            logger.error(f"Error in search_cars: {str(e)}")
            return {
                "returncode": 1,
                "message": f"Service error: {str(e)}",
                "result": {
                    "list": [],
                    "totalcount": 0,
                    "pageindex": filters.get("pageindex", 1),
                    "pagesize": filters.get("pagesize", 20)
                },
                "success": False
            }

    def get_car_detail(self, info_id: int) -> Dict[str, Any]:
        """
        Get detailed information for a specific car

        Args:
            info_id: Car listing ID

        Returns:
            Dictionary with car details
        """
        try:
            url = f"{self.base_url}/api/v11/carinfo"

            params = {
                "infoid": str(info_id),
                "pageid": f"{int(time.time())}_4145",
            }

            json_data = self._make_request(url, params)
            result = self.parser.parse_car_detail_response(json_data)

            return result

        except Exception as e:
            logger.error(f"Error in get_car_detail: {str(e)}")
            return {
                "returncode": 1,
                "message": f"Service error: {str(e)}",
                "result": {},
                "success": False
            }

    def get_brands(self) -> Dict[str, Any]:
        """Get all available car brands from Che168"""
        try:
            url = f"{self.base_url}/api/v2/getbrands"

            params = {
                "cid": "0",
                "pid": "0",
                "isenergy": "0",
                "s_pid": "0",
                "s_cid": "0",
            }

            json_data = self._make_request(url, params)
            result = self.parser.parse_brands_response(json_data)

            return result

        except Exception as e:
            logger.error(f"Error fetching brands: {str(e)}")
            return {
                "returncode": 1,
                "message": f"Error: {str(e)}",
                "result": {"hotbrand": [], "allbrand": []},
                "success": False
            }

    def get_models(self, brand_id: int) -> Dict[str, Any]:
        """
        Get available models for a specific brand

        Args:
            brand_id: Brand ID to get models for

        Returns:
            Dictionary with search results containing model filters
        """
        try:
            # Check cache first
            cache_key = f"brand_{brand_id}"
            if cache_key in self.models_cache:
                cached_result, cache_time = self.models_cache[cache_key]
                if (time.time() - cache_time) < 1800:  # 30 minutes cache
                    logger.info(f"Using cached models for brand {brand_id}")
                    return cached_result

            # Make search request with brand ID to get models from filters
            url = f"{self.base_url}/api/v11/search"
            params = {
                "pageindex": "1",
                "pagesize": "1",
                "ishideback": "1",
                "brandid": str(brand_id),
                "srecom": "2",
                "personalizedpush": "1",
                "cid": "0",
                "iscxcshowed": "-1",
                "scene_no": "12",
                "pageid": f"{int(time.time())}_4145",
                "existtags": "6",
                "pid": "0",
                "testtype": "X",
                "test102223": "X",
                "testnewcarspecid": "X",
                "test102797": "X",
                "otherstatisticsext": "%7B%22history%22%3A%22%E5%88%97%E8%A1%A8%E9%A1%B5%22%2C%22pvareaid%22%3A%220%22%2C%22eventid%22%3A%22usc_2sc_mc_mclby_cydj_click%22%7D",
                "filtertype": "0",
                "ssnew": "1",
            }

            # Get raw response to extract models from filters
            raw_response = self._make_request(url, params)

            if raw_response.get("returncode") != 0:
                return {
                    "returncode": raw_response.get("returncode", -1),
                    "message": raw_response.get('message', 'Unknown error'),
                    "result": {},
                    "success": False
                }

            # Parse the response with models in filters
            result = self.parser.parse_car_search_response(raw_response)

            # Extract models from filters array for easier frontend consumption
            models = []
            if result.get("result", {}).get("filters"):
                for filter_item in result["result"]["filters"]:
                    # Look for series/model filters (key = "seriesid")
                    if filter_item.get("key") == "seriesid":
                        models.append({
                            "id": int(filter_item.get("value", 0)),
                            "name": filter_item.get("title", ""),
                            "icon": filter_item.get("icon", ""),
                            "tag": filter_item.get("tag", ""),
                            "value": filter_item.get("value", ""),
                            "title": filter_item.get("title", ""),
                            "subtitle": filter_item.get("subtitle", ""),
                        })

            # Add models array to result for frontend compatibility
            if "result" in result and isinstance(result["result"], dict):
                result["result"]["models"] = models
                result["result"]["series"] = models  # Also add as series for backward compatibility

            # Cache the result
            self.models_cache[cache_key] = (result, time.time())

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

    def get_years(self, brand_id: int, series_id: int) -> Dict[str, Any]:
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
            cache_key = f"brand_{brand_id}_series_{series_id}"
            if cache_key in self.years_cache:
                cached_result, cache_time = self.years_cache[cache_key]
                if (time.time() - cache_time) < 1800:  # 30 minutes cache
                    logger.info(f"Using cached years for brand {brand_id}, series {series_id}")
                    return cached_result

            # Make search request with brand and series ID to get years from filters
            url = f"{self.base_url}/api/v11/search"
            params = {
                "pageindex": "1",
                "pagesize": "1",
                "ishideback": "1",
                "brandid": str(brand_id),
                "seriesid": str(series_id),
                "srecom": "2",
                "personalizedpush": "1",
                "cid": "0",
                "iscxcshowed": "-1",
                "scene_no": "12",
                "pageid": f"{int(time.time())}_4375",
                "existtags": "6",
                "pid": "0",
                "testtype": "X",
                "test102223": "X",
                "testnewcarspecid": "X",
                "test102797": "X",
                "otherstatisticsext": "%7B%22history%22%3A%22%E5%88%97%E8%A1%A8%E9%A1%B5%22%2C%22pvareaid%22%3A%220%22%2C%22eventid%22%3A%22usc_2sc_mc_mclby_cydj_click%22%7D",
                "filtertype": "0",
                "ssnew": "1",
            }

            # Get raw response to extract years from filters
            raw_response = self._make_request(url, params)

            if raw_response.get("returncode") != 0:
                return {
                    "returncode": raw_response.get("returncode", -1),
                    "message": raw_response.get('message', 'Unknown error'),
                    "result": {},
                    "success": False
                }

            # Parse the response with years in filters
            result = self.parser.parse_car_search_response(raw_response)

            # Extract years from filters array for easier frontend consumption
            years = []
            if result.get("result", {}).get("filters"):
                for filter_item in result["result"]["filters"]:
                    # Look for year filters (key = "seriesyearid")
                    if filter_item.get("key") == "seriesyearid":
                        years.append({
                            "id": int(filter_item.get("value", 0)),
                            "name": filter_item.get("title", ""),
                            "value": filter_item.get("value", ""),
                            "title": filter_item.get("title", ""),
                            "subtitle": filter_item.get("subtitle", ""),
                        })

            # Add years array to result for frontend compatibility
            if "result" in result and isinstance(result["result"], dict):
                result["result"]["years"] = years

            # Cache the result
            self.years_cache[cache_key] = (result, time.time())

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

    def get_filters(self) -> Dict[str, Any]:
        """Get filter options"""
        try:
            url = f"{self.base_url}/api/v11/filters"

            params = {
                "pageid": f"{int(time.time())}_4145",
            }

            json_data = self._make_request(url, params)
            result = self.parser.parse_filters_response(json_data)

            return result

        except Exception as e:
            logger.error(f"Error fetching filters: {str(e)}")
            return {
                "returncode": 1,
                "message": f"Error: {str(e)}",
                "result": {},
                "success": False
            }

    def health_check(self) -> Dict[str, Any]:
        """Health check for the service"""
        try:
            # Test basic connectivity
            url = f"{self.base_url}/api/v11/filters"
            params = {"pageid": f"{int(time.time())}_4145"}

            response = self.session.get(url, params=params, timeout=10)

            status = "healthy" if response.status_code == 200 else "unhealthy"

            return {
                "returncode": 0,
                "message": "Health check completed",
                "result": {
                    "status": status,
                    "response_code": response.status_code,
                    "request_count": self.request_count,
                    "session_active": bool(self.session.cookies)
                }
            }
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return {
                "returncode": 1,
                "message": f"Health check failed: {str(e)}",
                "result": {"status": "unhealthy"}
            }