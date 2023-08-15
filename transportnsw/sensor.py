"""Support for Transport NSW (AU) to query next leave event."""
from __future__ import annotations

import datetime
import logging
import math
from typing import List, Tuple, Any, get_args

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_NAME, UnitOfTime, CURRENCY_DOLLAR
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from .transportnsw_client import ModeOfTransport
from .transportnsw_client.model import Journey, RouteProductClass, TripRequestResponse
from .transportnsw_client.utils import (
    get_ticket,
    get_first_nonwalking_leg,
    count_trip_changes,
)

_LOGGER = logging.getLogger(__name__)

ATTR_DEPARTURE_TIME_ESTIMATED = "departure_time_estimated"
ATTR_DEPARTURE_TIME_PLANNED = "departure_time_planned"
ATTR_ARRIVAL_TIME_ESTIMATED = "arrival_time_estimated"
ATTR_ARRIVAL_TIME_PLANNED = "arrival_time_planned"

ATTR_ORIGIN_STOP_ID = "origin_stop_id"
ATTR_ORIGIN_NAME = "origin_name"
ATTR_DESTINATION_STOP_ID = "destination_stop_id"
ATTR_DESTINATION_NAME = "destination_name"
ATTR_ORIGIN_TRANSPORT_TYPE = "origin_transport_type"
ATTR_ORIGIN_TRANSPORT_NAME = "origin_transport_name"
ATTR_ORIGIN_LINE_NAME = "origin_line_name"
ATTR_ORIGIN_LINE_NAME_SHORT = "origin_line_name_short"
ATTR_CHANGES = "changes"
ATTR_OCCUPANCY = "occupancy"
ATTR_REAL_TIME_TRIP_ID = "real_time_trip_id"
ATTR_FARE_TYPE = "fare_type"
ATTR_FARE_PRICE = "fare_price"
ATTR_LATITUDE = "latitude"
ATTR_LONGITUDE = "longitude"

ICONS = {
    RouteProductClass.TRAIN: "mdi:train",
    RouteProductClass.LIGHT_RAIL: "mdi:tram",
    RouteProductClass.BUS: "mdi:bus",
    RouteProductClass.COACH: "mdi:bus",
    RouteProductClass.FERRY: "mdi:ferry",
    RouteProductClass.SCHOOL_BUS: "mdi:bus",
    None: "mdi:clock",
}

CONF_COORDINATOR = "coordinator"
CONF_STOP_ID = "stop_id"
CONF_DESTINATION_STOP_ID = "destination_stop_id"
CONF_NUM_JOURNEYS = "num_journeys"
CONF_FARE_TYPE = "fare_type"
CONF_MODES_OF_TRANSPORT = "modes_of_transport"
CONF_ALLOWED_MOT = []

CONF_TRIP = "trip"
CONF_TRIP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_STOP_ID): cv.string,
        vol.Required(CONF_DESTINATION_STOP_ID): cv.string,
        vol.Optional(CONF_NUM_JOURNEYS, default=1): cv.positive_int,
        vol.Optional(CONF_FARE_TYPE, default="ADULT"): cv.string,
        vol.Optional(CONF_MODES_OF_TRANSPORT): vol.All(
            cv.ensure_list, [vol.In(get_args(ModeOfTransport))]
        ),
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Transport NSW sensor."""
    coordinator = discovery_info[CONF_COORDINATOR]
    route = discovery_info[CONF_TRIP]

    if coordinator.data is None:
        _LOGGER.error("Initial data not available. Cannot setup sensor.")
        return

    entities = []
    for trip_index in range(route[CONF_NUM_JOURNEYS]):
        entities.append(
            TransportNSWJourneySensor(
                coordinator,
                name=route[CONF_NAME],
                stop_id=route[CONF_STOP_ID],
                destination_stop_id=route[CONF_DESTINATION_STOP_ID],
                trip_index=trip_index,
                fare_type=route[CONF_FARE_TYPE],
            )
        )

        # TODO: Add Sensor(s) for service information/delays?

        for fare_type in ["ADULT", "CHILD", "SCHOLAR", "SENIOR"]:
            entities.append(
                TransportNSWJourneyFareSensor(
                    coordinator,
                    name=route[CONF_NAME],
                    stop_id=route[CONF_STOP_ID],
                    destination_stop_id=route[CONF_DESTINATION_STOP_ID],
                    trip_index=trip_index,
                    fare_type=fare_type,
                )
            )

    add_entities(entities)


class TransportNSWJourneyFareSensor(
    CoordinatorEntity[DataUpdateCoordinator[List[Tuple[Journey, Any]]]], SensorEntity
):
    _attr_attribution = "Data provided by Transport NSW"
    _attr_native_unit_of_measurement = CURRENCY_DOLLAR
    _attr_icon = "mdi:cash"

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[List[Tuple[Journey, Any]]],
        name: str,
        stop_id: str,
        destination_stop_id: str,
        trip_index: int,
        fare_type: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._name = name
        self._stop_id = stop_id
        self._destination_stop_id = destination_stop_id
        self._trip_index = trip_index
        self._fare_type = fare_type

        self._attr_name = f"{name} {trip_index + 1} {self._fare_type.capitalize()} Fare"
        self._attr_unique_id = f"tnsw-{self._stop_id}-{self._destination_stop_id}-{self._trip_index}-fare-{self._fare_type}"

    def _get_journey(self) -> Tuple[Journey, Any] | None:
        if (
            self.coordinator.data is None
            or len(self.coordinator.data) <= self._trip_index
        ):
            return None

        return self.coordinator.data[self._trip_index]

    @property
    def native_value(self):
        """Return the state of the sensor."""
        journey, _ = self._get_journey()
        if journey is None:
            return None

        ticket = get_ticket(journey.fare.tickets, self._fare_type)
        return str(ticket.priceBrutto)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.data is not None


class TransportNSWJourneySensor(
    CoordinatorEntity[DataUpdateCoordinator[List[Tuple[Journey, Any]]]], SensorEntity
):
    _attr_attribution = "Data provided by Transport NSW"
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[List[Tuple[Journey, Any]]],
        name: str,
        stop_id: str,
        destination_stop_id: str,
        trip_index: int,
        fare_type: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._name = name
        self._stop_id = stop_id
        self._destination_stop_id = destination_stop_id
        self._trip_index = trip_index
        self._fare_type = fare_type

        self._attr_name = f"{name} {trip_index + 1}"
        self._attr_unique_id = (
            f"tnsw-{self._stop_id}-{self._destination_stop_id}-{self._trip_index}"
        )

    def _get_journey(self) -> Tuple[Journey, Any] | None:
        if (
            self.coordinator.data is None
            or len(self.coordinator.data) <= self._trip_index
        ):
            return None

        return self.coordinator.data[self._trip_index]

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state."""
        return True

    @property
    def native_value(self):
        """Return the state of the sensor."""
        journey, _ = self._get_journey()
        if journey is None:
            return None

        origin_leg = get_first_nonwalking_leg(journey.legs)
        origin = origin_leg.origin
        due = origin.departureTimeEstimated - datetime.datetime.now(
            datetime.timezone.utc
        )

        return math.floor(max(due.total_seconds() / 60, 0))

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        journey, realtime = self._get_journey()
        if journey is None:
            return None

        origin_leg = get_first_nonwalking_leg(journey.legs)
        dest_leg = get_first_nonwalking_leg(reversed(journey.legs))

        origin = origin_leg.origin
        destination = dest_leg.destination
        trip_changes = count_trip_changes(journey.legs)

        ticket = get_ticket(journey.fare.tickets, self._fare_type)

        return {
            ATTR_ORIGIN_STOP_ID: origin.id,
            ATTR_ORIGIN_NAME: origin.name,
            ATTR_DESTINATION_STOP_ID: destination.id,
            ATTR_DESTINATION_NAME: destination.name,
            ATTR_DEPARTURE_TIME_ESTIMATED: origin.departureTimeEstimated,
            ATTR_DEPARTURE_TIME_PLANNED: origin.departureTimePlanned,
            ATTR_ARRIVAL_TIME_ESTIMATED: destination.arrivalTimeEstimated,
            ATTR_ARRIVAL_TIME_PLANNED: destination.arrivalTimePlanned,
            ATTR_ORIGIN_TRANSPORT_TYPE: origin_leg.transportation.product.klass,
            ATTR_ORIGIN_TRANSPORT_NAME: origin_leg.transportation.product.klass.name,
            ATTR_ORIGIN_LINE_NAME: origin_leg.transportation.number,
            ATTR_ORIGIN_LINE_NAME_SHORT: origin_leg.transportation.disassembledName,
            ATTR_CHANGES: trip_changes,
            ATTR_OCCUPANCY: origin_leg.destination.properties.occupancy,
            ATTR_REAL_TIME_TRIP_ID: origin_leg.transportation.properties.realtime_trip_id,
            ATTR_FARE_TYPE: ticket.person,
            ATTR_FARE_PRICE: str(ticket.priceBrutto),
            ATTR_LATITUDE: realtime.vehicle.position.latitude
            if realtime is not None
            else None,
            ATTR_LONGITUDE: realtime.vehicle.position.longitude
            if realtime is not None
            else None,
        }

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        journey, _ = self._get_journey()
        if journey is None:
            return "mdi:clock"

        origin_leg = get_first_nonwalking_leg(journey.legs)
        return ICONS.get(origin_leg.transportation.product.klass, "mdi:clock")

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.data is not None


def get_due(estimated):
    """Min until departure"""
    due = 0
    if estimated > datetime.datetime.utcnow():
        due = round((estimated - datetime.datetime.utcnow()).seconds / 60)
    return due
