import datetime
import decimal
from enum import Enum
from typing import List, Literal

from pydantic import BaseModel, Field


class JourneyFareZone(BaseModel):
    pass


class JourneyFareTicket(BaseModel):
    id: str
    name: str
    comment: str
    person: Literal["ADULT", "CHILD", "SCHOLAR", "SENIOR"]
    priceLevel: str | None
    priceBrutto: decimal.Decimal


class Fare(BaseModel):
    tickets: List[JourneyFareTicket]
    zones: List[JourneyFareZone] | None = Field(default=None)


class AdditionalInfoResponseTimestamps(BaseModel):
    creation: datetime.datetime
    lastModification: datetime.datetime
    # availability:
    # validity


class JourneyLegStopInfo(BaseModel):
    timestamps: AdditionalInfoResponseTimestamps | None = Field(default=None)
    priority: Literal["veryLow", "low", "normal", "high", "veryHigh"]
    id: str
    version: int
    urlText: str | None
    url: str | None
    content: str | None
    subtitle: str | None


class JourneyLegStop(BaseModel):
    class JourneyLegStopProperties(BaseModel):
        occupancy: str = Field(default=None)

    id: str
    name: str
    disassembledName: str | None
    type: str
    # coord
    # parent
    departureTimeEstimated: datetime.datetime | None = Field(default=None)
    departureTimePlanned: datetime.datetime | None = Field(default=None)
    arrivalTimeEstimated: datetime.datetime | None = Field(default=None)
    arrivalTimePlanned: datetime.datetime | None = Field(default=None)
    properties: JourneyLegStopProperties


class RouteProductClass(Enum):
    TRAIN = 1
    LIGHT_RAIL = 4
    BUS = 5
    COACH = 7
    FERRY = 9
    SCHOOL_BUS = 11
    WALKING = 99
    WALKING_FOOTPATH = 100
    BICYCLE = 101
    TAKE_BICYCLE_ON_PUBLIC_TRANSPORT = 102
    KISS_AND_RIDE = 103
    PARK_AND_RIDE = 104
    TAXI = 105
    CAR = 106


class RouteProduct(BaseModel):
    name: str
    # 1: Train
    # 4: Light Rail
    # 5: Bus
    # 7: Coach
    # 9: Ferry
    # 11: School Bus
    # 99: Walking
    # 100: Walking (Footpath)
    # 101: Bicycle
    # 102: Take Bicycle On Public Transport
    # 103: Kiss & Ride
    # 104: Park & Ride
    # 105: Taxi
    # 106: Car
    klass: RouteProductClass = Field(alias="class")
    iconId: int


class TripTransportation(BaseModel):
    class TripTransportationProperties(BaseModel):
        realtime_trip_id: str | None = Field(alias="RealtimeTripId", default=None)

    id: str | None
    name: str | None
    disassembledName: str | None
    number: str | None
    # 1: Sydney Trains (product class 1)
    # 2: Intercity Trains (product class 1)
    # 3: Regional Trains (product class 1)
    # 19: Temporary Trains (product class 1)
    # 13: Sydney Light Rail (product class 4)
    # 20: Temporary Light Rail (product class 4)
    # 21: Newcastle Light Rail (product class 4)
    # 4: Blue Mountains Buses (product class 5)
    # 5: Sydney Buses (product class 5)
    # 6: Central Coast Buses (product class 5)
    # 14: Temporary Buses (product class 5)
    # 15: Hunter Buses (product class 5)
    # 16: Illawarra Buses (product class 5)
    # 9: Private Buses (product class 5)
    # 17: Private Coaches (product class 5)
    # 7: Regional Coaches (product class 7)
    # 22: Temporary Coaches (product class 7)
    # 10: Sydney Ferries (product class 9)
    # 11: Newcastle Ferries (product class 9)
    # 12: Private Ferries (product class 9)
    # 18: Temporary Ferries (product class 9)
    # 8: School Buses (product class 11)
    iconId: int | None
    description: str | None
    product: RouteProduct
    # operator
    # destination
    properties: TripTransportationProperties


class JourneyLeg(BaseModel):
    duration: int
    distance: int | None = Field(default=None)
    isRealtimeControlled: bool | None = Field(default=None)
    origin: JourneyLegStop
    destination: JourneyLegStop
    transportation: TripTransportation | None = Field(default=None)
    # hints
    infos: List[JourneyLegStopInfo]
    # pathDescriptions
    # interchange
    # coords
    # properties


class Journey(BaseModel):
    rating: int | None
    isAdditional: int
    legs: List[JourneyLeg]
    fare: Fare


class TripRequestResponse(BaseModel):
    version: str
    journeys: List[Journey]
