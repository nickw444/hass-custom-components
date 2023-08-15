import datetime
import sys

from .utils import (
    count_trip_changes,
    get_first_nonwalking_leg,
    get_gtfs_mode,
    find_realtime_info,
)
from . import TransportNSWClient


def main():
    client = TransportNSWClient(sys.argv[1])
    resp = client.get_trip(
        origin="222310", destination="200060", num_journeys=1, include_mot=["bus"]
    )

    for journey in resp.journeys:
        origin_leg = get_first_nonwalking_leg(journey.legs)
        dest_leg = get_first_nonwalking_leg(reversed(journey.legs))

        origin = origin_leg.origin
        destination = dest_leg.destination
        trip_changes = count_trip_changes(journey.legs)

        print("Origin", origin.id, origin.name, origin.disassembledName)
        print(
            "Destination",
            destination.id,
            destination.name,
            destination.disassembledName,
        )

        print("Trip Changes", trip_changes)
        print("Origin Mode", origin_leg.transportation.product.klass)

        print("Departure Time (est)", origin.departureTimeEstimated)
        print("Departure Time (planned)", origin.departureTimePlanned)
        print("Now", datetime.datetime.now(datetime.timezone.utc))
        print(
            "Due",
            origin.departureTimeEstimated
            - datetime.datetime.now(datetime.timezone.utc),
        )

        print("Arrival Time (est)", destination.arrivalTimeEstimated)
        print("Arrival Time (planned)", destination.arrivalTimePlanned)

        print("Occupancy", origin.properties.occupancy)
        print("Occupancy", destination.properties.occupancy)
        print("RealTimeTrip", origin_leg.transportation.properties.realtime_trip_id)

        print("Origin Line (short)", origin_leg.transportation.disassembledName)
        print("Origin Line", origin_leg.transportation.number)
        print("Origin Line (desc)", origin_leg.transportation.description)

        realtime_trip_id = origin_leg.transportation.properties.realtime_trip_id
        mode = get_gtfs_mode(origin_leg.transportation.product.klass)
        if mode is not None and realtime_trip_id is not None:
            feed = client.get_realtime_feed(mode)
            realtime = find_realtime_info(feed, realtime_trip_id)
            print(realtime.vehicle.position)


if __name__ == "__main__":
    main()
