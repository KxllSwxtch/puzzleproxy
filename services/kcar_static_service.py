import json
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class KCarStaticService:
    """Service for loading KCar data from static JSON file"""
    
    def __init__(self):
        self.cars_data = None
        self.manufacturers = {}
        self.model_groups = {}
        
    def load_data(self):
        """Load cars data from JSON file"""
        try:
            json_path = Path(__file__).parent.parent / 'KCAR' / 'cars.json'
            
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            if data.get('success') and data.get('data'):
                self.cars_data = data['data']['rows']
                self._extract_manufacturers()
                logger.info(f"Loaded {len(self.cars_data)} cars from JSON file")
            else:
                logger.error("Invalid JSON structure")
                self.cars_data = []
                
        except Exception as e:
            logger.error(f"Failed to load cars.json: {e}")
            self.cars_data = []
            
    def _extract_manufacturers(self):
        """Extract unique manufacturers and model groups from data"""
        if not self.cars_data:
            return
            
        for car in self.cars_data:
            mfr_code = car.get('mnuftrCd')
            mfr_name = car.get('mnuftrNm')
            
            if mfr_code and mfr_name:
                self.manufacturers[mfr_code] = mfr_name
                
                # Extract model groups
                model_grp_code = car.get('modelGrpCd')
                model_grp_name = car.get('modelGrpNm')
                
                if model_grp_code and model_grp_name:
                    if mfr_code not in self.model_groups:
                        self.model_groups[mfr_code] = {}
                    self.model_groups[mfr_code][model_grp_code] = model_grp_name
                    
    def search_cars(
        self,
        manufacturer_code: Optional[str] = None,
        model_group_code: Optional[str] = None,
        model_code: Optional[str] = None,
        page: int = 1,
        limit: int = 27
    ) -> Dict[str, Any]:
        """Search cars from static data"""
        
        if not self.cars_data:
            self.load_data()
            
        # Filter cars based on criteria
        filtered_cars = []
        
        for car in self.cars_data:
            # Apply filters
            if manufacturer_code and car.get('mnuftrCd') != manufacturer_code:
                continue
            if model_group_code and car.get('modelGrpCd') != model_group_code:
                continue
            if model_code and car.get('modelCd') != model_code:
                continue
                
            # Transform to our format
            transformed_car = self._transform_car(car)
            filtered_cars.append(transformed_car)
            
        # Apply pagination
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_cars = filtered_cars[start_idx:end_idx]
        
        return {
            "success": True,
            "data": paginated_cars,
            "total": len(filtered_cars),
            "page": page,
            "limit": limit
        }
        
    def _transform_car(self, car: Dict) -> Dict:
        """Transform car data to our standard format"""
        return {
            'id': car.get('carCd', f"kcar_{car.get('cno', '')}"),
            'manufacturer': car.get('mnuftrNm', ''),
            'model_group': car.get('modelGrpNm', ''),
            'model': car.get('modelNm', ''),
            'grade': car.get('grdNm', ''),
            'grade_detail': car.get('grdDtlNm', ''),
            'year': int(car.get('prdcnYr', 0)),
            'mileage': int(car.get('milg', 0)),
            'price': int(car.get('prc', 0)),  # Already in 만원
            'fuel_type': car.get('fuelNm', ''),
            'transmission': car.get('trnsmsnNm', ''),
            'accident_status': car.get('acdtHistCnts', ''),
            # Use real image URLs from KCar
            'image_url': car.get('lsizeImgPath') or car.get('msizeImgPath') or car.get('ssizeImgPath', ''),
            'seller_location': car.get('cntrNm', ''),
            'car_number': car.get('cno', ''),
            'description': car.get('simcDesc', ''),
            # Additional fields
            'engine_displacement': car.get('engdispmnt', ''),
            'passenger_count': car.get('pasngrCnt', ''),
            'car_category': car.get('carctgrNm', ''),
            'options': car.get('optnNm', ''),
            'exterior_color': car.get('extrColorNm', ''),
            'mfg_date': car.get('mfgDt', ''),
            'hot_marks': car.get('hotmarkNm', ''),
            'discount_price': car.get('dcPrc', ''),
            'view_3d': car.get('view3dFg', '2D')
        }
        
    def get_manufacturers(self) -> List[Dict]:
        """Get list of unique manufacturers"""
        if not self.cars_data:
            self.load_data()
            
        return [
            {'mnuftrCd': code, 'mnuftrNm': name}
            for code, name in self.manufacturers.items()
        ]
        
    def get_model_groups(self, manufacturer_code: str) -> List[Dict]:
        """Get model groups for a manufacturer"""
        if not self.cars_data:
            self.load_data()
            
        if manufacturer_code not in self.model_groups:
            return []
            
        return [
            {
                'mnuftrCd': manufacturer_code,
                'modelGrpCd': code,
                'modelGrpNm': name
            }
            for code, name in self.model_groups[manufacturer_code].items()
        ]
        
    def get_car_by_id(self, car_id: str) -> Optional[Dict]:
        """Get a specific car by ID"""
        if not self.cars_data:
            self.load_data()
            
        for car in self.cars_data:
            if car.get('carCd') == car_id:
                return self._transform_car(car)
                
        return None