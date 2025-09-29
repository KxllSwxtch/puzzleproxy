"""
Che168 Parser
Handles JSON parsing for Chinese car marketplace API responses
"""

import json
import logging
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin

from schemas.che168 import (
    Che168SearchResponse,
    Che168CarListing,
    Che168ServiceOption,
    Che168CarDetailResponse,
    Che168FiltersResponse,
    Che168CarTag,
    Che168CarTags,
    Che168CPCInfo,
    Che168Consignment,
    Che168BrandsResponse,
    Che168Brand,
)

logger = logging.getLogger(__name__)


class Che168Parser:
    """
    Comprehensive parser for Che168 API responses
    Handles JSON parsing and data transformation
    """

    def __init__(self):
        self.base_url = "https://api2scsou.che168.com"
        self.parser_name = "che168_json"

    def parse_car_search_response(self, json_data: Dict) -> Dict[str, Any]:
        """
        Parse main API response from Che168 search endpoint

        Args:
            json_data: Raw JSON response from API

        Returns:
            Dictionary with parsed search results
        """
        try:
            if json_data.get("returncode") != 0:
                return {
                    "returncode": json_data.get("returncode", 1),
                    "message": json_data.get("message", "API error"),
                    "result": {
                        "list": [],
                        "totalcount": 0,
                        "pageindex": 1,
                        "pagesize": 20
                    },
                    "success": False
                }

            result = json_data.get("result", {})

            # Parse car listings
            car_listings = []
            for car_data in result.get("carlist", []):
                try:
                    car = self._parse_car_listing(car_data)
                    if car:
                        car_listings.append(car)
                except Exception as e:
                    logger.warning(f"Failed to parse car listing: {str(e)}")
                    continue

            # Parse service filters
            service_filters = []
            for service_data in result.get("service", []):
                try:
                    service = self._parse_service_option(service_data)
                    if service:
                        service_filters.append(service)
                except Exception as e:
                    logger.warning(f"Failed to parse service filter: {str(e)}")
                    continue

            # Build response
            response = {
                "returncode": 0,
                "message": "Success",
                "result": {
                    "list": car_listings,
                    "totalcount": result.get("totalcount", 0),
                    "pageindex": result.get("pageindex", 1),
                    "pagesize": result.get("pagesize", 20),
                    "pagecount": result.get("pagecount", 0),
                    "queryid": result.get("queryid", ""),
                    "service": service_filters,
                },
                "success": True
            }

            logger.info(f"Successfully parsed {len(car_listings)} cars from search response")
            return response

        except Exception as e:
            logger.error(f"Error parsing search response: {str(e)}")
            return {
                "returncode": 1,
                "message": f"Parser error: {str(e)}",
                "result": {
                    "list": [],
                    "totalcount": 0,
                    "pageindex": 1,
                    "pagesize": 20
                },
                "success": False
            }

    def parse_car_detail_response(self, json_data: Dict) -> Dict[str, Any]:
        """
        Parse car detail response

        Args:
            json_data: Raw JSON response from API

        Returns:
            Dictionary with parsed car details
        """
        try:
            if json_data.get("returncode") != 0:
                return {
                    "returncode": json_data.get("returncode", 1),
                    "message": json_data.get("message", "API error"),
                    "result": {},
                    "success": False
                }

            result = json_data.get("result", {})

            return {
                "returncode": 0,
                "message": "Success",
                "result": result,
                "success": True
            }

        except Exception as e:
            logger.error(f"Error parsing car detail response: {str(e)}")
            return {
                "returncode": 1,
                "message": f"Parser error: {str(e)}",
                "result": {},
                "success": False
            }

    def parse_brands_response(self, json_data: Dict) -> Dict[str, Any]:
        """
        Parse brands response

        Args:
            json_data: Raw JSON response from API

        Returns:
            Dictionary with parsed brands
        """
        try:
            if json_data.get("returncode") != 0:
                return {
                    "returncode": json_data.get("returncode", 1),
                    "message": json_data.get("message", "API error"),
                    "result": {"hotbrand": [], "allbrand": []},
                    "success": False
                }

            result = json_data.get("result", {})

            # Parse brands from new getbrands response structure
            hotbrands = []
            allbrands = []

            # Parse hot brands
            for brand_data in result.get("hotbrand", []):
                try:
                    brand = self._parse_brand(brand_data)
                    if brand:
                        hotbrands.append(brand)
                except Exception as e:
                    logger.warning(f"Failed to parse hot brand: {str(e)}")
                    continue

            # Parse all brands
            for brand_data in result.get("allbrand", []):
                try:
                    brand = self._parse_brand(brand_data)
                    if brand:
                        allbrands.append(brand)
                except Exception as e:
                    logger.warning(f"Failed to parse brand: {str(e)}")
                    continue

            return {
                "returncode": 0,
                "message": "Success",
                "result": {
                    "hotbrand": hotbrands,
                    "allbrand": allbrands
                },
                "success": True
            }

        except Exception as e:
            logger.error(f"Error parsing brands response: {str(e)}")
            return {
                "returncode": 1,
                "message": f"Parser error: {str(e)}",
                "result": {"hotbrand": [], "allbrand": []},
                "success": False
            }

    def parse_filters_response(self, json_data: Dict) -> Dict[str, Any]:
        """
        Parse filters response

        Args:
            json_data: Raw JSON response from API

        Returns:
            Dictionary with parsed filters
        """
        try:
            if json_data.get("returncode") != 0:
                return {
                    "returncode": json_data.get("returncode", 1),
                    "message": json_data.get("message", "API error"),
                    "result": {},
                    "success": False
                }

            result = json_data.get("result", {})

            return {
                "returncode": 0,
                "message": "Success",
                "result": result,
                "success": True
            }

        except Exception as e:
            logger.error(f"Error parsing filters response: {str(e)}")
            return {
                "returncode": 1,
                "message": f"Parser error: {str(e)}",
                "result": {},
                "success": False
            }

    def _parse_car_listing(self, car_data: Dict) -> Optional[Dict[str, Any]]:
        """
        Parse individual car listing data

        Args:
            car_data: Raw car data from API

        Returns:
            Parsed car listing dictionary
        """
        try:
            # Extract all fields with proper defaults
            parsed_car = {
                "infoid": car_data.get("infoid", 0),
                "carname": car_data.get("carname", ""),
                "cname": car_data.get("cname", ""),
                "dealerid": car_data.get("dealerid", 0),
                "mileage": car_data.get("mileage", ""),
                "cityid": car_data.get("cityid", 0),
                "seriesid": car_data.get("seriesid", 0),
                "specid": car_data.get("specid", 0),
                "sname": car_data.get("sname", ""),
                "syname": car_data.get("syname", ""),
                "price": car_data.get("price", ""),
                "saveprice": car_data.get("saveprice", ""),
                "discount": car_data.get("discount", ""),
                "firstregyear": car_data.get("firstregyear", ""),
                "fromtype": car_data.get("fromtype", 0),
                "imageurl": car_data.get("imageurl", ""),
                "cartype": car_data.get("cartype", 0),
                "bucket": car_data.get("bucket", 0),
                "isunion": car_data.get("isunion", 0),
                "isoutsite": car_data.get("isoutsite", 0),
                "videourl": car_data.get("videourl", ""),
                "car_level": car_data.get("car_level", 0),
                "dealer_level": car_data.get("dealer_level", ""),
                "downpayment": car_data.get("downpayment", ""),
                "url": car_data.get("url", ""),
                "position": car_data.get("position", 0),
                "isnewly": car_data.get("isnewly", 0),
                "kindname": car_data.get("kindname", ""),
                "usc_adid": car_data.get("usc_adid", 0),
                "particularactivity": car_data.get("particularactivity", 0),
                "livestatus": car_data.get("livestatus", 0),
                "stra": car_data.get("stra", ""),
                "springid": car_data.get("springid", ""),
                "followcount": car_data.get("followcount", 0),
                "cxctype": car_data.get("cxctype", 0),
                "isfqtj": car_data.get("isfqtj", 0),
                "isrelivedbuy": car_data.get("isrelivedbuy", 0),
                "photocount": car_data.get("photocount", 0),
                "isextwarranty": car_data.get("isextwarranty", 0),
                "offertype": car_data.get("offertype", 0),
                "displacement": car_data.get("displacement", ""),
                "environmental": car_data.get("environmental", ""),
                "liveurl": car_data.get("liveurl", ""),
                "imuserid": car_data.get("imuserid", ""),
                "pv_extstr": car_data.get("pv_extstr", ""),
                "act_discount": car_data.get("act_discount", ""),
            }

            # Parse nested objects
            if "cartags" in car_data:
                parsed_car["cartags"] = self._parse_car_tags(car_data["cartags"])

            if "consignment" in car_data:
                parsed_car["consignment"] = self._parse_consignment(car_data["consignment"])

            if "cpcinfo" in car_data:
                parsed_car["cpcinfo"] = self._parse_cpc_info(car_data["cpcinfo"])

            return parsed_car

        except Exception as e:
            logger.error(f"Error parsing car listing: {str(e)}")
            return None

    def _parse_service_option(self, service_data: Dict) -> Optional[Dict[str, Any]]:
        """Parse service option data"""
        try:
            return {
                "title": service_data.get("title", ""),
                "subtitle": service_data.get("subtitle", ""),
                "key": service_data.get("key", ""),
                "value": service_data.get("value", ""),
                "icon": service_data.get("icon", ""),
                "iconfocus": service_data.get("iconfocus", ""),
                "tag": service_data.get("tag", ""),
                "viewtype": service_data.get("viewtype", 0),
                "iconwidth": service_data.get("iconwidth", 0),
                "badgetitle": service_data.get("badgetitle", ""),
                "headbgurl": service_data.get("headbgurl", ""),
                "headsubbgurl": service_data.get("headsubbgurl", ""),
                "titlecolorfocus": service_data.get("titlecolorfocus", ""),
                "titlecolor": service_data.get("titlecolor", ""),
                "tabtype": service_data.get("tabtype", 0),
                "linkurl": service_data.get("linkurl", ""),
                "basevalue": service_data.get("basevalue", ""),
                "dtype": service_data.get("dtype", 0),
                "subvalue": service_data.get("subvalue", ""),
                "subspecname": service_data.get("subspecname", ""),
                "needreddot": service_data.get("needreddot", 0),
                "brandvalue": service_data.get("brandvalue", ""),
                "brandname": service_data.get("brandname", ""),
                "isgray": service_data.get("isgray", 0),
            }
        except Exception as e:
            logger.error(f"Error parsing service option: {str(e)}")
            return None

    def _parse_brand(self, brand_data: Dict) -> Optional[Dict[str, Any]]:
        """Parse brand data"""
        try:
            return {
                "bid": brand_data.get("bid", 0),
                "name": brand_data.get("name", ""),
                "py": brand_data.get("py", ""),
                "icon": brand_data.get("icon", ""),
                "price": brand_data.get("price", ""),
                "on_sale_num": brand_data.get("on_sale_num", 0),
                "dtype": brand_data.get("dtype", 0),
            }
        except Exception as e:
            logger.error(f"Error parsing brand: {str(e)}")
            return None

    def _parse_car_tags(self, tags_data: Dict) -> Dict[str, Any]:
        """Parse car tags data"""
        try:
            return {
                "p1": [self._parse_car_tag(tag) for tag in tags_data.get("p1", [])],
                "p2": [self._parse_car_tag(tag) for tag in tags_data.get("p2", [])],
                "p3": [self._parse_car_tag(tag) for tag in tags_data.get("p3", [])],
            }
        except Exception as e:
            logger.error(f"Error parsing car tags: {str(e)}")
            return {"p1": [], "p2": [], "p3": []}

    def _parse_car_tag(self, tag_data: Dict) -> Dict[str, Any]:
        """Parse individual car tag"""
        return {
            "title": tag_data.get("title", ""),
            "bg_color": tag_data.get("bg_color", ""),
            "bg_color_end": tag_data.get("bg_color_end", ""),
            "font_color": tag_data.get("font_color", ""),
            "border_color": tag_data.get("border_color", ""),
            "bg_color_direction": tag_data.get("bg_color_direction", 0),
            "stype": tag_data.get("stype", ""),
            "sort": tag_data.get("sort", 0),
            "icon": tag_data.get("icon", ""),
            "url": tag_data.get("url", ""),
            "image": tag_data.get("image", ""),
            "imgheight": tag_data.get("imgheight", 0),
            "imgwidth": tag_data.get("imgwidth", 0),
        }

    def _parse_consignment(self, consignment_data: Dict) -> Dict[str, Any]:
        """Parse consignment data"""
        return {
            "isconsignment": consignment_data.get("isconsignment", 0),
            "endtime": consignment_data.get("endtime", 0),
            "imurl": consignment_data.get("imurl", ""),
            "isyouxin": consignment_data.get("isyouxin", 0),
            "citytype": consignment_data.get("citytype", 0),
        }

    def _parse_cpc_info(self, cpc_data: Dict) -> Dict[str, Any]:
        """Parse CPC info data"""
        return {
            "adid": cpc_data.get("adid", 0),
            "platform": cpc_data.get("platform", 0),
            "cpctype": cpc_data.get("cpctype", 0),
            "position": cpc_data.get("position", 0),
            "encryptinfo": cpc_data.get("encryptinfo", ""),
        }