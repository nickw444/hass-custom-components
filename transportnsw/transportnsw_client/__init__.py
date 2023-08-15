import datetime
from typing import Literal, List

import requests
from google.transit import gtfs_realtime_pb2

from .model import TripRequestResponse, RouteProductClass, Journey, JourneyLeg

ModeOfTransport = Literal["train", "light_rail", "bus", "coach", "ferry", "school_bus"]


class TransportNSWClient:
    def __init__(self, api_key: str):
        self._api_key = api_key

    def get_trip(
        self,
        origin: str,
        destination: str,
        num_journeys: int = 1,
        depart_at: datetime.datetime = None,
        arrive_by: datetime.datetime = None,
        include_mot: List[ModeOfTransport] = None,
        exclude_mot: List[ModeOfTransport] = None,
    ) -> TripRequestResponse:
        if depart_at is not None and arrive_by is not None:
            raise AssertionError("Unable to specify both depart_at and arrive_by")

        if include_mot is not None and exclude_mot is not None:
            raise AssertionError("Unable to specify both include_mot and exclude_mot")

        exclude_mot_params = get_exclude_mot_params(
            include_mot=include_mot, exclude_mot=exclude_mot
        )
        itd = depart_at or arrive_by or datetime.datetime.now()

        params = {
            "outputFormat": "rapidJSON",
            "depArrMacro": "arr" if arrive_by is not None else "dep",
            "itdDate": itd.strftime("%Y%m%d"),
            "itdTime": itd.strftime("%H%M"),
            "type_origin": "any",
            "type_destination": "any",
            "name_origin": origin,
            "name_destination": destination,
            "calcNumberOfTrips": num_journeys,
            "version": "10.2.1.42",
            "TfNSWTR": "true",
            **exclude_mot_params,
        }
        resp = requests.get(
            "https://api.transport.nsw.gov.au/v1/tp/trip",
            params=params,
            headers={"Authorization": f"apikey {self._api_key}"},
        )
        resp.raise_for_status()
        data = resp.json()
        return TripRequestResponse(**data)

    def get_realtime_feed(self, mode: str):
        resp = requests.get(
            f"https://api.transport.nsw.gov.au/v1/gtfs/vehiclepos/{mode}",
            headers={"Authorization": f"apikey {self._api_key}"},
        )
        resp.raise_for_status()

        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(resp.content)
        return feed


excl_mot_map = {
    "train": "exclMOT_1",
    "light_rail": "exclMOT_4",
    "bus": "exclMOT_5",
    "coach": "exclMOT_7",
    "ferry": "exclMOT_9",
    "school_bus": "exclMOT_11",
}


def get_exclude_mot_params(
    include_mot: List[ModeOfTransport] | None, exclude_mot: List[ModeOfTransport] | None
):
    params = {}

    if include_mot:
        exclude = set(excl_mot_map.keys()) - set(include_mot)
        params["excludedMeans"] = "checkbox"
        for entry in exclude:
            params[excl_mot_map[entry]] = "1"
    elif exclude_mot is not None:
        params["excludedMeans"] = "checkbox"
        for mot in exclude_mot:
            params[excl_mot_map[mot]] = "1"

    return params
