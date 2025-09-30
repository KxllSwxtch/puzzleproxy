"""
Che168 API Schemas
Pydantic models for Chinese car marketplace data structures
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class Che168ServiceType(str, Enum):
    """Service type codes for Che168"""

    ALL = ""  # 全部
    PLATFORM_SUBSIDY = "410"  # 平台补贴
    LIVE_PURCHASE = "480"  # 直播购
    DEALER_DIRECT = "27"  # 4S直卖
    NEW_ENERGY = "430"  # 新能源
    MEMBER_DEALER = "40"  # 会员商家
    SHOP = "306"  # 店铺
    INSTALLMENT = "330"  # 分期


class Che168CarTag(BaseModel):
    """Car tag/badge information"""

    title: str = Field(description="Tag title")
    bg_color: str = Field(description="Background color")
    bg_color_end: str = Field(description="Background end color")
    font_color: str = Field(description="Font color")
    border_color: str = Field(description="Border color")
    bg_color_direction: int = Field(description="Background direction")
    stype: str = Field(description="Style type")
    sort: int = Field(description="Sort order")
    icon: str = Field(description="Icon URL")
    url: str = Field(description="Link URL")
    image: str = Field(description="Image URL")
    imgheight: int = Field(description="Image height")
    imgwidth: int = Field(description="Image width")


class Che168CarTags(BaseModel):
    """Car tags container"""

    p1: List[Che168CarTag] = Field(default=[], description="Primary tags")
    p2: List[Che168CarTag] = Field(default=[], description="Secondary tags")
    p3: List[Che168CarTag] = Field(default=[], description="Tertiary tags")


class Che168CPCInfo(BaseModel):
    """CPC (Cost Per Click) advertising information"""

    adid: int = Field(description="Ad ID")
    platform: int = Field(description="Platform ID")
    cpctype: int = Field(description="CPC type")
    position: int = Field(description="Position")
    encryptinfo: str = Field(description="Encrypted info")


class Che168Consignment(BaseModel):
    """Consignment information"""

    isconsignment: int = Field(description="Is consignment (0/1)")
    endtime: int = Field(description="End time timestamp")
    imurl: str = Field(description="IM URL")
    isyouxin: int = Field(description="Is Youxin (0/1)")
    citytype: int = Field(description="City type")


class Che168CarListing(BaseModel):
    """Individual car listing from Che168"""

    infoid: int = Field(description="Car listing ID")
    carname: str = Field(description="Car name/model")
    cname: str = Field(description="City name")
    dealerid: int = Field(description="Dealer ID")
    mileage: str = Field(description="Mileage (万公里)")
    cityid: int = Field(description="City ID")
    seriesid: int = Field(description="Car series ID")
    specid: int = Field(description="Specification ID")
    sname: str = Field(description="Series name")
    syname: str = Field(description="Specification name")
    price: str = Field(description="Price (万元)")
    saveprice: str = Field(description="Save price")
    discount: str = Field(description="Discount")
    firstregyear: str = Field(description="First registration year")
    fromtype: int = Field(description="Source type")
    imageurl: str = Field(description="Main image URL")
    cartype: int = Field(description="Car type")
    bucket: int = Field(description="Bucket")
    isunion: int = Field(description="Is union (0/1)")
    isoutsite: int = Field(description="Is out site (0/1)")
    videourl: str = Field(description="Video URL")
    car_level: int = Field(description="Car level")
    dealer_level: str = Field(description="Dealer level info")
    downpayment: str = Field(description="Down payment (万元)")
    url: str = Field(description="Car detail URL")
    position: int = Field(description="Position in results")
    isnewly: int = Field(description="Is newly listed (0/1)")
    kindname: str = Field(default="", description="Kind name")
    usc_adid: int = Field(default=0, description="USC ad ID")
    particularactivity: int = Field(default=0, description="Particular activity")
    livestatus: int = Field(default=0, description="Live status")
    stra: str = Field(default="", description="Strategy")
    springid: str = Field(default="", description="Spring ID")
    followcount: int = Field(default=0, description="Follow count")
    cxctype: int = Field(default=0, description="CXC type")
    isfqtj: int = Field(default=0, description="Is FQTJ")
    isrelivedbuy: int = Field(default=0, description="Is relived buy")
    photocount: int = Field(default=0, description="Photo count")
    isextwarranty: int = Field(default=0, description="Is extended warranty")
    offertype: int = Field(default=0, description="Offer type")
    displacement: str = Field(default="", description="Engine displacement")
    environmental: str = Field(default="", description="Environmental standard")
    liveurl: str = Field(default="", description="Live URL")
    imuserid: str = Field(default="", description="IM user ID")
    pv_extstr: str = Field(default="", description="PV extension string")
    act_discount: str = Field(default="", description="Active discount")
    cartags: Optional[Che168CarTags] = Field(default=None, description="Car tags")
    consignment: Optional[Che168Consignment] = Field(default=None, description="Consignment info")
    cpcinfo: Optional[Che168CPCInfo] = Field(default=None, description="CPC info")


class Che168ServiceOption(BaseModel):
    """Service filter option"""

    title: str = Field(description="Display title")
    subtitle: str = Field(description="Subtitle")
    key: str = Field(description="Filter key")
    value: str = Field(description="Filter value")
    icon: str = Field(description="Icon URL")
    iconfocus: str = Field(description="Focused icon URL")
    tag: str = Field(description="Tag")
    viewtype: int = Field(description="View type")
    iconwidth: int = Field(description="Icon width")
    badgetitle: str = Field(description="Badge title")
    headbgurl: str = Field(description="Header background URL")
    headsubbgurl: str = Field(description="Header sub background URL")
    titlecolorfocus: str = Field(description="Title color focus")
    titlecolor: str = Field(description="Title color")
    tabtype: int = Field(description="Tab type")
    linkurl: str = Field(description="Link URL")
    basevalue: str = Field(description="Base value")
    dtype: int = Field(description="Data type")
    subvalue: str = Field(description="Sub value")
    subspecname: str = Field(description="Sub spec name")
    needreddot: int = Field(description="Need red dot")
    brandvalue: str = Field(description="Brand value")
    brandname: str = Field(description="Brand name")
    isgray: int = Field(description="Is gray")


class Che168Brand(BaseModel):
    """Car brand information"""

    bid: int = Field(description="Brand ID")
    name: str = Field(description="Brand name")
    py: str = Field(description="Pinyin")
    icon: str = Field(description="Brand icon URL")
    price: str = Field(default="", description="Price range")
    on_sale_num: int = Field(description="Number of cars on sale")
    dtype: int = Field(default=0, description="Data type")


class Che168BrandsResult(BaseModel):
    """Brands response result"""

    hotbrand: List[Che168Brand] = Field(description="Hot/popular brands")
    allbrand: List[Che168Brand] = Field(description="All brands")


class Che168BrandsResponse(BaseModel):
    """Complete brands API response"""

    returncode: int = Field(description="Return code (0=success)")
    message: str = Field(description="Response message")
    result: Che168BrandsResult = Field(description="Brands data")


class Che168SearchResult(BaseModel):
    """Search response result"""

    totalcount: int = Field(description="Total car count")
    pagesize: int = Field(description="Page size")
    pageindex: int = Field(description="Current page index")
    pagecount: int = Field(description="Total page count")
    queryid: str = Field(default="", description="Query ID")
    styletype: int = Field(default=0, description="Style type")
    showtype: int = Field(default=0, description="Show type")
    service: List[Che168ServiceOption] = Field(default=[], description="Service options")
    subservice: List[Che168ServiceOption] = Field(default=[], description="Sub service options")
    filters: List[Che168ServiceOption] = Field(default=[], description="Filter options")
    carlist: List[Che168CarListing] = Field(default=[], description="Car listings")


class Che168SearchResponse(BaseModel):
    """Complete search API response"""

    returncode: int = Field(description="Return code (0=success)")
    message: str = Field(description="Response message")
    result: Che168SearchResult = Field(description="Search data")


class Che168SearchFilters(BaseModel):
    """Search filter parameters"""

    pageindex: int = Field(default=1, description="Page index")
    pagesize: int = Field(default=20, description="Page size")
    brandid: Optional[int] = Field(default=None, description="Brand ID")
    seriesid: Optional[int] = Field(default=None, description="Series ID")
    seriesyearid: Optional[int] = Field(default=None, description="Series year ID")
    specid: Optional[int] = Field(default=None, description="Specification ID")
    service: Optional[str] = Field(default=None, description="Service type")
    price_min: Optional[float] = Field(default=None, description="Minimum price")
    price_max: Optional[float] = Field(default=None, description="Maximum price")
    transmission: Optional[str] = Field(default=None, description="Transmission type (manual/automatic)")
    mileage_max: Optional[float] = Field(default=None, description="Maximum mileage")
    sort: Optional[str] = Field(default=None, description="Sort order")
    ishideback: int = Field(default=0, description="Is hide back")
    srecom: int = Field(default=1, description="Search recommendation")
    personalizedpush: int = Field(default=1, description="Personalized push")
    cid: int = Field(default=0, description="City ID")
    iscxcshowed: int = Field(default=0, description="Is CXC showed")
    scene_no: str = Field(default="common_2sc_wap_mc_mclby", description="Scene number")
    pid: int = Field(default=0, description="PID")
    filtertype: int = Field(default=4, description="Filter type")
    ssnew: int = Field(default=0, description="SS new")


class Che168CarDetail(BaseModel):
    """Detailed car information"""

    infoid: int = Field(description="Car listing ID")
    title: str = Field(description="Car title")
    price: str = Field(description="Price")
    year: str = Field(description="Year")
    mileage: str = Field(description="Mileage")
    location: str = Field(description="Location")
    images: List[str] = Field(default=[], description="Car images")
    description: str = Field(default="", description="Car description")
    params: Dict[str, Any] = Field(default={}, description="Technical parameters")
    seller_info: Dict[str, Any] = Field(default={}, description="Seller information")


class Che168CarDetailResponse(BaseModel):
    """Car detail API response"""

    returncode: int = Field(description="Return code (0=success)")
    message: str = Field(description="Response message")
    result: Che168CarDetail = Field(description="Car detail data")


class Che168CarInfoResponse(BaseModel):
    """Basic car info response"""

    returncode: int = Field(description="Return code (0=success)")
    message: str = Field(description="Response message")
    result: Dict[str, Any] = Field(description="Basic car info")


class Che168CarParamsResponse(BaseModel):
    """Car parameters response"""

    returncode: int = Field(description="Return code (0=success)")
    message: str = Field(description="Response message")
    result: Dict[str, Any] = Field(description="Car parameters")


class Che168CarAnalysisResponse(BaseModel):
    """Car analysis response"""

    returncode: int = Field(description="Return code (0=success)")
    message: str = Field(description="Response message")
    result: Dict[str, Any] = Field(description="Car analysis data")


class TranslationRequest(BaseModel):
    """Translation request"""

    text: str = Field(description="Text to translate")
    target_lang: str = Field(default="ru", description="Target language")


class TranslationResponse(BaseModel):
    """Translation response"""

    returncode: int = Field(description="Return code (0=success)")
    message: str = Field(description="Response message")
    result: Dict[str, Any] = Field(description="Translation result")


class Che168FiltersResponse(BaseModel):
    """Filters response"""

    returncode: int = Field(description="Return code (0=success)")
    message: str = Field(description="Response message")
    result: Dict[str, Any] = Field(description="Available filters")