"""Calibrated light support for existing light entities."""
from __future__ import annotations

from typing import Any, Tuple

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components import light
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_EFFECT_LIST,
    ATTR_RGB_COLOR,
    COLOR_MODE_RGB,
    PLATFORM_SCHEMA,
    LightEntity,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    CONF_ENTITY_ID,
    CONF_NAME,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

DEFAULT_NAME = "Light Switch"

CONF_CALIBRATION_RGB = "calibration_rgb"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_ENTITY_ID): cv.entity_domain(light.DOMAIN),
        vol.Required(CONF_CALIBRATION_RGB): vol.All(
            cv.ensure_list, vol.Length(min=1), [vol.Range(min=-254, max=255)]
        ),
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
):
    """Set up entities for calibrated light platform."""

    registry = await hass.helpers.entity_registry.async_get_registry()
    wrapped_light = registry.async_get(config[CONF_ENTITY_ID])
    unique_id = wrapped_light.unique_id if wrapped_light else None

    async_add_entities(
        [
            CalibratedLight(
                config[CONF_ENTITY_ID],
                config[CONF_NAME],
                config[CONF_CALIBRATION_RGB],
                unique_id,
            )
        ]
    )


def clamp_rgb(value):
    """Clamp a given value between 0 and 255."""
    return min(max(value, 0), 255)


def apply_calibration(
    calibration: Tuple[int, int, int], color_rgb: Tuple[int, int, int], invert=False
) -> Tuple[int, int, int]:
    """Apply an RGB color calibration."""
    modifier = -1 if invert else 1
    return (
        clamp_rgb(color_rgb[0] + (calibration[0] * modifier)),
        clamp_rgb(color_rgb[1] + (calibration[1] * modifier)),
        clamp_rgb(color_rgb[2] + (calibration[2] * modifier)),
    )


class CalibratedLight(LightEntity):
    """Represents a calibrated light entity."""

    _attr_color_mode = COLOR_MODE_RGB
    _attr_supported_color_modes = {COLOR_MODE_RGB}

    def __init__(
        self,
        light_entity_id: str,
        name: str,
        calibration_rgb: Tuple[int, int, int],
        unique_id: str,
    ):
        """Initialize the calibrated light entity."""
        self._light_entity_id = light_entity_id
        self._light_state: State | None = None
        self._name = name
        self._calibration_rgb = calibration_rgb
        self._unique_id = unique_id

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        if self._light_state is None:
            return 0

        return self._light_state.attributes.get(ATTR_SUPPORTED_FEATURES)

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        return self._light_state.attributes.get(ATTR_BRIGHTNESS)

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the rgb color value [int, int, int]."""
        return apply_calibration(
            self._calibration_rgb,
            self._light_state.attributes.get(ATTR_RGB_COLOR),
            invert=True,
        )

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def is_on(self) -> bool:
        """Return true if light switch is on."""
        assert self._light_state is not None
        return self._light_state.state == STATE_ON

    @property
    def available(self) -> bool:
        """Return true if light switch is on."""
        return (
            self._light_state is not None
            and self._light_state.state != STATE_UNAVAILABLE
        )

    @property
    def should_poll(self) -> bool:
        """No polling needed for a light switch."""
        return False

    @property
    def unique_id(self):
        """Return the unique id of the light switch."""
        return self._unique_id + "_calibrated"

    @property
    def effect_list(self) -> list[str] | None:
        """Return the list of supported effects."""
        return self._light_state.attributes.get(ATTR_EFFECT_LIST)

    @property
    def effect(self) -> str | None:
        """Return the current effect."""
        return self._light_state.attributes.get(ATTR_EFFECT)

    async def async_turn_on(self, **kwargs):
        """Forward the turn_on command to the light."""
        data = {
            ATTR_ENTITY_ID: self._light_entity_id,
            **kwargs,
        }

        if light.ATTR_RGB_COLOR in data:
            data[light.ATTR_RGB_COLOR] = apply_calibration(
                self._calibration_rgb, data[light.ATTR_RGB_COLOR]
            )

        await self.hass.services.async_call(
            light.DOMAIN,
            light.SERVICE_TURN_ON,
            data,
            blocking=True,
            context=self._context,
        )

    async def async_turn_off(self, **kwargs):
        """Forward the turn_off command to the switch in this light switch."""
        data = {ATTR_ENTITY_ID: self._light_entity_id}
        await self.hass.services.async_call(
            light.DOMAIN,
            light.SERVICE_TURN_OFF,
            data,
            blocking=True,
            context=self._context,
        )

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self._light_state = self.hass.states.get(self._light_entity_id)

        @callback
        def async_state_changed_listener(*_: Any) -> None:
            """Handle child updates."""
            self._light_state = self.hass.states.get(self._light_entity_id)
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._light_entity_id], async_state_changed_listener
            )
        )
