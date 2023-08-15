"""The transportnsw component."""
import datetime
import logging
import threading
import time
from functools import lru_cache
from typing import Any, Tuple, List

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from .sensor import (
    CONF_TRIP_SCHEMA,
    CONF_COORDINATOR,
    CONF_TRIP,
    CONF_STOP_ID,
    CONF_DESTINATION_STOP_ID,
    CONF_NUM_JOURNEYS,
    CONF_MODES_OF_TRANSPORT,
)
from .transportnsw_client import TransportNSWClient, Journey
from .transportnsw_client.utils import (
    get_gtfs_mode,
    get_first_nonwalking_leg,
    find_realtime_info,
)

_LOGGER = logging.getLogger(__name__)

DOMAIN = "transportnsw"

CONF_TRIPS = "trips"

SCAN_INTERVAL = datetime.timedelta(minutes=1)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_API_KEY): cv.string,
                vol.Required(CONF_TRIPS): vol.All(cv.ensure_list, [CONF_TRIP_SCHEMA]),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    conf = config[DOMAIN]
    client = TransportNSWClient(conf[CONF_API_KEY])
    gtfs_cache = GTFSCache(client)

    for trip in conf[CONF_TRIPS]:

        async def async_update_data() -> List[Tuple[Journey, Any]]:
            resp = await hass.async_add_executor_job(
                client.get_trip,
                trip[CONF_STOP_ID],
                trip[CONF_DESTINATION_STOP_ID],
                trip[CONF_NUM_JOURNEYS],
                None,
                None,
                trip.get(CONF_MODES_OF_TRANSPORT),
            )
            res = []

            # Hydrate journey information with realtime information if it is available. This
            # utilises an LRU cache with TTL to avoid hammering the GTFS endpoint for every
            # defined trip.
            for journey in resp.journeys:
                realtime = None

                origin_leg = get_first_nonwalking_leg(journey.legs)
                if origin_leg is not None:
                    realtime_trip_id = (
                        origin_leg.transportation.properties.realtime_trip_id
                    )
                    mode = get_gtfs_mode(origin_leg.transportation.product.klass)

                    if realtime_trip_id is not None and mode is not None:
                        feed = await hass.async_add_executor_job(
                            gtfs_cache.get_gtfs_feed,
                            mode,
                        )
                        realtime = find_realtime_info(feed, realtime_trip_id)

                res.append((journey, realtime))

            return res

        coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name="sensor",
            update_interval=SCAN_INTERVAL,
            update_method=async_update_data,
        )
        await coordinator.async_refresh()

        hass.async_create_task(
            async_load_platform(
                hass,
                Platform.SENSOR,
                DOMAIN,
                {CONF_TRIP: trip, CONF_COORDINATOR: coordinator},
                config,
            )
        )

    return True


class GTFSCache:
    def __init__(self, client: TransportNSWClient):
        self._client = client
        self._lock = threading.Lock()

    def get_gtfs_feed(self, mode):
        with self._lock:
            return self._get_gtfs_feed(mode=mode, ttl_hash=round(time.time() / 60))

    @lru_cache()
    def _get_gtfs_feed(self, mode, ttl_hash=None):
        return self._client.get_realtime_feed(mode)
