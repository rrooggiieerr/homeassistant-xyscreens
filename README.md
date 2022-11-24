Home Assistant XY Screens integration
=
Home Assistant integration to controll XY Screens projector screens and projector lifts over the RS485 interface.
I use a cheap USB RS485 controler from eBay to talk to the projector screen.

XY Screens is an OEM manufacturer of projector screen and projector lifts.

Known to work:\
iVisions Electro M Series

Not tested but uses the same protocol according to the documentation:\
iVisions Electro L/XL/Pro/HD Series\
iVisions PL Series projector lift\
Elite Screens\
KIMEX\
DELUXX

Please let me know if your projector screen or projector lift works with this integration so I can improve the overview of supported devices.

Caution
==
This integration follows the Cover Entity where open means retracting the screen and close opens the screen, like how rolling blinds, garage doors and curtains work. For a projector screen this is counter intuitive.

Installation
=
* Create a directory named xyscreens in the custom_components directory of your Home Assistant installation.
* Copy the contents of this repository in the xyscreens directory

or

* SSH to the custom_components directory of your Home Assistant installation
* Execute 'git clone https://github.com/rrooggiieerr/homeassistant-xyscreens.git xyscreens'