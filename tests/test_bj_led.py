"""Tests for the BJ_LED stale-connection fix, run against HA's real config-entry machinery."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bleak.backends.device import BLEDevice
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from pytest_homeassistant_custom_component.common import MockConfigEntry

import custom_components.bj_led.bjled  # noqa: F401,E402  (ensure module loaded for patching)

DOMAIN = "bj_led"
MAC = "FF:FF:10:B0:F9:68"
BLE_DEVICE = BLEDevice(MAC, "BJ_LED", {})


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture(autouse=True)
def fake_bluetooth(hass: HomeAssistant):
    # Pretend the bluetooth integration is loaded and the device is in range.
    hass.config.components.add("bluetooth")
    with patch(
        "custom_components.bj_led.bjled.bluetooth.async_ble_device_from_address",
        return_value=BLE_DEVICE,
    ):
        yield


def make_entry(hass, options=None, data_extra=None):
    data = {"mac": MAC, "name": "BJ_LED (F968)"}
    data.update(data_extra or {})
    entry = MockConfigEntry(domain=DOMAIN, unique_id=MAC, title="BJ_LED (F968)", data=data, options=options or {})
    entry.add_to_hass(hass)
    return entry


async def setup(hass, entry):
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    return hass.data[DOMAIN][entry.entry_id]


# --- disconnect delay resolution -------------------------------------------

async def test_default_delay_when_unset(hass):
    """Existing installs (no delay stored anywhere) now get a 120 s idle disconnect."""
    inst = await setup(hass, make_entry(hass))
    assert inst._delay == 120


async def test_explicit_zero_means_never_disconnect(hass):
    inst = await setup(hass, make_entry(hass, options={"reset": False, "delay": 0}))
    assert inst._delay == 0


async def test_explicit_option_respected(hass):
    inst = await setup(hass, make_entry(hass, options={"reset": False, "delay": 30}))
    assert inst._delay == 30


async def test_delay_in_entry_data_respected(hass):
    inst = await setup(hass, make_entry(hass, data_extra={"delay": 45}))
    assert inst._delay == 45


# --- options flow ---------------------------------------------------------

async def test_options_flow_opens_and_saves_and_reloads(hass):
    entry = make_entry(hass)
    inst_before = await setup(hass, entry)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    # Default shown in the form is 120
    schema = result["data_schema"].schema
    key = next(k for k in schema if k == "delay")
    assert key.default() == 120

    result = await hass.config_entries.options.async_configure(result["flow_id"], {"delay": 60})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert dict(entry.options) == {"reset": False, "delay": 60}

    # The entry was reloaded, so a new instance with the new delay is live
    inst_after = hass.data[DOMAIN][entry.entry_id]
    assert inst_after is not inst_before
    assert inst_after._delay == 60
    assert entry.state is ConfigEntryState.LOADED


async def test_options_flow_rejects_negative(hass):
    entry = make_entry(hass)
    await setup(hass, entry)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    with pytest.raises(InvalidData):
        await hass.config_entries.options.async_configure(result["flow_id"], {"delay": -5})


# --- connection lifecycle -------------------------------------------------

def fake_client():
    client = MagicMock()
    client.is_connected = True
    client.write_gatt_char = AsyncMock()

    async def _disconnect():
        client.is_connected = False

    client.disconnect = AsyncMock(side_effect=_disconnect)
    client.services.get_characteristic.return_value = "ee01-char"
    return client


async def test_idle_disconnect_then_fresh_reconnect(hass):
    """After the idle delay the link is closed; the next command opens a new one."""
    inst = await setup(hass, make_entry(hass))
    inst._delay = 0.2  # shorten for the test; same code path as 120 s

    clients = []

    async def _establish(*args, **kwargs):
        c = fake_client()
        clients.append(c)
        return c

    with patch("custom_components.bj_led.bjled.establish_connection", side_effect=_establish):
        await inst.turn_off()
        assert len(clients) == 1
        clients[0].write_gatt_char.assert_awaited_once()
        assert clients[0].write_gatt_char.await_args.args[1] == bytearray.fromhex("69 96 02 01 00")

        # Commands inside the idle window reuse the same connection
        await inst.turn_on()
        assert len(clients) == 1

        await asyncio.sleep(0.5)
        await hass.async_block_till_done()
        clients[0].disconnect.assert_awaited_once()
        assert inst._client is None

        # Next command after idle -> brand-new connection
        await inst.turn_on()
        assert len(clients) == 2
        assert clients[1].write_gatt_char.await_args.args[1] == bytearray.fromhex("69 96 02 01 01")
        await inst.stop()


async def test_zero_delay_keeps_connection(hass):
    inst = await setup(hass, make_entry(hass, options={"reset": False, "delay": 0}))
    clients = []

    async def _establish(*args, **kwargs):
        c = fake_client()
        clients.append(c)
        return c

    with patch("custom_components.bj_led.bjled.establish_connection", side_effect=_establish):
        await inst.turn_off()
        assert inst._disconnect_timer is None
        await asyncio.sleep(0.3)
        clients[0].disconnect.assert_not_awaited()
        await inst.turn_on()
        assert len(clients) == 1
        await inst.stop()
