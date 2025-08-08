import httpx
import json
import logging
from typing import List, Optional, Dict, Any
from urllib.parse import urlencode

from schemas.kcar import (
    KCarManufacturersResponse,
    KCarModelGroupsResponse,
    KCarModelsResponse,
    KCarGradesResponse,
    KCarGradeDetailsResponse,
    KCarSearchResponse,
    KCarParsedCar,
    KCarSearchFilters
)
from parsers.kcar_parser import KCarHTMLParser
try:
    from services.kcar_browser_service import KCarBrowserService
except ImportError:
    KCarBrowserService = None
from services.kcar_session_service import KCarSessionService

logger = logging.getLogger(__name__)


class KCarService:
    """Service for interacting with KCar API"""
    
    BASE_URL = "https://www.kcar.com"
    API_BASE = "https://api.kcar.com"
    SEARCH_URL = f"{BASE_URL}/bc/search"
    
    # Required headers for KCar API
    HEADERS = {
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Content-Type': 'application/json;charset=UTF-8',
        'Origin': 'https://www.kcar.com',
        'Referer': 'https://www.kcar.com/bc/search',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest'
    }
    
    # Required cookies for API access
    COOKIES = {
        'WMONID': 'Ym5fqoFFUcz',
        'OAX': 'b0llK2eOxOgABqoF',
        '_fbp': 'fb.1.1734259488962.129162157287848337',
        '_fwb': '189bxUF2hGzPgRXXqGjfQ8C.1734259489042',
        '__utmz': '266257884.1734259492.1.1.utmcsr=(direct)|utmccn=(direct)|utmcmd=(none)',
        '__utma': '266257884.1668033477.1734259492.1734259492.1734259492.1',
        '__utmc': '266257884',
        '__utmt': '1',
        '__utmb': '266257884.2.10.1734259492',
        'KCAR_MAIN_NEW_01': '20241215',
        'BSSELCARTYPE': 'null',
        'JSESSIONID': 'VqJa4Cux6Z5O-1wP-vQ-IyC3u4xhxFPXI5hnCH2fEQP6Mjj0Mw7b7MBUBbjQCrOW.cmVhcHBkb21haW4va2Nhci1hcGktcHJkMDI=',
        'PCID': '17342595002625644975755',
        'RC_COLOR': 'V1',
        'RC_RESOLUTION': '1920*1080',
        'hanaopnet': '15bXaA2yxyJH9vJZJOYHJQBT5yIJaAUHpQTxJh9NJhjrx7pYx5QH97prJOzxJjYxxhCTJSQxyJAY5ajaxaCxTybx5AJOqhCrqhIJxhmxJsJT5yQJphJTq7CrJb5h5oJH5jzJxyQa51QxJQyHJyhJ5OzTqhCY9SY1pZQ1JV9H9ZY1pZQ1'
    }
    
    def __init__(self, proxy_client=None, use_browser=False):
        """Initialize KCar service with optional proxy client"""
        self.proxy_client = proxy_client
        self.session = None
        self.use_browser = use_browser and KCarBrowserService is not None
        self.browser_service = None
        self.session_service = None
        
    async def _make_proxy_request(self, url: str) -> Dict:
        """Make request using proxy client if available"""
        if self.proxy_client:
            # Use the proxy client for requests
            result = await self.proxy_client.make_request(url)
            return result
        else:
            # Fallback to direct request
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=self.HEADERS, cookies=self.COOKIES)
                return {
                    "success": response.status_code == 200,
                    "status_code": response.status_code,
                    "text": response.text,
                    "headers": dict(response.headers),
                    "url": url
                }
    
    async def _make_request(
        self,
        method: str,
        url: str,
        json_data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        cookies: Optional[Dict] = None
    ) -> Any:
        """Make HTTP request with error handling"""
        # Merge headers and cookies
        request_headers = {**self.HEADERS, **(headers or {})}
        request_cookies = {**self.COOKIES, **(cookies or {})}
        
        try:
            if method.upper() == "GET" and self.proxy_client:
                # Use proxy client for GET requests
                result = await self.proxy_client.make_request(url)
                if result["success"]:
                    # Try to parse as JSON
                    try:
                        return json.loads(result["text"])
                    except json.JSONDecodeError:
                        return result["text"]
                else:
                    raise Exception(f"Request failed: {result.get('error', 'Unknown error')}")
            else:
                # Use httpx for POST requests or when no proxy
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        json=json_data,
                        params=params,
                        headers=request_headers,
                        cookies=request_cookies
                    )
                    response.raise_for_status()
                    
                    # Check if response is JSON
                    content_type = response.headers.get('content-type', '')
                    if 'application/json' in content_type:
                        return response.json()
                    else:
                        return response.text
                
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Request error: {e}")
            raise
    
    async def get_manufacturers(self) -> KCarManufacturersResponse:
        """Get all manufacturers"""
        url = f"{self.API_BASE}/bc/search/group/mnuftr"
        
        payload = {
            "wr_eq_sell_dcd": "ALL",
            "wr_in_multi_columns": "cntr_rgn_cd|cntr_cd"
        }
        
        data = await self._make_request("POST", url, json_data=payload)
        return KCarManufacturersResponse(**data)
    
    async def get_model_groups(self, manufacturer_code: str) -> KCarModelGroupsResponse:
        """Get model groups for a manufacturer"""
        url = f"{self.API_BASE}/bc/search/group/modelGrp"
        
        payload = {
            "wr_eq_sell_dcd": "ALL",
            "wr_in_multi_columns": "cntr_rgn_cd|cntr_cd",
            "wr_eq_mnuftr_cd": manufacturer_code
        }
        
        data = await self._make_request("POST", url, json_data=payload)
        return KCarModelGroupsResponse(**data)
    
    async def get_models(
        self,
        manufacturer_code: str,
        model_group_code: str
    ) -> KCarModelsResponse:
        """Get models for a model group"""
        url = f"{self.API_BASE}/bc/search/group/model"
        
        payload = {
            "wr_eq_sell_dcd": "ALL",
            "wr_in_multi_columns": "cntr_rgn_cd|cntr_cd",
            "wr_eq_mnuftr_cd": manufacturer_code,
            "wr_eq_model_grp_cd": model_group_code
        }
        
        data = await self._make_request("POST", url, json_data=payload)
        return KCarModelsResponse(**data)
    
    async def get_grades(
        self,
        manufacturer_code: str,
        model_group_code: str,
        model_code: str
    ) -> KCarGradesResponse:
        """Get grades for a model"""
        url = f"{self.API_BASE}/bc/search/group/grd"
        
        payload = {
            "wr_eq_sell_dcd": "ALL",
            "wr_in_multi_columns": "cntr_rgn_cd|cntr_cd",
            "wr_eq_mnuftr_cd": manufacturer_code,
            "wr_eq_model_grp_cd": model_group_code,
            "wr_eq_model_cd": model_code
        }
        
        data = await self._make_request("POST", url, json_data=payload)
        return KCarGradesResponse(**data)
    
    async def get_grade_details(
        self,
        manufacturer_code: str,
        model_group_code: str,
        model_code: str,
        grade_code: str
    ) -> KCarGradeDetailsResponse:
        """Get grade details for a grade"""
        url = f"{self.API_BASE}/bc/search/group/grdDtl"
        
        payload = {
            "wr_eq_sell_dcd": "ALL",
            "wr_in_multi_columns": "cntr_rgn_cd|cntr_cd",
            "wr_eq_mnuftr_cd": manufacturer_code,
            "wr_eq_model_grp_cd": model_group_code,
            "wr_eq_model_cd": model_code,
            "wr_eq_grd_cd": grade_code
        }
        
        data = await self._make_request("POST", url, json_data=payload)
        return KCarGradeDetailsResponse(**data)
    
    async def search_cars_session(
        self,
        filters: KCarSearchFilters,
        page: int = 1,
        limit: int = 27
    ) -> Dict:
        """Search cars using session-based scraping"""
        if not self.session_service:
            self.session_service = KCarSessionService()
            await self.session_service.initialize()
            
        result = await self.session_service.search_cars_html(
            manufacturer_code=filters.mnuftrCd if hasattr(filters, 'mnuftrCd') else None,
            model_group_code=filters.modelGrpCd if hasattr(filters, 'modelGrpCd') else None,
            model_code=filters.modelCd if hasattr(filters, 'modelCd') else None,
            page_num=page,
            limit=limit
        )
        
        return result
    
    async def search_cars_browser(
        self,
        filters: KCarSearchFilters,
        page: int = 1,
        limit: int = 27
    ) -> Dict:
        """Search cars using browser automation"""
        if not self.use_browser or not KCarBrowserService:
            # Fallback to session service
            return await self.search_cars_session(filters, page, limit)
            
        if not self.browser_service:
            self.browser_service = KCarBrowserService()
            await self.browser_service.initialize()
            
        result = await self.browser_service.search_cars(
            manufacturer_code=filters.mnuftrCd if hasattr(filters, 'mnuftrCd') else None,
            model_group_code=filters.modelGrpCd if hasattr(filters, 'modelGrpCd') else None,
            model_code=filters.modelCd if hasattr(filters, 'modelCd') else None,
            page_num=page,
            limit=limit
        )
        
        return result
    
    async def search_cars_html(
        self,
        filters: KCarSearchFilters,
        page: int = 1,
        limit: int = 27
    ) -> List[KCarParsedCar]:
        """Search cars using HTML scraping approach"""
        # Build query parameters
        params = {
            "page": str(page),
            "limit": str(limit),
            "wr_eq_sell_dcd": filters.sell_type or "ALL",
            "wr_in_multi_columns": filters.multi_columns or "cntr_rgn_cd|cntr_cd"
        }
        
        # Add optional filters
        if filters.manufacturer_code:
            params["wr_eq_mnuftr_cd"] = filters.manufacturer_code
        if filters.model_group_code:
            params["wr_eq_model_grp_cd"] = filters.model_group_code
        if filters.model_code:
            params["wr_eq_model_cd"] = filters.model_code
        if filters.grade_code:
            params["wr_eq_grd_cd"] = filters.grade_code
        if filters.grade_detail_code:
            params["wr_eq_grd_dtl_cd"] = filters.grade_detail_code
        
        # Make request for HTML
        url = f"{self.SEARCH_URL}?{urlencode(params)}"
        html_content = await self._make_request("GET", url)
        
        # Parse HTML to extract cars
        if isinstance(html_content, str):
            parser = KCarHTMLParser()
            return parser.parse_search_results(html_content)
        else:
            logger.error("Unexpected response type from KCar search")
            return []
    
    async def search_cars_json(
        self,
        filters: KCarSearchFilters,
        page: int = 1,
        limit: int = 27
    ) -> KCarSearchResponse:
        """
        Search cars using JSON API (Note: payload is encrypted in production)
        This method is included for completeness but may not work without proper encryption
        """
        url = f"{self.API_BASE}/v1/cars"
        
        # This payload structure is known but the actual data needs encryption
        payload = {
            "service": "carListFnc",
            "params": filters.dict(by_alias=True, exclude_none=True),
            "page": page,
            "limit": limit
        }
        
        try:
            data = await self._make_request("POST", url, json_data=payload)
            return KCarSearchResponse(**data)
        except Exception as e:
            logger.error(f"JSON search failed (likely due to encryption): {e}")
            # Fall back to HTML search
            cars = await self.search_cars_html(filters, page, limit)
            return KCarSearchResponse(
                success=True,
                data={"rows": [car.dict() for car in cars]},
                message="Fetched via HTML fallback"
            )
    
    async def get_car_details(self, car_id: str) -> Optional[Dict]:
        """Get detailed information for a specific car"""
        url = f"{self.BASE_URL}/bc/car/{car_id}"
        
        try:
            html_content = await self._make_request("GET", url)
            if isinstance(html_content, str):
                # Parse car details from HTML
                # This would need a dedicated parser for the detail page
                return {"car_id": car_id, "html": html_content[:500]}  # Placeholder
            return None
        except Exception as e:
            logger.error(f"Failed to get car details: {e}")
            return None
    
    async def close(self):
        """Close the HTTP session and browser resources"""
        if self.session:
            await self.session.aclose()
            self.session = None
        if self.browser_service:
            await self.browser_service.cleanup()
            self.browser_service = None
        if self.session_service:
            await self.session_service.cleanup()
            self.session_service = None
    
    async def __aenter__(self):
        """Context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        await self.close()