"""
Encar History Parser
Parser for extracting manufacturing and registration data from Encar history pages
"""

import json
import logging
import re
from typing import Dict, Any, Optional, List
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class EncarHistoryParser:
    """
    Parser for Encar car history data
    
    Extracts manufacturing date, registration date, and other car details
    from Encar's history page HTML response
    """
    
    def __init__(self):
        self.korean_months = {
            '01': '01월', '02': '02월', '03': '03월', '04': '04월',
            '05': '05월', '06': '06월', '07': '07월', '08': '08월',
            '09': '09월', '10': '10월', '11': '11월', '12': '12월'
        }
    
    def extract_manufacturing_date(self, html: str) -> Optional[Dict[str, Any]]:
        """
        Extract manufacturing date from Encar history HTML
        
        Args:
            html: HTML content from Encar history page
            
        Returns:
            Dictionary with manufacturing date information or None if not found
        """
        try:
            # Extract JSON data from HTML
            json_data = self._extract_json_from_html(html)
            if not json_data:
                logger.warning("Could not extract JSON data from HTML")
                return None
            
            # Extract manufacturing date from timeline
            manufacturing_info = self._find_manufacturing_date_in_timeline(json_data)
            if manufacturing_info:
                logger.info(f"Found manufacturing date: {manufacturing_info}")
                return manufacturing_info
            
            # Alternative: try to extract from release info
            release_info = self._extract_from_release_section(json_data)
            if release_info:
                logger.info(f"Found manufacturing date from release info: {release_info}")
                return release_info
            
            logger.warning("Manufacturing date not found in any section")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting manufacturing date: {str(e)}")
            return None
    
    def _extract_json_from_html(self, html: str) -> Optional[Dict[str, Any]]:
        """Extract JSON data from __NEXT_DATA__ script tag"""
        try:
            # Try BeautifulSoup first
            soup = BeautifulSoup(html, 'html.parser')
            script_tag = soup.find('script', {'id': '__NEXT_DATA__'})
            
            if script_tag and script_tag.string:
                return json.loads(script_tag.string)
            
            # Fallback: use regex to find the JSON data directly
            logger.warning("BeautifulSoup failed, trying regex fallback")
            
            import re
            # Look for the script tag with regex
            pattern = r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>'
            match = re.search(pattern, html, re.DOTALL)
            
            if match:
                json_str = match.group(1)
                logger.info("Found __NEXT_DATA__ via regex")
                return json.loads(json_str)
            
            logger.warning("__NEXT_DATA__ script tag not found or empty")
            return None
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from HTML: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error extracting JSON from HTML: {str(e)}")
            return None
    
    def _find_manufacturing_date_in_timeline(self, json_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Find manufacturing date in the timeline events"""
        try:
            timeline = json_data.get('props', {}).get('pageProps', {}).get('uiData', {}).get('timeline', [])
            
            for event in timeline:
                contents = event.get('contents', [])
                for content in contents:
                    layer_data = content.get('layerData', {})
                    content_items = layer_data.get('content', [])
                    
                    # Look for manufacturing date (제작일시)
                    for item in content_items:
                        if item.get('name') == '제작일시':
                            manufacturing_date = item.get('value', '')
                            parsed_date = self._parse_korean_date(manufacturing_date)
                            if parsed_date:
                                # Also look for first registration date in the same content
                                first_reg_date = None
                                for reg_item in content_items:
                                    if reg_item.get('name') == '최초등록일':
                                        first_reg_date = reg_item.get('value', '')
                                        break
                                
                                result = {
                                    'manufacturingDate': parsed_date,
                                    'originalManufacturingDate': manufacturing_date,
                                    'firstRegistrationDate': first_reg_date,
                                    'source': 'timeline'
                                }
                                return result
            
            return None
            
        except Exception as e:
            logger.error(f"Error searching timeline for manufacturing date: {str(e)}")
            return None
    
    def _extract_from_release_section(self, json_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract manufacturing date from release section as fallback"""
        try:
            release_data = json_data.get('props', {}).get('pageProps', {}).get('uiData', {}).get('item', {}).get('release', {})
            
            if release_data:
                release_date = release_data.get('date', '')
                if release_date:
                    parsed_date = self._parse_korean_date(release_date)
                    if parsed_date:
                        return {
                            'manufacturingDate': parsed_date,
                            'originalManufacturingDate': release_date,
                            'firstRegistrationDate': None,
                            'source': 'release'
                        }
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting from release section: {str(e)}")
            return None
    
    def _parse_korean_date(self, date_str: str) -> Optional[Dict[str, str]]:
        """
        Parse Korean date format to standardized format
        
        Args:
            date_str: Korean date string like "2018년 03월 26일" or "2018년 03월"
            
        Returns:
            Dictionary with parsed date components or None if parsing failed
        """
        try:
            if not date_str:
                return None
            
            # Pattern for full date: "2018년 03월 26일"
            full_date_match = re.match(r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일', date_str)
            if full_date_match:
                year, month, day = full_date_match.groups()
                return {
                    'year': year,
                    'month': month.zfill(2),
                    'day': day.zfill(2),
                    'formatted': f"{year}.{month.zfill(2)}",
                    'display': f"{month.zfill(2)}/{year}",
                    'full_date': f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                }
            
            # Pattern for year/month only: "2018년 03월"
            year_month_match = re.match(r'(\d{4})년\s*(\d{1,2})월', date_str)
            if year_month_match:
                year, month = year_month_match.groups()
                return {
                    'year': year,
                    'month': month.zfill(2),
                    'day': None,
                    'formatted': f"{year}.{month.zfill(2)}",
                    'display': f"{month.zfill(2)}/{year}",
                    'full_date': f"{year}-{month.zfill(2)}"
                }
            
            # Pattern for alternative format: "2018/03/26" or "2018/03"
            slash_date_match = re.match(r'(\d{4})/(\d{1,2})(?:/(\d{1,2}))?', date_str)
            if slash_date_match:
                year, month, day = slash_date_match.groups()
                return {
                    'year': year,
                    'month': month.zfill(2),
                    'day': day.zfill(2) if day else None,
                    'formatted': f"{year}.{month.zfill(2)}",
                    'display': f"{month.zfill(2)}/{year}",
                    'full_date': f"{year}-{month.zfill(2)}" + (f"-{day.zfill(2)}" if day else "")
                }
            
            logger.warning(f"Could not parse date string: {date_str}")
            return None
            
        except Exception as e:
            logger.error(f"Error parsing Korean date '{date_str}': {str(e)}")
            return None
    
    def extract_additional_info(self, html: str) -> Dict[str, Any]:
        """
        Extract additional car information from history page
        
        Args:
            html: HTML content from Encar history page
            
        Returns:
            Dictionary with additional car information
        """
        try:
            json_data = self._extract_json_from_html(html)
            if not json_data:
                return {}
            
            intro_data = json_data.get('props', {}).get('pageProps', {}).get('uiData', {}).get('intro', {})
            release_data = json_data.get('props', {}).get('pageProps', {}).get('uiData', {}).get('item', {}).get('release', {})
            
            return {
                'carNumber': intro_data.get('carNum', ''),
                'manufacturer': intro_data.get('manufacturer', ''),
                'carModel': intro_data.get('carModel', ''),
                'carGrade': intro_data.get('carGrade', ''),
                'mileage': intro_data.get('mileage', ''),
                'productionCountry': release_data.get('nation', ''),
                'fuelType': release_data.get('fuel', ''),
                'fixedPrice': release_data.get('fixedPrice', '')
            }
            
        except Exception as e:
            logger.error(f"Error extracting additional info: {str(e)}")
            return {}
    
    def format_date_for_display(self, date_info: Dict[str, str], format_type: str = 'display') -> str:
        """
        Format date information for display
        
        Args:
            date_info: Parsed date information
            format_type: Type of format ('display', 'formatted', 'full_date')
            
        Returns:
            Formatted date string
        """
        if not date_info:
            return "Дата производства недоступна, обращайтесь к менеджеру"
        
        return date_info.get(format_type, date_info.get('formatted', ''))