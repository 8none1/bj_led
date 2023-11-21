# BJ_LED

Home Assistant custom integration for BJ LED devices which are not supported on the official LED BLE integration or Flux LED.


## Supported devices

This has only been tested with a single generic LED strip from Ali Express.

It reports itself as `BJ_LED` over Bluetooth LE.  The app is called `MohuanLED`.
MAC address seem to start `FF:FF:xx:xx:xx:xx`.

## Supported Features in this integration

- On/Off
- RGB colour
- Brightness
- Fancy colour Modes (not speed)

## Not yet supported but planned
- Automatic discovery of supported devices

## Not supported and not currently planned

- Microphone interactivity
- Timer / Clock functions
- Discovery of current light state

The timer/clock functions are understandable from the HCI Bluetooth logs but adding that functionality seems pointless and I don't think Home Assistant would support it any way.

The discovery of the light's state requires that the device be able to tell us what state it is in.  The BT controller on the device does report that it has `notify` capabilities but I have not been able to get it to report anything at all.  Perhaps you will have more luck.  Until this is solved, we have to use these lights in `optimistic` mode and assume everything just worked.  Looking at HCI logs from the Android app it doesn't even try to enable notifications and never receives a packet from the light.

## Installation

### Requirements

You need to have the bluetooth component configured and working in Home Assistant in order to use this integration.

### Manual installation

Clone this repository into `config/custom_components/BJ_LED` Home Assistant folder.

### Config
After setting up, you can config two parameters Settings -> Integrations -> BJ_LED -> Config.


## Credits

This integration was possible thanks to the work done by raulgbcr in this repo:

https://github.com/raulgbcr/lednetwf_ble

which in turn is thanks to:

https://github.com/dave-code-ruiz/elkbledom for most of the base code adapted to this integration.
