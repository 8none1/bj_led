import asyncio
from datetime import datetime
from homeassistant.components import bluetooth
from homeassistant.exceptions import ConfigEntryNotReady

from bleak.backends.device import BLEDevice
from bleak.backends.service import BleakGATTCharacteristic, BleakGATTServiceCollection
from bleak.exc import BleakDBusError
from bleak_retry_connector import BLEAK_RETRY_EXCEPTIONS as BLEAK_EXCEPTIONS
from bleak_retry_connector import (
    BleakClientWithServiceCache,
    BleakError,
    BleakNotFoundError,
    ble_device_has_changed,
    establish_connection,
)
from typing import Any, TypeVar, cast, Tuple
from collections.abc import Callable
import traceback
import asyncio
import logging

LOGGER = logging.getLogger(__name__)

EFFECT_COLORLOOP = "colorloop"
EFFECT_RED_FADE = "red_fade"
EFFECT_GREEN_FADE = "green_fade"
EFFECT_BLUE_FADE = "blue_fade"
EFFECT_YELLOW_FADE = "yellow_fade"
EFFECT_CYAN_FADE = "cyan_fade"
EFFECT_PURPLE_FADE = "purple_fade"
EFFECT_WHITE_FADE = "white_fade"
EFFECT_RED_GREEN_BLUE_CROSS_FADE = "rgb_cross_fade"
EFFECT_RED_GREEN_CROSS_FADE = "rg_cross_fade"
EFFECT_RED_BLUE_CROSS_FADE = "rb_cross_fade"
EFFECT_GREEN_BLUE_CROSS_FADE = "gb_cross_fade"
EFFECT_COLORSTROBE = "colorstrobe"
EFFECT_RED_STROBE = "red_strobe"
EFFECT_GREEN_STROBE = "green_strobe"
EFFECT_BLUE_STROBE = "blue_strobe"
EFFECT_YELLOW_STROBE = "yellow_strobe"
EFFECT_CYAN_STROBE = "cyan_strobe"
EFFECT_PURPLE_STROBE = "purple_strobe"
EFFECT_WHITE_STROBE = "white_strobe"
EFFECT_CYCLE_RGB = "cycle_rgb"
EFFECT_CYCLE_SEVEN_COLORS = "cycle_seven_colors"
EFFECT_COLORJUMP = "colorjump"
EFFECT_CUSTOM = "custom"

EFFECT_MAP = {
    EFFECT_COLORLOOP:               0x00,
    EFFECT_RED_FADE:                0x01,
    EFFECT_GREEN_FADE:              0x02,
    EFFECT_BLUE_FADE:               0x03,
    EFFECT_YELLOW_FADE:             0x04,
    EFFECT_CYAN_FADE:               0x05,
    EFFECT_PURPLE_FADE:             0x06,
    EFFECT_WHITE_FADE:              0x07,
    EFFECT_RED_GREEN_CROSS_FADE:    0x08,
    EFFECT_RED_BLUE_CROSS_FADE:     0x09,
    EFFECT_GREEN_BLUE_CROSS_FADE:   0x0a,
    EFFECT_COLORSTROBE:             0x0c,
    EFFECT_RED_STROBE:              0x0d,
    EFFECT_GREEN_STROBE:            0x0e,
    EFFECT_BLUE_STROBE:             0x0f,
    EFFECT_YELLOW_STROBE:           0x10,
    EFFECT_CYAN_STROBE:             0x11,
    EFFECT_PURPLE_STROBE:           0x12,
    EFFECT_WHITE_STROBE:            0x13,
    EFFECT_COLORJUMP:               0x14,
}

EFFECT_LIST = sorted(EFFECT_MAP)
EFFECT_ID_NAME = {v: k for k, v in EFFECT_MAP.items()}


NAME_ARRAY = ["BJ_LED"]
WRITE_CHARACTERISTIC_UUIDS = ["0000ee01-0000-1000-8000-00805f9b34fb"]
TURN_ON_CMD  = [bytearray.fromhex("69 96 02 01 01")]
TURN_OFF_CMD = [bytearray.fromhex("69 96 02 01 00")]
DEFAULT_ATTEMPTS = 3
BLEAK_BACKOFF_TIME = 0.25
RETRY_BACKOFF_EXCEPTIONS = (BleakDBusError,)
WrapFuncType = TypeVar("WrapFuncType", bound=Callable[..., Any])

def retry_bluetooth_connection_error(func: WrapFuncType) -> WrapFuncType:
    async def _async_wrap_retry_bluetooth_connection_error(
        self: "BJLEDInstance", *args: Any, **kwargs: Any
    ) -> Any:
        attempts = DEFAULT_ATTEMPTS
        max_attempts = attempts - 1

        for attempt in range(attempts):
            try:
                return await func(self, *args, **kwargs)
            except BleakNotFoundError:
                # The lock cannot be found so there is no
                # point in retrying.
                raise
            except RETRY_BACKOFF_EXCEPTIONS as err:
                if attempt >= max_attempts:
                    LOGGER.debug("%s: %s error calling %s, reach max attempts (%s/%s)",self.name,type(err),func,attempt,max_attempts,exc_info=True,)
                    raise
                LOGGER.debug("%s: %s error calling %s, backing off %ss, retrying (%s/%s)...",self.name,type(err),func,BLEAK_BACKOFF_TIME,attempt,max_attempts,exc_info=True,)
                await asyncio.sleep(BLEAK_BACKOFF_TIME)
            except BLEAK_EXCEPTIONS as err:
                if attempt >= max_attempts:
                    LOGGER.debug("%s: %s error calling %s, reach max attempts (%s/%s): %s",self.name,type(err),func,attempt,max_attempts,err,exc_info=True,)
                    raise
                LOGGER.debug("%s: %s error calling %s, retrying  (%s/%s)...: %s",self.name,type(err),func,attempt,max_attempts,err,exc_info=True,)

    return cast(WrapFuncType, _async_wrap_retry_bluetooth_connection_error)

class BJLEDInstance:
    def __init__(self, address, reset: bool, delay: int, hass) -> None:
        self.loop = asyncio.get_running_loop()
        self._mac = address
        self._reset = reset
        self._delay = delay
        self._hass = hass
        self._device: BLEDevice | None = None
        self._device = bluetooth.async_ble_device_from_address(self._hass, address)
        if not self._device:
            raise ConfigEntryNotReady(f"You need to add bluetooth integration (https://www.home-assistant.io/integrations/bluetooth) or couldn't find a nearby device with address: {address}")
        self._connect_lock: asyncio.Lock = asyncio.Lock()
        self._client: BleakClientWithServiceCache | None = None
        self._disconnect_timer: asyncio.TimerHandle | None = None
        self._cached_services: BleakGATTServiceCollection | None = None
        self._expected_disconnect = False
        self._is_on = None
        self._rgb_color = None
        self._brightness = None
        self._effect = None
        self._effect_speed = None
        self._write_uuid = None
        self._turn_on_cmd = None
        self._turn_off_cmd = None
        self._model = self._detect_model()
        LOGGER.debug('Model information for device %s : ModelNo %s, Turn on cmd %s, Turn off cmd %s', self._device.name, self._model, self._turn_on_cmd, self._turn_off_cmd)

    def _detect_model(self):
        x = 0
        for name in NAME_ARRAY:
            if self._device.name.lower().startswith(name.lower()):
                self._turn_on_cmd = TURN_ON_CMD[x]
                self._turn_off_cmd = TURN_OFF_CMD[x]
                return x
            x = x + 1
        
    async def _write(self, data: bytearray):
        """Send command to device and read response."""
        await self._ensure_connected()
        await self._write_while_connected(data)

    async def _write_while_connected(self, data: bytearray):
        LOGGER.debug(''.join(format(x, ' 03x') for x in data))
        await self._client.write_gatt_char(self._write_uuid, data, False)

    @property
    def mac(self):
        return self._device.address

    @property
    def reset(self):
        return self._reset

    @property
    def name(self):
        return self._device.name

    @property
    def rssi(self):
        return self._device.rssi

    @property
    def is_on(self):
        return self._is_on

    @property
    def brightness(self):
        return self._brightness

    @property
    def rgb_color(self):
        return self._rgb_color

    @property
    def effect_list(self) -> list[str]:
        return EFFECT_LIST
    
    @property
    def effect(self):
        # This might need to return a string of the effect name?
        return self._effect
    
    @retry_bluetooth_connection_error
    async def set_rgb_color(self, rgb: Tuple[int, int, int], brightness: int | None = None):
        self._rgb_color = rgb
        if brightness is None:
            if self._brightness is None:
                self._brightness = 255
            else:
                brightness = self._brightness
        brightness_percent = int(brightness * 100 / 255)
        # Now adjust the RBG values to match the brightness
        red = int(rgb[0] * brightness_percent / 100)
        green = int(rgb[1] * brightness_percent / 100)
        blue = int(rgb[2] * brightness_percent / 100)
        # RGB packet
        rgb_packet = bytearray.fromhex("69 96 05 02")
        rgb_packet.append(red)
        rgb_packet.append(green)
        rgb_packet.append(blue)
        await self._write(rgb_packet)

    async def set_brightness_local(self, value: int):
        # 0 - 255, should convert automatically with the hex calls
        # call color temp or rgb functions to update
        self._brightness = value
        await self.set_rgb_color(self._rgb_color, value)

    @retry_bluetooth_connection_error
    async def turn_on(self):
        await self._write(self._turn_on_cmd)
        self._is_on = True
                
    @retry_bluetooth_connection_error
    async def turn_off(self):
        await self._write(self._turn_off_cmd)
        self._is_on = False

    @retry_bluetooth_connection_error
    async def set_effect(self, effect: str):
        if effect not in EFFECT_LIST:
            LOGGER.error("Effect %s not supported", effect)
            return
        self._effect = effect
        effect_packet = bytearray.fromhex("69 96 03 03")
        effect_id = EFFECT_MAP.get(effect)
        LOGGER.debug('Effect ID: %s', effect_id)
        LOGGER.debug('Effect name: %s', effect)
        effect_packet.append(effect_id)
        effect_packet.append(0x01) # FIXME: Need to support speed in here too
        await self._write(effect_packet)
    
    @retry_bluetooth_connection_error
    async def update(self):
        try:
            await self._ensure_connected()
            if(self._is_on is None):
                self._is_on = False
                self._brightness = 255
                self._rgb_color = (255, 0, 0)
        except (Exception) as error:
            self._is_on = False
            LOGGER.error("Error getting status: %s", error)
            track = traceback.format_exc()
            LOGGER.debug(track)

    async def _ensure_connected(self) -> None:
        """Ensure connection to device is established."""
        if self._connect_lock.locked():
            LOGGER.debug(
                "%s: Connection already in progress, waiting for it to complete",
                self.name
            )
        if self._client and self._client.is_connected:
            self._reset_disconnect_timer()
            return
        async with self._connect_lock:
            # Check again while holding the lock
            if self._client and self._client.is_connected:
                self._reset_disconnect_timer()
                return
            LOGGER.debug("%s: Connecting", self.name)
            client = await establish_connection(
                BleakClientWithServiceCache,
                self._device,
                self.name,
                self._disconnected,
                cached_services=self._cached_services,
                ble_device_callback=lambda: self._device,
            )
            LOGGER.debug("%s: Connected", self.name)
            resolved = self._resolve_characteristics(client.services)
            if not resolved:
                # Try to handle services failing to load
                resolved = self._resolve_characteristics(await client.get_services())
            self._cached_services = client.services if resolved else None

            self._client = client
            self._reset_disconnect_timer()

    def _resolve_characteristics(self, services: BleakGATTServiceCollection) -> bool:
        """Resolve characteristics."""
        for characteristic in WRITE_CHARACTERISTIC_UUIDS:
            if char := services.get_characteristic(characteristic):
                self._write_uuid = char
                break
        return bool(self._write_uuid)

    def _reset_disconnect_timer(self) -> None:
        """Reset disconnect timer."""
        if self._disconnect_timer:
            self._disconnect_timer.cancel()
        self._expected_disconnect = False
        if self._delay is not None and self._delay != 0:
            LOGGER.debug("%s: Configured disconnect from device in %s seconds", self.name, self._delay)
            self._disconnect_timer = self.loop.call_later(
                self._delay, self._disconnect
            )

    def _disconnected(self, client: BleakClientWithServiceCache) -> None:
        """Disconnected callback."""
        if self._expected_disconnect:
            LOGGER.debug("%s: Disconnected from device", self.name)
            return
        LOGGER.warning("%s: Device unexpectedly disconnected",self.name)

    def _disconnect(self) -> None:
        """Disconnect from device."""
        self._disconnect_timer = None
        asyncio.create_task(self._execute_timed_disconnect())

    async def stop(self) -> None:
        """Stop the LEDBLE."""
        LOGGER.debug("%s: Stop", self.name)
        await self._execute_disconnect()
        
    async def _execute_timed_disconnect(self) -> None:
        """Execute timed disconnection."""
        LOGGER.debug(
            "%s: Disconnecting after timeout of %s",
            self.name,
            self._delay,
        )
        await self._execute_disconnect()

    async def _execute_disconnect(self) -> None:
        """Execute disconnection."""
        async with self._connect_lock:
            read_char = self._read_uuid
            client = self._client
            self._expected_disconnect = True
            self._client = None
            self._write_uuid = None
            self._read_uuid = None
            if client and client.is_connected:
                await client.disconnect()
