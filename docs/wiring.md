# Pylontech Console Cable

This document describes the tested cable used to connect a Pylontech US2000C console port to the RS232 interface of a Waveshare serial device server.

> [!WARNING]
> The RJ45 console connector on the battery is **not Ethernet**. Do not connect it to an Ethernet switch, router, or network interface.

## Tested setup

- Battery: Pylontech US2000C
- Main software version: B67.5.0
- Serial device server: Waveshare RS232/485/422 TO POE ETH (B)
- Interface: RS232
- Serial settings: 115200 baud, 8 data bits, no parity, 1 stop bit, no flow control

The cable and settings were verified by successfully executing the console commands `help`, `info`, `pwr`, `bat`, `stat`, and `time`.

## Electrical pinout

### Pylontech console port (RJ45)

| RJ45 pin | Signal |
|---:|---|
| 3 | TX |
| 6 | RX |
| 8 | GND |

### Waveshare RS232 port (DB9)

| DB9 pin | Signal |
|---:|---|
| 2 | RX |
| 3 | TX |
| 5 | GND |

TX and RX must be crossed between the battery and the serial device server.

## Cable wiring

| Pylontech RJ45 pin | Pylontech signal | T568B wire colour | Waveshare DB9 pin | Waveshare signal |
|---:|---|---|---:|---|
| 3 | TX | White/Green | 2 | RX |
| 6 | RX | Green | 3 | TX |
| 8 | GND | Brown | 5 | GND |

The remaining five conductors are not connected.

```text
Pylontech US2000C                    Waveshare
RJ45 console                        DB9 RS232

Pin 3  TX   White/Green  ---------> Pin 2  RX
Pin 6  RX   Green        <--------- Pin 3  TX
Pin 8  GND  Brown        ---------- Pin 5  GND
```

## Tested physical build

A standard shielded CAT patch cable wired according to T568B was used:

1. Keep the factory-crimped RJ45 plug on one end.
2. Cut off the connector at the other end.
3. Identify the White/Green, Green, and Brown conductors.
4. Connect these three conductors to DB9 pins 2, 3, and 5 as shown above.
5. Insulate all unused conductors individually.
6. Leave the cable shield unconnected for the initial installation.

For the temporary test setup, individual female jumper contacts were fitted directly onto DB9 pins 2, 3, and 5.

## DB9 jumper colours used in the tested setup

The following additional jumper-wire colours were used on the Waveshare DB9 connector:

| Jumper colour | DB9 pin | Signal |
|---|---:|---|
| Orange | 2 | RX |
| Red | 3 | TX |
| Brown | 5 | GND |

This gives the complete tested connection:

| CAT cable conductor | DB9 jumper | Connection |
|---|---|---|
| White/Green | Orange | RJ45 pin 3 TX to DB9 pin 2 RX |
| Green | Red | RJ45 pin 6 RX to DB9 pin 3 TX |
| Brown | Brown | RJ45 pin 8 GND to DB9 pin 5 GND |

## RJ45 pin orientation

RJ45 numbering is easy to mirror accidentally. When looking directly at the gold contacts of the plug, with the latch on the opposite side, pins are counted from left to right:

```text
Gold contacts facing the viewer

┌─────────────────┐
│ 1 2 3 4 5 6 7 8 │
└─────────────────┘

Latch on the rear side
```

For a standard T568B cable, the conductor colours are:

| Pin | Colour |
|---:|---|
| 1 | White/Orange |
| 2 | Orange |
| 3 | White/Green |
| 4 | Blue |
| 5 | White/Blue |
| 6 | Green |
| 7 | White/Brown |
| 8 | Brown |

## Verification before connection

Before connecting the cable to the battery:

1. Verify continuity from RJ45 pin 3 to DB9 pin 2.
2. Verify continuity from RJ45 pin 6 to DB9 pin 3.
3. Verify continuity from RJ45 pin 8 to DB9 pin 5.
4. Verify that none of these three conductors is shorted to another conductor or to the shield.
5. Verify that the Waveshare interface is configured for RS232, not RS485 or RS422.

## Shield connection

The tested cable shield was left unconnected. For a short cable in this application, only TX, RX, and GND are required.

If electromagnetic interference later becomes a problem, connect the shield at one end only to chassis or connector shell, not automatically to DB9 signal ground pin 5. This avoids creating an unintended ground loop.
