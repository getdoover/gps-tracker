# GPS Tracker

<img src="https://doover.com/wp-content/uploads/Doover-Logo-Landscape-Navy-padded-small.png" alt="App Icon" style="max-width: 300px;">

**Puts a device on the Doover map from the raw GPS fields in its messages**

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/getdoover/gps-tracker/blob/main/LICENSE)

[Overview](#overview) • [Configuration](#configuration) • [Tags](#tags) • [Channels](#channels) • [Need Help?](#need-help)

<br/>

## Overview

GPS Tracker is a cloud processor. Whatever sends a device's GPS readings to Doover (a Doovit
app, a LoRaWAN node, a telemetry gateway), this app reads the latitude, longitude and
quality fields out of those messages and turns them into:

- **the device's location** on its device page and on the organisation map, with a location
  history track;
- **position tags** (latitude, longitude, altitude, satellites, HDOP, fix status, last fix
  time) that other apps on the device can read;
- an optional **bearing and distance from a reference point**, such as a pivot centre, a
  hub or a home yard, for pivots and any other radial or tethered machine;
- an optional **notification** when the device moves further than a set distance from that
  reference point.

It is read-only: it never sends anything to the device.

Fixes that are not good enough are ignored rather than plotted: a receiver reporting no fix,
a 0,0 position, or (when configured) too few satellites or too high an HDOP. The last good
position stays on the map, and the page shows why the latest reading was set aside.

<br/>

## Configuration

Every input is a **message path**, `$<channel>.<path.to.value>`, read from messages on the
subscribed channels. Nested values use dots (`$io_state.gps.lat`), list items their index
(`$io_state.fixes.0.lat`). Latitude and longitude must be on the same channel; an optional
field is only read from that same message, and clearing an optional path turns it off.

| Setting | Key | Description | Default |
|---------|-----|-------------|---------|
| **Latitude Message Path** | `latitude_path` | Latitude, decimal degrees | `$io_state.latitude` |
| **Longitude Message Path** | `longitude_path` | Longitude, decimal degrees | `$io_state.longitude` |
| **Altitude Message Path** | `altitude_path` | Altitude, metres (optional) | `$io_state.altitude` |
| **Satellites Message Path** | `satellites_path` | Satellites in use (optional) | `$io_state.satellites` |
| **HDOP Message Path** | `hdop_path` | Horizontal dilution of precision (optional) | `$io_state.hdop` |
| **Fix Status Message Path** | `fix_status_path` | Fix status (optional): `true`/`false`, a fix quality number where 0 is no fix, or text such as `3D`, `A`, `no fix`, `V` | `$io_state.gps_fix` |
| **GPS Time Message Path** | `gps_time_path` | Time of the fix (optional): epoch seconds or milliseconds, or ISO 8601. Without it, the arrival time is used | `$io_state.gps_time` |
| **Minimum Satellites** | `min_satellites` | Ignore fixes from fewer satellites. Empty for no minimum | empty |
| **Maximum HDOP** | `max_hdop` | Ignore fixes with a higher HDOP, e.g. `5.0`. Empty for no maximum | empty |
| **Reference Latitude** | `reference_latitude` | Latitude of the reference point, decimal degrees | empty |
| **Reference Longitude** | `reference_longitude` | Longitude of the reference point, decimal degrees | empty |
| **Bearing Offset** | `bearing_offset_deg` | Degrees added to the bearing, to line it up with a machine's own zero | `0.0` |
| **Notify When Moved Away** | `notify_on_move` | Send a notification when a good fix is beyond the alert distance from the reference point | `false` |
| **Alert Distance** | `move_alert_distance_m` | Metres from the reference point beyond which the notification is sent | `500.0` |
| **Location Update Distance** *(advanced)* | `location_min_move_m` | Only update the map location when a fix has moved at least this many metres from the last one published, so jitter on a parked machine does not fill its track. `0` publishes every good fix | `2.0` |
| **Subscription** *(advanced)* | `dv_proc_subscriptions` | Channels whose messages invoke the processor | `["io_state"]` |

The minimum-satellites and maximum-HDOP checks apply only when the source sends that value.

### Bearing from a reference point

With both reference coordinates set, every good fix also publishes:

- `bearing_deg`: the direction from the reference point to the device, 0° = true North,
  increasing clockwise (90° East, 180° South, 270° West), plus the Bearing Offset, always in
  the range 0 to 360;
- `distance_m`: the great-circle distance from the reference point, in metres.

On a centre pivot with the receiver on the end tower and the reference point at the pivot
centre, `bearing_deg` is the pivot's angle. Set the Bearing Offset if the pivot's own 0° is
not North. While no reference point is set, neither tag is published and the page hides
them.

<br/>

## Tags

| Tag | Type | Description |
|-----|------|-------------|
| `latitude` | number | Last good latitude, decimal degrees |
| `longitude` | number | Last good longitude, decimal degrees |
| `altitude` | number | Last good altitude, metres |
| `satellites` | number | Satellites in use, from the latest reading |
| `hdop` | number | HDOP, from the latest reading |
| `fix_ok` | boolean | Whether the latest reading was a usable fix |
| `last_fix_ts` | number | Time of the last good fix, ms since the epoch |
| `bearing_deg` | number | Bearing from the reference point (0 = North, clockwise, plus offset) |
| `distance_m` | number | Distance from the reference point, metres |
| `fix_quality` | string | Summary of the latest reading, e.g. `Good (9 satellites, HDOP 0.9)` or `Ignored: HDOP 7 (maximum 5)` |

Other apps on the same device read these as `{app_key}` / `{tag_name}`, for example a pivot
app reading `bearing_deg` from this app's install. Until a first good fix arrives every
tag is empty and the page shows no reading.

<br/>

## Channels

### Input

Messages on the subscribed channels (default `io_state`). Only the channel named in the
latitude and longitude paths is read; a message without GPS fields is passed over.

### Output: location

The device's position is published the way Doover's location apps (Location Manager,
Digital Matter Device, Agbot Device) publish it, on the device's **`location`** channel:

- the channel **aggregate** is replaced with the current position. The Doover site reads
  it to place the device on its device page and the organisation map;
- a **message** with the same body is added for each published position. These messages
  are the device's location history, drawn as its track on the map.

```json
{"lat": -27.5, "long": 151.9, "alt": 410.2, "satellites": 9, "hdop": 0.9}
```

`lat` and `long` (decimal degrees) are what the map reads. `alt`, `satellites` and `hdop`
are included when the source sends them. A device should have one app publishing to
`location`, so leave Location Manager off a device that runs GPS Tracker.

### Notification

| Notification | Severity | When |
|--------------|----------|------|
| Moved away from reference point | Warn | Notify When Moved Away is on and a good fix is further than the Alert Distance from the reference point. Sent once each time it moves out; it re-arms when a fix is back inside |

It never fires from missing data or an ignored fix.

<br/>

## Need Help?

- Email: support@doover.com
- [Doover Documentation](https://docs.doover.com)
