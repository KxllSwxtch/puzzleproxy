import asyncio
import json
import logging
from typing import Dict, List, Optional, Any
from playwright.async_api import async_playwright, Browser, Page, Response
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)


class KCarBrowserService:
    """Browser automation service for KCar data extraction"""
    
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context = None
        self.page: Optional[Page] = None
        self.intercepted_data: List[Dict] = []
        
    async def initialize(self):
        """Initialize browser instance"""
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--no-gpu',
                    '--window-size=1920,1080',
                ]
            )
            self.context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                locale='ko-KR'
            )
            self.page = await self.context.new_page()
            
            # Set up response interceptor
            self.page.on('response', self._handle_response)
            
            logger.info("Browser initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}")
            raise
            
    async def _handle_response(self, response: Response):
        """Intercept and capture API responses"""
        try:
            url = response.url
            
            # Capture KCar API responses
            if 'api.kcar.com/bc/search/list' in url:
                if response.status == 200:
                    try:
                        data = await response.json()
                        if data and 'data' in data:
                            logger.info(f"Intercepted KCar API response with {len(data.get('data', {}).get('rows', []))} cars")
                            self.intercepted_data.append(data)
                    except Exception as e:
                        logger.debug(f"Failed to parse response as JSON: {e}")
                        
        except Exception as e:
            logger.debug(f"Error handling response: {e}")
            
    async def search_cars(
        self,
        manufacturer_code: Optional[str] = None,
        model_group_code: Optional[str] = None,
        model_code: Optional[str] = None,
        page_num: int = 1,
        limit: int = 27
    ) -> Dict[str, Any]:
        """Search for cars using browser automation"""
        
        if not self.page:
            await self.initialize()
            
        try:
            # Clear previous intercepted data
            self.intercepted_data = []
            
            # Build search URL
            base_url = "https://www.kcar.com/bc/search"
            search_cond = {}
            
            if manufacturer_code:
                search_cond['wr_eq_mnuftr_cd'] = manufacturer_code
            if model_group_code:
                search_cond['wr_eq_modelGrp_cd'] = model_group_code
            if model_code:
                search_cond['wr_eq_model_cd'] = model_code
                
            # Navigate to search page
            if search_cond:
                url = f"{base_url}?searchCond={json.dumps(search_cond)}"
            else:
                url = base_url
                
            logger.info(f"Navigating to: {url}")
            
            # Navigate and wait for content
            await self.page.goto(url, wait_until='networkidle', timeout=30000)
            
            # Wait for car listings to load
            await self.page.wait_for_selector('.car-list-item, .search-result-item, [class*="car"], [class*="vehicle"]', 
                                             timeout=10000, 
                                             state='visible')
            
            # Try to get intercepted API data first
            if self.intercepted_data:
                logger.info(f"Using intercepted API data: {len(self.intercepted_data)} responses")
                # Return the most recent intercepted data
                api_data = self.intercepted_data[-1]
                return self._transform_api_response(api_data, page_num, limit)
            
            # Fallback to HTML parsing if no API data intercepted
            logger.info("No API data intercepted, parsing HTML")
            return await self._parse_html_listings(page_num, limit)
            
        except Exception as e:
            logger.error(f"Error searching cars: {e}")
            return {
                "success": False,
                "data": [],
                "total": 0,
                "page": page_num,
                "limit": limit,
                "error": str(e)
            }
            
    async def _parse_html_listings(self, page_num: int, limit: int) -> Dict[str, Any]:
        """Parse car listings from HTML"""
        try:
            # Wait for listings container
            listings = await self.page.query_selector_all('.car-item, .vehicle-card, [data-car-id], .list-item')
            
            cars = []
            for listing in listings[:limit]:
                try:
                    car_data = await self._extract_car_from_element(listing)
                    if car_data:
                        cars.append(car_data)
                except Exception as e:
                    logger.debug(f"Failed to extract car data: {e}")
                    continue
                    
            return {
                "success": True,
                "data": cars,
                "total": len(cars),
                "page": page_num,
                "limit": limit
            }
            
        except Exception as e:
            logger.error(f"Error parsing HTML: {e}")
            return {
                "success": False,
                "data": [],
                "total": 0,
                "page": page_num,
                "limit": limit
            }
            
    async def _extract_car_from_element(self, element) -> Optional[Dict]:
        """Extract car data from HTML element"""
        try:
            car_data = {}
            
            # Try to extract car ID
            car_id = await element.get_attribute('data-car-id') or \
                     await element.get_attribute('data-car-code') or \
                     f"kcar_{hash(await element.text_content())}"
            
            car_data['id'] = car_id
            
            # Extract image URL
            img_elem = await element.query_selector('img')
            if img_elem:
                car_data['image_url'] = await img_elem.get_attribute('src') or \
                                        await img_elem.get_attribute('data-src')
                                        
            # Extract text content
            text_content = await element.text_content()
            
            # Try to extract structured data
            title_elem = await element.query_selector('.car-title, .vehicle-name, h3, h4')
            if title_elem:
                title = await title_elem.text_content()
                car_data['title'] = title.strip()
                
            price_elem = await element.query_selector('.price, .car-price, [class*="price"]')
            if price_elem:
                price_text = await price_elem.text_content()
                # Extract numeric price (in 만원)
                import re
                price_match = re.search(r'(\d+(?:,\d+)*)\s*만원', price_text)
                if price_match:
                    car_data['price'] = int(price_match.group(1).replace(',', ''))
                    
            # Extract mileage
            mileage_elem = await element.query_selector('.mileage, [class*="mileage"], [class*="km"]')
            if mileage_elem:
                mileage_text = await mileage_elem.text_content()
                mileage_match = re.search(r'(\d+(?:,\d+)*)\s*km', mileage_text, re.I)
                if mileage_match:
                    car_data['mileage'] = int(mileage_match.group(1).replace(',', ''))
                    
            # Extract year
            year_elem = await element.query_selector('.year, [class*="year"]')
            if year_elem:
                year_text = await year_elem.text_content()
                year_match = re.search(r'(\d{4})', year_text)
                if year_match:
                    car_data['year'] = int(year_match.group(1))
                    
            return car_data if car_data.get('id') else None
            
        except Exception as e:
            logger.debug(f"Error extracting car data: {e}")
            return None
            
    def _transform_api_response(self, api_data: Dict, page_num: int, limit: int) -> Dict:
        """Transform intercepted API response to our format"""
        try:
            rows = api_data.get('data', {}).get('rows', [])
            transformed_cars = []
            
            for row in rows[:limit]:
                car = {
                    'id': row.get('carCd', f"kcar_{len(transformed_cars)}"),
                    'manufacturer': row.get('mnuftrNm', ''),
                    'model_group': row.get('modelGrpNm', ''),
                    'model': row.get('modelNm', ''),
                    'grade': row.get('grdNm', ''),
                    'grade_detail': row.get('grdDtlNm', ''),
                    'year': int(row.get('prdcnYr', 0)),
                    'mileage': int(row.get('milg', 0)),
                    'price': int(row.get('prc', 0)),  # Already in 만원
                    'fuel_type': row.get('fuelNm', ''),
                    'transmission': row.get('trnsmsnNm', ''),
                    'accident_status': row.get('acdtHistCnts', ''),
                    'image_url': row.get('lsizeImgPath') or row.get('msizeImgPath') or row.get('ssizeImgPath'),
                    'seller_location': row.get('cntrNm', ''),
                    'car_number': row.get('cno', ''),
                    'description': row.get('simcDesc', '')
                }
                transformed_cars.append(car)
                
            return {
                "success": True,
                "data": transformed_cars,
                "total": api_data.get('data', {}).get('totalCnt', len(transformed_cars)),
                "page": page_num,
                "limit": limit
            }
            
        except Exception as e:
            logger.error(f"Error transforming API response: {e}")
            return {
                "success": False,
                "data": [],
                "total": 0,
                "page": page_num,
                "limit": limit
            }
            
    async def get_manufacturers(self) -> List[Dict]:
        """Get list of manufacturers"""
        if not self.page:
            await self.initialize()
            
        try:
            # Navigate to search page
            await self.page.goto('https://www.kcar.com/bc/search', wait_until='networkidle')
            
            # Wait for manufacturer dropdown/list
            await self.page.wait_for_selector('[data-manufacturer], .manufacturer-list, select[name*="manufacturer"]', 
                                             timeout=10000)
            
            # Extract manufacturers
            manufacturers = []
            
            # Try select option first
            options = await self.page.query_selector_all('select[name*="manufacturer"] option, [data-manufacturer]')
            for option in options:
                value = await option.get_attribute('value')
                text = await option.text_content()
                if value and text and value != '':
                    manufacturers.append({
                        'mnuftrCd': value,
                        'mnuftrNm': text.strip()
                    })
                    
            return manufacturers
            
        except Exception as e:
            logger.error(f"Error getting manufacturers: {e}")
            return []
            
    async def cleanup(self):
        """Clean up browser resources"""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if hasattr(self, 'playwright'):
                await self.playwright.stop()
                
            logger.info("Browser cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")