from typing import Iterable, Literal

from google.transit import gtfs_realtime_pb2

from .model import RouteProductClass, JourneyFareTicket, JourneyLeg


def get_first_nonwalking_leg(legs: Iterable[JourneyLeg]) -> JourneyLeg | None:
    for leg in legs:
        # Both 99 and 100 indicate walking. = ['99', '100']
        if leg.transportation.product.klass not in (
            RouteProductClass.WALKING,
            RouteProductClass.WALKING_FOOTPATH,
        ):
            return leg

    return None


def count_trip_changes(legs: Iterable[JourneyLeg]) -> int:
    changes = -1
    for leg in legs:
        if leg.transportation.product.klass not in (99, 100):
            changes += 1

    return changes


def get_ticket(
    tickets: Iterable[JourneyFareTicket], person: str
) -> JourneyFareTicket | None:
    for ticket in tickets:
        if ticket.person == person:
            return ticket

    return None


def find_realtime_info(feed: gtfs_realtime_pb2.FeedMessage, realtime_trip_id: str):
    for entity in feed.entity:
        if entity.vehicle.trip.trip_id == realtime_trip_id:
            return entity


def get_gtfs_mode(
    klass: RouteProductClass,
) -> Literal["buses", "ferries", "lightrail", "sydneytrains"] | None:
    if klass == RouteProductClass.BUS:
        return "buses"
    elif klass == RouteProductClass.FERRY:
        return "ferries"
    elif klass == RouteProductClass.LIGHT_RAIL:
        return "lightrail"
    elif klass == RouteProductClass.TRAIN:
        return "sydneytrains"
    else:
        return None
