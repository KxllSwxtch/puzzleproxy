"""
Pydantic schemas for Encar vehicle record/accident data
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class AccidentRecord(BaseModel):
    """Individual accident record with insurance claim details"""
    type: str = Field(..., description="Accident type: 1=자차, 2=대인, 3=대물")
    date: str = Field(..., description="Accident date in YYYY-MM-DD format")
    insuranceBenefit: int = Field(..., description="Insurance payout amount in KRW")
    partCost: int = Field(..., description="Parts replacement cost in KRW")
    laborCost: int = Field(..., description="Labor cost in KRW")
    paintingCost: int = Field(..., description="Painting/body work cost in KRW")


class CarInfoChange(BaseModel):
    """Car information change record"""
    date: str = Field(..., description="Change date in YYYY-MM-DD format")
    carNo: str = Field(..., description="Car plate number (may be masked)")


class EncarRecordResponse(BaseModel):
    """Complete vehicle record/accident history response"""
    success: bool = Field(default=True, description="Request success status")

    # Basic vehicle information
    openData: Optional[bool] = Field(None, description="Whether data is publicly available")
    regDate: Optional[str] = Field(None, description="Registration date")
    carNo: Optional[str] = Field(None, description="Car plate number")
    year: Optional[str] = Field(None, description="Model year")
    maker: Optional[str] = Field(None, description="Manufacturer name")
    carKind: Optional[str] = Field(None, description="Car kind code")
    use: Optional[str] = Field(None, description="Usage type code")
    displacement: Optional[str] = Field(None, description="Engine displacement")
    carName: Optional[str] = Field(None, description="Car name")
    firstDate: Optional[str] = Field(None, description="First registration date")
    fuel: Optional[str] = Field(None, description="Fuel type")
    carShape: Optional[str] = Field(None, description="Body shape")
    model: Optional[str] = Field(None, description="Model name")
    transmission: Optional[str] = Field(None, description="Transmission type")
    carNameCode: Optional[str] = Field(None, description="Car name code")

    # Accident counts
    myAccidentCnt: int = Field(default=0, description="Number of own-fault accidents (자차)")
    otherAccidentCnt: int = Field(default=0, description="Number of other-party accidents (대인/대물)")
    accidentCnt: int = Field(default=0, description="Total number of accidents")

    # Accident costs
    myAccidentCost: int = Field(default=0, description="Total cost of own-fault accidents in KRW")
    otherAccidentCost: int = Field(default=0, description="Total cost of other-party accidents in KRW")

    # Ownership
    ownerChangeCnt: int = Field(default=0, description="Number of owner changes")
    ownerChanges: List[dict] = Field(default_factory=list, description="Owner change history")

    # Theft/Loss
    robberCnt: int = Field(default=0, description="Number of theft incidents")
    robberDate: Optional[str] = Field(None, description="Theft date if any")
    totalLossCnt: int = Field(default=0, description="Number of total loss incidents")
    totalLossDate: Optional[str] = Field(None, description="Total loss date if any")

    # Flood damage
    floodTotalLossCnt: int = Field(default=0, description="Flood total loss count")
    floodPartLossCnt: Optional[int] = Field(None, description="Flood partial loss count")
    floodDate: Optional[str] = Field(None, description="Flood damage date if any")

    # Special usage
    government: int = Field(default=0, description="Government vehicle flag")
    business: int = Field(default=0, description="Business vehicle flag")
    loan: int = Field(default=0, description="Loan/financial flag")

    # Car number changes
    carNoChangeCnt: int = Field(default=0, description="Number of plate number changes")
    carInfoChanges: List[CarInfoChange] = Field(default_factory=list, description="Car info change history")

    # Usage history
    carInfoUse1s: List[str] = Field(default_factory=list, description="Primary usage history")
    carInfoUse2s: List[str] = Field(default_factory=list, description="Secondary usage history")

    # Insurance non-subscription periods
    notJoinDate1: Optional[str] = Field(None, description="Non-subscription period 1")
    notJoinDate2: Optional[str] = Field(None, description="Non-subscription period 2")
    notJoinDate3: Optional[str] = Field(None, description="Non-subscription period 3")
    notJoinDate4: Optional[str] = Field(None, description="Non-subscription period 4")
    notJoinDate5: Optional[str] = Field(None, description="Non-subscription period 5")

    # Detailed accident records
    accidents: List[AccidentRecord] = Field(default_factory=list, description="Detailed accident history")

    # Metadata
    meta: dict = Field(default_factory=dict, description="Additional metadata")


class EncarRecordErrorResponse(BaseModel):
    """Error response when record data cannot be fetched"""
    success: bool = Field(default=False)
    error: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Error code (404, 403, etc)")
    meta: dict = Field(default_factory=dict, description="Additional error metadata")
