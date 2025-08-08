import re
import json
from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup
import logging

from schemas.kcar import KCarParsedCar

logger = logging.getLogger(__name__)


class KCarHTMLParser:
    """Parser for KCar HTML responses"""
    
    @staticmethod
    def extract_nuxt_data(html: str) -> Optional[Dict[str, Any]]:
        """Extract NUXT data from HTML page"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Find the NUXT data script tag
            script_tags = soup.find_all('script')
            for script in script_tags:
                if script.string and 'window.__NUXT__' in script.string:
                    # Extract the JSON data
                    match = re.search(r'window\.__NUXT__\s*=\s*({.*?});', script.string, re.DOTALL)
                    if match:
                        # The NUXT data is a JavaScript object, not pure JSON
                        # We need to parse it carefully
                        nuxt_data_str = match.group(1)
                        # This is a simplified approach - in production you might need a JS parser
                        return None  # For now, we'll parse the HTML directly
            return None
        except Exception as e:
            logger.error(f"Error extracting NUXT data: {e}")
            return None
    
    @staticmethod
    def parse_search_results(html: str) -> List[KCarParsedCar]:
        """Parse search results from HTML"""
        cars = []
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Find car listings - KCar uses specific class names for car cards
            car_cards = soup.find_all('div', class_='car-item') or \
                       soup.find_all('article', class_='car-card') or \
                       soup.find_all('div', {'data-car-id': True})
            
            # If no car cards found, try to find by common patterns
            if not car_cards:
                # Look for elements with car-related classes
                car_cards = soup.find_all('div', class_=re.compile(r'car|vehicle|listing'))
            
            for card in car_cards:
                try:
                    car = KCarHTMLParser._parse_car_card(card)
                    if car:
                        cars.append(car)
                except Exception as e:
                    logger.warning(f"Error parsing car card: {e}")
                    continue
                    
            # If no cars found using card method, try extracting from script data
            if not cars:
                cars = KCarHTMLParser._extract_from_script_data(soup)
                
        except Exception as e:
            logger.error(f"Error parsing search results: {e}")
            
        return cars
    
    @staticmethod
    def _parse_car_card(card_element) -> Optional[KCarParsedCar]:
        """Parse individual car card element"""
        try:
            # Extract car ID
            car_id = card_element.get('data-car-id') or \
                    card_element.get('id') or \
                    KCarHTMLParser._extract_from_link(card_element)
            
            if not car_id:
                return None
            
            # Extract title/name
            title_elem = card_element.find(['h2', 'h3', 'h4'], class_=re.compile(r'title|name'))
            if not title_elem:
                title_elem = card_element.find('a', class_=re.compile(r'title|name'))
            
            title = title_elem.get_text(strip=True) if title_elem else ""
            
            # Parse title to extract manufacturer, model, etc.
            car_info = KCarHTMLParser._parse_car_title(title)
            
            # Extract price
            price_elem = card_element.find(class_=re.compile(r'price'))
            price = KCarHTMLParser._extract_price(price_elem.get_text(strip=True) if price_elem else "0")
            
            # Extract year
            year_elem = card_element.find(class_=re.compile(r'year'))
            year = KCarHTMLParser._extract_year(year_elem.get_text(strip=True) if year_elem else "")
            
            # Extract mileage
            mileage_elem = card_element.find(class_=re.compile(r'mileage|km'))
            mileage = KCarHTMLParser._extract_mileage(mileage_elem.get_text(strip=True) if mileage_elem else "0")
            
            # Extract fuel type
            fuel_elem = card_element.find(class_=re.compile(r'fuel'))
            fuel_type = fuel_elem.get_text(strip=True) if fuel_elem else "가솔린"
            
            # Extract transmission
            trans_elem = card_element.find(class_=re.compile(r'trans|mission'))
            transmission = trans_elem.get_text(strip=True) if trans_elem else "오토"
            
            # Extract accident status
            accident_elem = card_element.find(class_=re.compile(r'accident|history'))
            accident_status = accident_elem.get_text(strip=True) if accident_elem else "무사고"
            
            # Extract image URL
            img_elem = card_element.find('img')
            image_url = None
            if img_elem:
                image_url = img_elem.get('src') or img_elem.get('data-src')
                if image_url and not image_url.startswith('http'):
                    image_url = f"https://www.kcar.com{image_url}"
            
            # Extract location
            location_elem = card_element.find(class_=re.compile(r'location|center'))
            seller_location = location_elem.get_text(strip=True) if location_elem else "서울"
            
            # Extract car number
            car_number_elem = card_element.find(class_=re.compile(r'number|plate'))
            car_number = car_number_elem.get_text(strip=True) if car_number_elem else None
            
            # Extract description
            desc_elem = card_element.find(class_=re.compile(r'desc|comment'))
            description = desc_elem.get_text(strip=True) if desc_elem else None
            
            return KCarParsedCar(
                id=car_id,
                manufacturer=car_info.get('manufacturer', '현대'),
                model_group=car_info.get('model_group', ''),
                model=car_info.get('model', ''),
                grade=car_info.get('grade', ''),
                grade_detail=car_info.get('grade_detail'),
                year=year,
                mileage=mileage,
                price=price,
                fuel_type=fuel_type,
                transmission=transmission,
                accident_status=accident_status,
                image_url=image_url,
                seller_location=seller_location,
                car_number=car_number,
                description=description
            )
            
        except Exception as e:
            logger.warning(f"Error parsing car card: {e}")
            return None
    
    @staticmethod
    def _extract_from_script_data(soup: BeautifulSoup) -> List[KCarParsedCar]:
        """Extract car data from script tags"""
        cars = []
        try:
            # Look for script tags containing car data
            script_tags = soup.find_all('script', type='application/json')
            for script in script_tags:
                try:
                    data = json.loads(script.string)
                    # Check if this contains car data
                    if isinstance(data, dict):
                        # Look for car list in various possible locations
                        car_list = data.get('cars') or \
                                  data.get('items') or \
                                  data.get('data', {}).get('rows') or \
                                  data.get('results')
                        
                        if car_list and isinstance(car_list, list):
                            for car_data in car_list:
                                car = KCarHTMLParser._parse_json_car(car_data)
                                if car:
                                    cars.append(car)
                except:
                    continue
        except Exception as e:
            logger.warning(f"Error extracting from script data: {e}")
        
        return cars
    
    @staticmethod
    def _parse_json_car(car_data: Dict) -> Optional[KCarParsedCar]:
        """Parse car from JSON data"""
        try:
            # Map KCar JSON fields to our model
            return KCarParsedCar(
                id=car_data.get('carCd', ''),
                manufacturer=car_data.get('mnuftrNm', ''),
                model_group=car_data.get('modelGrpNm', ''),
                model=car_data.get('modelNm', ''),
                grade=car_data.get('grdNm', ''),
                grade_detail=car_data.get('grdDtlNm'),
                year=int(car_data.get('prdcnYr', 0)),
                mileage=int(car_data.get('milg', 0)),
                price=int(car_data.get('prc', 0)),
                fuel_type=car_data.get('fuelNm', '가솔린'),
                transmission=car_data.get('trnsmsnNm', '오토'),
                accident_status=car_data.get('acdtHistCnts', '무사고'),
                image_url=car_data.get('lsizeImgPath'),
                seller_location=car_data.get('cntrNm', ''),
                car_number=car_data.get('cno'),
                description=car_data.get('simcDesc')
            )
        except Exception as e:
            logger.warning(f"Error parsing JSON car: {e}")
            return None
    
    @staticmethod
    def _parse_car_title(title: str) -> Dict[str, str]:
        """Parse car title to extract components"""
        info = {
            'manufacturer': '',
            'model_group': '',
            'model': '',
            'grade': '',
            'grade_detail': None
        }
        
        # Common patterns for Korean car titles
        # Example: "현대 그랜저 (GN7) 가솔린 3.5 2WD 캘리그래피"
        parts = title.split()
        
        if len(parts) > 0:
            info['manufacturer'] = parts[0]
        if len(parts) > 1:
            info['model_group'] = parts[1]
        if len(parts) > 2:
            # Skip parts in parentheses
            remaining = []
            for part in parts[2:]:
                if not (part.startswith('(') and part.endswith(')')):
                    remaining.append(part)
            
            if remaining:
                info['model'] = remaining[0] if remaining else ''
                if len(remaining) > 1:
                    info['grade'] = ' '.join(remaining[1:3]) if len(remaining) > 2 else remaining[1]
                if len(remaining) > 3:
                    info['grade_detail'] = remaining[-1]
        
        return info
    
    @staticmethod
    def _extract_price(price_str: str) -> int:
        """Extract price from string (returns in 만원)"""
        try:
            # Remove all non-numeric characters
            price_clean = re.sub(r'[^\d]', '', price_str)
            if price_clean:
                price = int(price_clean)
                # If price is too large, it might be in won, convert to 만원
                if price > 100000:
                    price = price // 10000
                return price
        except:
            pass
        return 0
    
    @staticmethod
    def _extract_year(year_str: str) -> int:
        """Extract year from string"""
        try:
            # Look for 4-digit year
            match = re.search(r'20\d{2}', year_str)
            if match:
                return int(match.group())
            # Look for 2-digit year
            match = re.search(r'\d{2}년', year_str)
            if match:
                year = int(match.group()[:2])
                return 2000 + year if year < 50 else 1900 + year
        except:
            pass
        return 2020  # Default year
    
    @staticmethod
    def _extract_mileage(mileage_str: str) -> int:
        """Extract mileage from string (returns in km)"""
        try:
            # Remove all non-numeric characters
            mileage_clean = re.sub(r'[^\d]', '', mileage_str)
            if mileage_clean:
                return int(mileage_clean)
        except:
            pass
        return 0
    
    @staticmethod
    def _extract_from_link(element) -> Optional[str]:
        """Extract car ID from link"""
        try:
            link = element.find('a', href=True)
            if link:
                href = link['href']
                # Extract ID from URL pattern
                match = re.search(r'/car/(\w+)', href)
                if match:
                    return match.group(1)
        except:
            pass
        return None