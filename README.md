# BJ_LED

Home Assistant custom integration for BJ_LED devices controlled by the MohuanLED app over Bluetooth LE.

These were the cheapest Bluetooth controlled LEDs I could find on AliExpress.  5M of 5050 LEDs for £2.67.  The app is basic, but it works.  The IR remote is basic, but it works.  The lights connect to a USB port.

![image](https://github.com/8none1/bj_led/assets/6552931/686eff8b-ab87-4327-b784-ed91d695f957)

I figured it should be pretty easy to get them working, and it was.  I have no intention of adding this to HACS in any official capacity, but it should work when you add this repo as a custom repo in HACS.

There are some btsnoop HCI logs in the `bt_snoops` folder if you want to examine them.

## Bluetooth LE commands

`69 96 06 01 01`                 - On
`69 96 02 01 00`                 - Off

### Colours

```
|---------| -------------------- header
|         | ||------------------ red
|         | || ||--------------- green
|         | || || ||------------ blue
|         | || || || ||--------- white
69 96 05 02 7f 00 00 7f        - red
69 96 05 02 00 7f 00 7f        - green
69 96 05 02 00 00 7f 7f        - blue
69 96 05 02 ff ff ff ff        - white
```

In fact, you only need to provide RGB and can skip the last byte.  Since these strips don't have an white LED, it's easier to make sense of the shorter packet.

### Mode

```
|-----|------------------------- header
|     |     |------------------- mode
|     |     |  ||--------------- speed
69 96 03 03 02 01
69 96 03 03 01 01
```

Mode are numbered `00` to `15`.

Speed is 01 fast to 0a slow.  There are values accepted above this, but strange things happen.

## Supported devices

This has only been tested with a single generic LED strip from Ali Express.

It reports itself as `BJ_LED` over Bluetooth LE.  The app is called `MohuanLED`.
MAC address seem to start `FF:FF:xx:xx:xx:xx`.

## Supported Features in this integration

- On/Off
- RGB colour
- Brightness
- Fancy colour Modes (not speed)
- Automatic discovery of supported devices

## Not supported and not planned

- Microphone interactivity
- Timer / Clock functions
- Discovery of current light state

The timer/clock functions are understandable from the HCI Bluetooth logs but adding that functionality seems pointless and I don't think Home Assistant would support it any way.

The discovery of the light's state requires that the device be able to tell us what state it is in.  The BT controller on the device does report that it has `notify` capabilities but I have not been able to get it to report anything at all.  Perhaps you will have more luck.  Until this is solved, we have to use these lights in `optimistic` mode and assume everything just worked.  Looking at HCI logs from the Android app it doesn't even try to enable notifications and never receives a packet from the light.

## Installation

### Requirements

You need to have the bluetooth component configured and working in Home Assistant in order to use this integration.

### HACS

Add this repo to HACS as a custom repo.  Click through:

- HACS -> Integrations -> Top right menu -> Custom Repositories
- Paste the Github URL to this repo in to the Repository box
- Choose category `Integration`
- Click Add
- Restart Home Assistant
- BJ_LED devices should start to appear in your Integrations page

### Config

After setting up, you can config two parameters Settings -> Integrations -> BJ_LED -> Config.

## Credits

This integration was possible thanks to the work done by raulgbcr in this repo:

<https://github.com/raulgbcr/lednetwf_ble>

which in turn is thanks to:

<https://github.com/dave-code-ruiz/elkbledom> for most of the base code adapted to this integration.

## Other projects that might be of interest

- [iDotMatrix](https://github.com/8none1/idotmatrix)
- [Zengge LEDnet WF](https://github.com/8none1/zengge_lednetwf)
- [iDealLED](https://github.com/8none1/idealLED)
- [BJ_LED](https://github.com/8none1/bj_led)
- [ELK BLEDOB](https://github.com/8none1/elk-bledob)
- [HiLighting LED](https://github.com/8none1/hilighting_homeassistant)

