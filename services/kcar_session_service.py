import httpx
import json
import logging
import re
from typing import Dict, List, Optional, Any
from bs4 import BeautifulSoup
from urllib.parse import urlencode, quote

logger = logging.getLogger(__name__)


class KCarSessionService:
    """Session-based service for KCar data extraction without browser automation"""
    
    BASE_URL = "https://www.kcar.com"
    API_BASE = "https://api.kcar.com"
    
    def __init__(self):
        self.session: Optional[httpx.AsyncClient] = None
        self.cookies = {}
        self.csrf_token = None
        
    async def initialize(self):
        """Initialize session with proper headers and cookies"""
        
        # Headers that mimic a real browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0'
        }
        
        self.session = httpx.AsyncClient(
            headers=headers,
            timeout=30.0,
            follow_redirects=True,
            verify=False  # Disable SSL verification for testing
        )
        
        try:
            # First, get the main page to establish session
            response = await self.session.get(f"{self.BASE_URL}/bc/search")
            
            # Store cookies
            self.cookies.update(response.cookies)
            
            # Try to extract CSRF token if present
            if response.text:
                soup = BeautifulSoup(response.text, 'html.parser')
                csrf_meta = soup.find('meta', {'name': 'csrf-token'})
                if csrf_meta:
                    self.csrf_token = csrf_meta.get('content')
                    
            logger.info("Session initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize session: {e}")
            raise
            
    async def search_cars_html(
        self,
        manufacturer_code: Optional[str] = None,
        model_group_code: Optional[str] = None,
        model_code: Optional[str] = None,
        page_num: int = 1,
        limit: int = 27
    ) -> Dict[str, Any]:
        """Search for cars by parsing HTML directly"""
        
        if not self.session:
            await self.initialize()
            
        try:
            # Build search URL with parameters
            params = {
                'page': str(page_num),
                'limit': str(limit)
            }
            
            # Add search conditions if provided
            search_cond = {}
            if manufacturer_code:
                search_cond['wr_eq_mnuftr_cd'] = manufacturer_code
            if model_group_code:
                search_cond['wr_eq_modelGrp_cd'] = model_group_code
            if model_code:
                search_cond['wr_eq_model_cd'] = model_code
                
            if search_cond:
                params['searchCond'] = json.dumps(search_cond)
                
            url = f"{self.BASE_URL}/bc/search"
            
            # Make request
            response = await self.session.get(url, params=params)
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch search page: {response.status_code}")
                return {
                    "success": False,
                    "data": [],
                    "total": 0,
                    "page": page_num,
                    "limit": limit,
                    "error": f"HTTP {response.status_code}"
                }
                
            # Parse HTML
            cars = self._parse_search_html(response.text)
            
            return {
                "success": True,
                "data": cars[:limit],
                "total": len(cars),
                "page": page_num,
                "limit": limit
            }
            
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
            
    def _parse_search_html(self, html: str) -> List[Dict]:
        """Parse car listings from HTML"""
        soup = BeautifulSoup(html, 'html.parser')
        cars = []
        
        # Look for car listing containers - adjust selectors based on actual HTML structure
        car_elements = soup.find_all(['div', 'li', 'article'], class_=re.compile(
            r'(car|vehicle|listing|item|product|result)', re.I
        ))
        
        for idx, elem in enumerate(car_elements):
            try:
                car_data = self._extract_car_from_element(elem, idx)
                if car_data:
                    cars.append(car_data)
            except Exception as e:
                logger.debug(f"Failed to extract car data: {e}")
                continue
                
        # If no cars found with generic selectors, try specific patterns
        if not cars:
            # Try data attributes
            car_elements = soup.find_all(attrs={'data-car-id': True}) or \
                          soup.find_all(attrs={'data-car-code': True}) or \
                          soup.find_all(attrs={'data-vehicle-id': True})
                          
            for idx, elem in enumerate(car_elements):
                try:
                    car_data = self._extract_car_from_element(elem, idx)
                    if car_data:
                        cars.append(car_data)
                except Exception as e:
                    logger.debug(f"Failed to extract car data: {e}")
                    continue
                    
        # Last resort: look for script tags with JSON data
        if not cars:
            cars = self._extract_from_json_scripts(soup)
            
        return cars
        
    def _extract_car_from_element(self, elem, idx: int) -> Optional[Dict]:
        """Extract car data from HTML element"""
        car_data = {}
        
        # Extract ID
        car_id = elem.get('data-car-id') or \
                elem.get('data-car-code') or \
                elem.get('data-vehicle-id') or \
                f"kcar_{idx}"
                
        car_data['id'] = car_id
        
        # Extract image
        img = elem.find('img')
        if img:
            img_url = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
            if img_url:
                # Make sure URL is absolute
                if not img_url.startswith('http'):
                    img_url = f"{self.BASE_URL}{img_url}"
                car_data['image_url'] = img_url
                
        # Extract title/name
        title_elem = elem.find(['h2', 'h3', 'h4', 'h5'], class_=re.compile(r'(title|name|model)', re.I))
        if not title_elem:
            title_elem = elem.find(['span', 'div'], class_=re.compile(r'(title|name|model)', re.I))
        
        if title_elem:
            title_text = title_elem.get_text(strip=True)
            car_data['title'] = title_text
            
            # Try to parse manufacturer and model from title
            parts = title_text.split()
            if parts:
                car_data['manufacturer'] = parts[0]
                if len(parts) > 1:
                    car_data['model'] = ' '.join(parts[1:3])
                    
        # Extract price
        price_elem = elem.find(text=re.compile(r'\d+[,\d]*\s*만\s*원'))
        if price_elem:
            price_match = re.search(r'(\d+(?:,\d+)*)\s*만\s*원', str(price_elem))
            if price_match:
                car_data['price'] = int(price_match.group(1).replace(',', ''))
        else:
            # Try finding price in class or data attributes
            price_elem = elem.find(class_=re.compile(r'price', re.I))
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                price_match = re.search(r'(\d+(?:,\d+)*)', price_text)
                if price_match:
                    car_data['price'] = int(price_match.group(1).replace(',', ''))
                    
        # Extract year
        year_match = re.search(r'(19|20)\d{2}', elem.get_text())
        if year_match:
            car_data['year'] = int(year_match.group(0))
            
        # Extract mileage
        mileage_match = re.search(r'(\d+(?:,\d+)*)\s*km', elem.get_text(), re.I)
        if mileage_match:
            car_data['mileage'] = int(mileage_match.group(1).replace(',', ''))
            
        # Extract fuel type
        fuel_patterns = ['가솔린', '디젤', '하이브리드', '전기', 'LPG', 'CNG']
        elem_text = elem.get_text()
        for fuel in fuel_patterns:
            if fuel in elem_text:
                car_data['fuel_type'] = fuel
                break
                
        # Default values for missing fields
        car_data.setdefault('manufacturer', '미확인')
        car_data.setdefault('model', '미확인')
        car_data.setdefault('year', 2020)
        car_data.setdefault('price', 0)
        car_data.setdefault('mileage', 0)
        car_data.setdefault('fuel_type', '가솔린')
        car_data.setdefault('transmission', '오토')
        car_data.setdefault('accident_status', '확인필요')
        car_data.setdefault('seller_location', '전국')
        
        return car_data if car_data.get('id') else None
        
    def _extract_from_json_scripts(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract car data from JSON in script tags"""
        cars = []
        
        # Look for script tags with JSON data
        scripts = soup.find_all('script', type=['application/json', 'text/javascript'])
        
        for script in scripts:
            try:
                text = script.string or script.get_text()
                if not text:
                    continue
                    
                # Look for JSON-like structures
                json_matches = re.findall(r'\{[^{}]*"(?:car|vehicle|data|rows|items)"[^{}]*\}', text)
                
                for match in json_matches:
                    try:
                        data = json.loads(match)
                        if isinstance(data, dict):
                            # Process the JSON data
                            if 'rows' in data:
                                for row in data['rows']:
                                    car = self._transform_json_car(row)
                                    if car:
                                        cars.append(car)
                            elif 'items' in data:
                                for item in data['items']:
                                    car = self._transform_json_car(item)
                                    if car:
                                        cars.append(car)
                    except json.JSONDecodeError:
                        continue
                        
            except Exception as e:
                logger.debug(f"Error processing script tag: {e}")
                continue
                
        return cars
        
    def _transform_json_car(self, data: Dict) -> Optional[Dict]:
        """Transform JSON car data to our format"""
        if not isinstance(data, dict):
            return None
            
        return {
            'id': data.get('carCd') or data.get('carId') or data.get('id', f"kcar_{hash(str(data))}"),
            'manufacturer': data.get('mnuftrNm') or data.get('manufacturer', '미확인'),
            'model': data.get('modelNm') or data.get('modelGrpNm') or data.get('model', '미확인'),
            'grade': data.get('grdNm', ''),
            'grade_detail': data.get('grdDtlNm', ''),
            'year': int(data.get('prdcnYr') or data.get('year', 2020)),
            'mileage': int(data.get('milg') or data.get('mileage', 0)),
            'price': int(data.get('prc') or data.get('price', 0)),
            'fuel_type': data.get('fuelNm') or data.get('fuelType', '가솔린'),
            'transmission': data.get('trnsmsnNm') or data.get('transmission', '오토'),
            'accident_status': data.get('acdtHistCnts') or data.get('accidentStatus', '확인필요'),
            'image_url': data.get('lsizeImgPath') or data.get('msizeImgPath') or data.get('ssizeImgPath') or data.get('imageUrl'),
            'seller_location': data.get('cntrNm') or data.get('location', '전국'),
            'car_number': data.get('cno') or data.get('carNumber', ''),
            'description': data.get('simcDesc') or data.get('description', '')
        }
        
    async def cleanup(self):
        """Clean up session resources"""
        if self.session:
            await self.session.aclose()
            self.session = None
            
        logger.info("Session cleanup completed")