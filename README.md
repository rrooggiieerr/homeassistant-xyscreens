# Home Assistant XY Screens integration
Home Assistant integration to control XY Screens projector screens and
projector lifts over the RS-485 interface.

[<img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" >](https://www.buymeacoffee.com/rrooggiieerr)

XY Screens is an OEM manufacturer of projector screens and projector lifts.

## Hardware
I use a cheap USB RS-485 controler from eBay to talk to the projector screen
where position 5 of the RJ25 connector is connected to D+ and position 6 to
the D-.

See the documentation of your specific device on how to wire yours correctly.

## Known to work
* iVisions Electro M Series

Not tested but uses the same protocol according to the documentation:
* iVisions Electro L/XL/Pro/HD Series
* iVisions PL Series projector lift
* Elite Screens
* KIMEX
* DELUXX

Please let me know if your projector screen or projector lift works with this
integration so I can improve the overview of supported devices.

## Caution
This integration follows the Cover Entity where open means retracting the
screen and close opens the screen, like how rolling blinds, garage doors and
curtains work. For a projector screen this is counter intuitive.

## Installation
* Copy the `custom_components/xyscreens` directory of this repository into the
`config/custom_components/` directory of you Home Assistant installation 
