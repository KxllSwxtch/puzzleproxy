from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class KCarManufacturer(BaseModel):
    """KCar manufacturer model"""
    path: str
    car_type: str = Field(alias="carType")
    manufacturer_name: str = Field(alias="mnuftrNm")
    manufacturer_eng_name: str = Field(alias="mnuftrEnm")
    manufacturer_type: str = Field(alias="mnuftrType")
    count: int
    manufacturer_code: str = Field(alias="mnuftrCd")
    path_name: str = Field(alias="pathNm")

    class Config:
        populate_by_name = True


class KCarModelGroup(BaseModel):
    """KCar model group model"""
    path: str
    car_type: str = Field(alias="carType")
    manufacturer_name: str = Field(alias="mnuftrNm")
    manufacturer_type: str = Field(alias="mnuftrType")
    model_group_code: str = Field(alias="modelGrpCd")
    count: int
    manufacturer_code: str = Field(alias="mnuftrCd")
    model_group_name: str = Field(alias="modelGrpNm")
    path_name: str = Field(alias="pathNm")

    class Config:
        populate_by_name = True


class KCarModel(BaseModel):
    """KCar model model"""
    path: str
    car_type: str = Field(alias="carType")
    production_year: str = Field(alias="prdcnYear")
    model_group_code: str = Field(alias="modelGrpCd")
    count: int
    manufacturer_code: str = Field(alias="mnuftrCd")
    model_name: str = Field(alias="modelNm")
    model_code: str = Field(alias="modelCd")
    path_name: str = Field(alias="pathNm")

    class Config:
        populate_by_name = True


class KCarGrade(BaseModel):
    """KCar grade model"""
    path: str
    model_group_code: str = Field(alias="modelGrpCd")
    grade_name: str = Field(alias="grdNm")
    count: int
    manufacturer_code: str = Field(alias="mnuftrCd")
    grade_code: str = Field(alias="grdCd")
    model_code: str = Field(alias="modelCd")
    path_name: str = Field(alias="pathNm")

    class Config:
        populate_by_name = True


class KCarGradeDetail(BaseModel):
    """KCar grade detail model"""
    path: str
    model_group_code: str = Field(alias="modelGrpCd")
    count: int
    manufacturer_code: str = Field(alias="mnuftrCd")
    grade_code: str = Field(alias="grdCd")
    grade_detail_name: str = Field(alias="grdDtlNm")
    model_code: str = Field(alias="modelCd")
    grade_detail_code: str = Field(alias="grdDtlCd")
    path_name: str = Field(alias="pathNm")

    class Config:
        populate_by_name = True


class KCarSearchItem(BaseModel):
    """KCar search result item"""
    car_code: str = Field(alias="carCd")
    manufacturer_code: str = Field(alias="mnuftrCd")
    manufacturer_name: str = Field(alias="mnuftrNm")
    model_group_code: str = Field(alias="modelGrpCd")
    model_group_name: str = Field(alias="modelGrpNm")
    model_code: str = Field(alias="modelCd")
    model_name: str = Field(alias="modelNm")
    grade_code: str = Field(alias="grdCd")
    grade_name: str = Field(alias="grdNm")
    grade_detail_code: Optional[str] = Field(alias="grdDtlCd", default=None)
    grade_detail_name: Optional[str] = Field(alias="grdDtlNm", default=None)
    car_wheel_name: str = Field(alias="carWhlNm")
    production_year: str = Field(alias="prdcnYr")
    manufacture_date: str = Field(alias="mfgDt")
    mileage: int = Field(alias="milg")
    fuel_code: str = Field(alias="fuelCd")
    fuel_name: str = Field(alias="fuelNm")
    transmission_code: str = Field(alias="trnsmsnCd")
    transmission_name: str = Field(alias="trnsmsnNm")
    price: int = Field(alias="prc")
    accident_history_code: str = Field(alias="acdtHistCd")
    accident_history_counts: str = Field(alias="acdtHistCnts")
    exterior_color_code: str = Field(alias="extrColorCd")
    exterior_color_name: str = Field(alias="extrColorNm")
    car_number: str = Field(alias="cno")
    center_code: str = Field(alias="cntrCd")
    center_name: str = Field(alias="cntrNm")
    center_region_code: str = Field(alias="cntrRgnCd")
    center_region_name: str = Field(alias="cntrRgnNm")
    seller_name: str = Field(alias="selerNm")
    seller_phone: Optional[str] = Field(alias="selerMpno", default=None)
    image_path: Optional[str] = Field(alias="lsizeImgPath", default=None)
    hotmark_name: Optional[str] = Field(alias="hotmarkNm", default=None)
    simple_description: Optional[str] = Field(alias="simcDesc", default=None)
    engine_displacement: Optional[str] = Field(alias="engdispmnt", default=None)
    passenger_count: Optional[str] = Field(alias="pasngrCnt", default=None)
    car_category_code: Optional[str] = Field(alias="carctgrCd", default=None)
    car_category_name: Optional[str] = Field(alias="carctgrNm", default=None)
    
    class Config:
        populate_by_name = True


class KCarSearchResponse(BaseModel):
    """KCar search response"""
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    extra_data: Optional[Dict] = Field(alias="extraData", default={})
    extra_string: Optional[str] = Field(alias="extraString", default=None)
    return_code: Optional[str] = Field(alias="returnCode", default=None)
    success: bool

    class Config:
        populate_by_name = True


class KCarApiResponse(BaseModel):
    """Generic KCar API response wrapper"""
    message: Optional[str] = None
    data: List[Any]
    extra_data: Optional[Dict] = Field(alias="extraData", default={})
    extra_string: Optional[str] = Field(alias="extraString", default=None)
    return_code: Optional[str] = Field(alias="returnCode", default=None)
    success: bool

    class Config:
        populate_by_name = True


class KCarManufacturersResponse(KCarApiResponse):
    """KCar manufacturers response"""
    data: List[KCarManufacturer]


class KCarModelGroupsResponse(KCarApiResponse):
    """KCar model groups response"""
    data: List[KCarModelGroup]


class KCarModelsResponse(KCarApiResponse):
    """KCar models response"""
    data: List[KCarModel]


class KCarGradesResponse(KCarApiResponse):
    """KCar grades response"""
    data: List[KCarGrade]


class KCarGradeDetailsResponse(KCarApiResponse):
    """KCar grade details response"""
    data: List[KCarGradeDetail]


class KCarParsedCar(BaseModel):
    """Parsed car from HTML"""
    id: str
    manufacturer: str
    model_group: str
    model: str
    grade: str
    grade_detail: Optional[str] = None
    year: int
    mileage: int
    price: int  # in 만원
    fuel_type: str
    transmission: str
    accident_status: str
    image_url: Optional[str] = None
    seller_location: str
    car_number: Optional[str] = None
    description: Optional[str] = None
    
    
class KCarSearchFilters(BaseModel):
    """Search filters for KCar"""
    manufacturer_code: Optional[str] = Field(alias="wr_eq_mnuftr_cd", default=None)
    model_group_code: Optional[str] = Field(alias="wr_eq_model_grp_cd", default=None)
    model_code: Optional[str] = Field(alias="wr_eq_model_cd", default=None)
    grade_code: Optional[str] = Field(alias="wr_eq_grd_cd", default=None)
    grade_detail_code: Optional[str] = Field(alias="wr_eq_grd_dtl_cd", default=None)
    sell_type: str = Field(alias="wr_eq_sell_dcd", default="ALL")
    multi_columns: str = Field(alias="wr_in_multi_columns", default="cntr_rgn_cd|cntr_cd")
    page: int = 1
    limit: int = 27
    
    class Config:
        populate_by_name = True