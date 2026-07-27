# NorthTracker API Documentation

This document describes the NorthTracker cloud API used by this Home Assistant integration.
It is intended to help AI assistants (like Claude) understand the backend API structure for future development.

## Base URL

```
https://apiv2.northtracker.com/api/v1
```

## Authentication

All requests (except login) require a Bearer token in the Authorization header:

```
Authorization: Bearer <token>
```

### POST /login

Authenticate and obtain an access token.

**Request:**
```json
{
  "username": "user@example.com",
  "password": "password",
  "subsiteid": "0",
  "remember_me": false
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "checkindata": [],
    "user": {
      "ID": 12345,
      "Email": "user@example.com",
      "FullName": "User Name",
      "DepartmentID": 0,
      "ParentID": 12344,
      "administrator": true,
      "userGroup": [
        {"GroupID": 7, "GroupName": "Kontoadministratörer"},
        {"GroupID": 4, "GroupName": "User"}
      ],
      "token": "123456|xXxXxXxXxXxXxXxXxXxXxXxXxXxXxXxXxXxXxXxXxXxXxXxX",
      "userHasOnlyBasSubscription": true
    }
  }
}
```

The `token` field is used for all subsequent API calls.

---

## Device/Terminal Endpoints

### GET /user/terminal/list

Get a simple list of all terminals (devices) for the user.

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "ID": 12345,
      "Name": "My Boat",
      "Imei": "123456789012345",
      "device_type": "gps"
    },
    {
      "ID": 1001,
      "ClassName": "BltUnit",
      "SerialNumber": "AABBCCDDEEFF",
      "Imei": "AABBCCDDEEFF",
      "Name": "My Boat Engine Room",
      "device_type": "bluetooth"
    }
  ]
}
```

**Device Types:**
- `gps` - GPS tracker device
- `bluetooth` - BLE sensor (temperature, humidity, etc.)

---

### GET /user/terminal/get-units

Get detailed list of all GPS units with their current state.

**Query Parameters:**
- `page` (optional): Page number for pagination

**Response:**
```json
{
  "success": true,
  "data": {
    "current_page": 1,
    "data": [
      {
        "ID": 12345,
        "NameOnly": "My Boat",
        "SubscriptionType": "Bas",
        "Imei": "123456789012345",
        "GpsModel": "Machine Connect",
        "VehicleType": "boat",
        "RegNr": null,
        "Symbol": "terminalmarkericon-motor-powered-boat",
        "BleEnabled": 1,
        "LastSeen": "2026-02-02 14:00:05",
        "Battery": "14.4V",
        "BatteryVoltage": "14400",
        "Odometer": 372.625,
        "GPS": 0,
        "Dout1Status": 0,
        "Dout2Status": null,
        "Dout3Status": null,
        "Din2Status": 0,
        "Din3Status": 0,
        "Model": "FMC130",
        "WorkingHours": "Manual",
        "GreenDriving": "Off",
        "OverSpeeding": "Off",
        "tags": [],
        "projects": []
      }
    ],
    "last_page": 1,
    "total": 1
  }
}
```

**Important Fields:**
- `ID` - Terminal ID used in other API calls
- `Imei` - Device IMEI, unique identifier
- `Model` - Device model (e.g., "FMC130")
- `VehicleType` - Type: "car", "boat", "motorcycle", etc.
- `Dout1Status`, `Dout2Status`, `Dout3Status` - Digital output states (0=off, 1=on)
- `Din2Status`, `Din3Status` - Digital input states
- `BleEnabled` - Whether Bluetooth sensors are enabled

---

### POST /user/terminal/edit-terminal

Get detailed information for a specific terminal.

**Request:**
```json
{
  "device_type": "gps",
  "device_id": 12345
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "terminal": {
      "ID": 12345,
      "OwnerID": 12344,
      "Name": "My Boat",
      "Imei": "123456789012345",
      "Color": "2d7484",
      "MapIconSymbol": "terminalmarkericon-motor-powered-boat",
      "Model": "FMC130",
      "AzimuthEnabled": 0,
      "SubscriptionType": "Bas",
      "IsCompanyCar": 0,
      "ReportFrequency": 240,
      "VehicleType": "boat",
      "IsSpeedInKnots": 0,
      "BluetoothStatus": true,
      "isFMTracker": true
    },
    "DINsettings": [
      {
        "ID": 1001,
        "TerminalID": 12345,
        "ShowDINBtnTwo": 1,
        "ShowDINBtnThree": 1,
        "DINTwoBtnLabel": "DIN 2",
        "DINThreeBtnLabel": "Din 3",
        "DINTwoValue": 0,
        "DINThreeValue": 0
      }
    ],
    "relaySettings": [
      {
        "ID": 1002,
        "TerminalID": 12345,
        "ShowDoutBtnOne": 1,
        "ShowDoutBtnTwo": 1,
        "ShowDoutBtnThree": 1,
        "DoutBtnLabelOne": "Refrigerator",
        "DoutBtnLabelTwo": "DOUT 2 on/off",
        "DoutBtnLabelThree": "DOUT 3 on/off",
        "DoutValueOne": 0,
        "DoutValueTwo": 0,
        "DoutValueThree": 0,
        "DoutOneAckStatus": 1,
        "DoutTwoAckStatus": 1,
        "DoutThreeAckStatus": 1
      }
    ],
    "SosAlarmEnabled": true,
    "AccountHasSensors": true
  }
}
```

**Relay Settings:**
- `DoutValueOne/Two/Three` - Current state of digital outputs (0=off, 1=on)
- `DoutBtnLabelOne/Two/Three` - User-configured labels for outputs
- `DoutOneAckStatus` - Acknowledgment status (1=acknowledged)

---

## Real-Time Tracking

### GET /user/realtimetracking/latest-units-data

Get real-time GPS data for all devices.

**Query Parameters:**
- `lang` (optional): Language code (e.g., "sv", "en")
- `page` (optional): Page number
- `only_marker_detail` (optional): 0 or 1

**Response:**
```json
{
  "success": true,
  "data": {
    "gps": {
      "current_page": 1,
      "data": [
        {
          "ID": 12345,
          "Imei": "123456789012345",
          "Name": "My Boat",
          "Model": "FMC130",
          "Color": "2d7484",
          "MapIconSymbol": "terminalmarkericon-motor-powered-boat",
          "VehicleType": "boat",
          "Latitude": "59.0000000",
          "Longitude": "13.0000000",
          "Send_Time": "2026-02-02 14:00:05",
          "Speed": 0,
          "Azimuth": "0.0",
          "GPS_accuracy": 0,
          "Battery_percentage": 100,
          "BatteryVoltage": "14400",
          "NetworkQuality": 4,
          "Command": "GTFRI",
          "IsParked": true,
          "HasPosition": true,
          "IsTeltonika4G": true,
          "BatteryPercentage": "14.4V",
          "ModelType": "FM",
          "ReportFrequencyReadable": "Stopp: 4 min",
          "PairedSensors": [
            {
              "SerialNumber": "AABBCCDDEEFF",
              "PairedSlot": "1",
              "Imei": "123456789012345",
              "latest_sensor_data": {
                "SerialNumber": "AABBCCDDEEFF",
                "Send_Time": "2026-02-02 14:00:05",
                "Temperature": "-3.40",
                "Humidity": "70",
                "MagneticField": true,
                "BatteryVoltage": "2800"
              }
            }
          ]
        }
      ]
    }
  }
}
```

**GPS Data Fields:**
- `Latitude`, `Longitude` - GPS coordinates
- `Send_Time` - Timestamp of last data (format: "YYYY-MM-DD HH:MM:SS")
- `Speed` - Current speed
- `Azimuth` - Direction/heading in degrees
- `Battery_percentage` - Battery percentage (0-100)
- `BatteryVoltage` - Battery voltage in millivolts (e.g., "14400" = 14.4V)
- `NetworkQuality` - Cellular signal quality (0-5)
- `IsParked` - Whether device is stationary
- `Command` - Last command type (e.g., "GTFRI")

**Paired Sensors (Bluetooth):**
- `Temperature` - Temperature reading in Celsius
- `Humidity` - Humidity percentage
- `MagneticField` - Magnetic field detected (door sensor)
- `BatteryVoltage` - Sensor battery in millivolts

---

### GET /user/realtimetracking/get

**Removed by NorthTracker (confirmed 2026-07-27).** The route still exists but the
controller behind it crashes, so it answers `500 Server Error` with an HTML body for
every request. The web client no longer calls it. Use
`/user/realtimetracking/latest-units-data` instead; it returns the same unit payload,
but `data.gps` is a paginated object rather than a plain list.

---

## Device Control Commands

> **Not used by this integration.** The integration is read-only: it never writes to
> the API. These endpoints are documented for reference only, and the two `sendmsg`
> ones below appear to be legacy - the web client uses
> `relaysetting/sendmsg-collection` and `dout-control-via-din` instead
> (see "Write endpoints used by the web client").

### POST /user/terminal/relaysetting/sendmsg

Control digital outputs (relays) on the device.

**Request (Turn On):**
```json
{
  "terminal_id": 12345,
  "output_number": 1,
  "value": 1
}
```

**Request (Turn Off):**
```json
{
  "terminal_id": 12345,
  "output_number": 1,
  "value": 0
}
```

**Parameters:**
- `terminal_id` - Device ID
- `output_number` - Output number (1, 2, or 3)
- `value` - 0 (off) or 1 (on)

---

### POST /user/terminal/dinsetting/sendmsg

Control or configure digital inputs.

**Request:**
```json
{
  "terminal_id": 12345,
  "input_number": 2,
  "value": 1
}
```

---

### GET /user/terminal/relaysetting/check-ack

Check if a relay command has been acknowledged by the device.

**Query Parameters:**
- `terminal_id` - Device ID
- `output_number` - Output number

**Response:**
```json
{
  "success": true,
  "data": {
    "remaining_waiting_time": null,
    "msg": "NothingInQueue"
  }
}
```

---

### GET /user/terminal/relaysetting/check-ack-collection

Check acknowledgment status for all pending commands.

**Response:**
```json
{
  "success": true,
  "data": {
    "remaining_waiting_time": null,
    "msg": "NothingInQueue"
  }
}
```

Possible messages:
- `NothingInQueue` - No pending commands
- `CommandAcknowledged` - Command received by device
- `WaitingForAck` - Still waiting for acknowledgment

---

## Device Features & Settings

### POST /user/terminal/get-unit-features

Get configurable features for a device.

**Request:**
```json
{
  "Imei": "123456789012345"
}
```

---

### POST /user/terminal/enable-features

Update device features and settings.

**Request:**
```json
{
  "Imeis": ["123456789012345"],
  "Settings": {
    "ID": "",
    "ProfileName": "",
    "ProfileDescription": "",
    "TripType": "",
    "TripTypeSettings": {
      "default_trip": 0,
      "private_trip": 0,
      "onmap_during_workinghour": 0,
      "businessTripDays": ""
    },
    "CarBenefitSettings": {
      "benefit_type": "",
      "fuel_consumption_company": "",
      "vehicle_type": "",
      "currency": "",
      "fuel_consumption_private": ""
    },
    "CarBenefitEnabled": false,
    "GreenDrivingSensitivity": "",
    "OverspeedingThreshold": "",
    "SaveConfiguration": false,
    "GreenDrivingEnabled": false,
    "OverSpeedingEnabled": false,
    "WorkingHoursEnabled": false,
    "FromApp": "false",
    "SaveCarBenefit": false,
    "SaveWorkingHours": false,
    "SendEcoDrivingCommand": false,
    "SendOverspeedingCommand": false,
    "IsKorjournalUnit": false,
    "LowBatteryAlertEnabled": 1,
    "LowBatteryThreshold": "20",
    "SendLowBatteryCommand": true
  }
}
```

**Key Settings:**
- `LowBatteryAlertEnabled` - 0/1 to enable low battery alerts
- `LowBatteryThreshold` - Percentage threshold for alerts
- `GreenDrivingEnabled` - Enable eco-driving monitoring
- `OverSpeedingEnabled` - Enable overspeed alerts
- `OverspeedingThreshold` - Speed limit for alerts

---

## Geofence Endpoints

### GET /user/geofence/get/list

Get all geofences for the user.

**Response:**
```json
{
  "success": true,
  "data": {
    "hasYabbyOrScout": false,
    "geofences": [
      {
        "ID": 10001,
        "Name": "Office",
        "Radius": 300,
        "LastState": "in",
        "CenterLat": "59.000000",
        "CenterLon": "13.000000",
        "CheckInterval": 300,
        "Place": 1,
        "Color": "2b90d9",
        "TerminalID": 12345,
        "Status": "1",
        "SendOn": "in/out",
        "GroupIdentifier": "abc123def456abc1",
        "unitsCount": 1
      }
    ]
  }
}
```

**Geofence Fields:**
- `Radius` - Radius in meters
- `LastState` - Current state: "in" or "out"
- `CenterLat`, `CenterLon` - Center coordinates
- `CheckInterval` - Check interval in seconds
- `Status` - "1" = active, "0" = inactive
- `SendOn` - Alert trigger: "in", "out", or "in/out"

---

### POST /user/geofence/state/group-update

Enable or disable a geofence.

**Request:**
```json
{
  "status": "0",
  "geofence_id": 10002,
  "group_identifier": "def456abc123def4"
}
```

**Parameters:**
- `status` - "1" to enable, "0" to disable
- `geofence_id` - Geofence ID
- `group_identifier` - Group identifier from geofence data

**Response:**
```json
{
  "success": true,
  "data": "GeofenceIsInActive"
}
```

---

### GET /user/geofence/get/{group_identifier}/geofences

Get geofences for a specific group.

---

### GET /user/geofence/get/visible-terminal

Get terminals visible for geofence configuration.

---

## Trip Log Endpoints

### GET /user/triplog/generate

Generate trip log for a device.

**Query Parameters:**
- `date_from` - Start date (format: "YYYY-MM-DD HH:MM")
- `date_to` - End date (format: "YYYY-MM-DD HH:MM")
- `imei` - Device IMEI
- `page` (optional): Page number

**Response:**
```json
{
  "success": true,
  "data": {
    "TerminalID": 12345,
    "IsMachine": false,
    "rows": [],
    "Name": "My Boat",
    "RawFromDate": "2026-02-01 00:00",
    "RawToDate": "2026-02-02 14:38",
    "PrivateTripsCount": 0,
    "BusinessTripsCount": 0,
    "BusinessTripsDistanceTotal": 0,
    "PrivateTripsDistanceTotal": 0,
    "TotalRecords": 0,
    "OdometerStart": 0,
    "OdometerEnd": 0
  }
}
```

---

### GET /user/triplog/visible-terminal

Get terminals available for trip log viewing.

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "ID": 12345,
      "Name": "My Boat",
      "Imei": "123456789012345",
      "Model": "FMC130",
      "IsCompanyCar": 0,
      "get_tracker_latest_one_position": {
        "Latitude": "59.0000000",
        "Longitude": "13.0000000",
        "Imei": "123456789012345",
        "Send_Time": "2026-02-02 13:00:05"
      }
    }
  ]
}
```

---

## User & Settings Endpoints

### GET /user/get-settings

Get user account settings.

**Response:**
```json
{
  "success": true,
  "data": {
    "enable_car_booking": false,
    "enable_rfid": false,
    "enable_triplog_report_by_user": false
  }
}
```

---

### POST /user/terminal/access/lockstatus

Check if a terminal is locked.

**Request:**
```json
{
  "terminal_id": 12345
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "lockedstatus": false,
    "accessToworkingHour": true,
    "lockedBy": ""
  }
}
```

---

### GET /user/terminal/get-user-preferences

Get user's UI preferences for terminal display.

**Response:**
```json
{
  "success": true,
  "data": {
    "RegNr": "1",
    "NameOnly": "1",
    "Driver": "1",
    "LastSeen": 1,
    "Odometer": "1",
    "Battery": "1",
    "GPS": "1",
    "Dout1Status": 1
  }
}
```

---

### GET /user/get-address

Reverse geocode coordinates to address.

**Query Parameters:**
- `lat` - Latitude
- `lng` - Longitude

**Response:**
```json
{
  "success": true,
  "data": "Example Street 123, 12345 City, Sweden"
}
```

---

## Administration Endpoints

### GET /administration/user/list

Get list of users in the account.

**Response:**
```json
{
  "success": true,
  "data": {
    "AllowUserCreatePurposes": 0,
    "AllowUserCreateProject": 0,
    "user": [
      {
        "ID": 12345,
        "Email": "user@example.com",
        "IsAdmin": 0,
        "FirstName": "User Name",
        "group": [...]
      }
    ],
    "totalUsers": 1
  }
}
```

---

### GET /administration/safe-home/config

Get safe-home feature configuration.

**Response:**
```json
{
  "success": true,
  "data": {
    "EnableSafeReturnHome": 0
  }
}
```

---

## Common Response Format

All API responses follow this format:

```json
{
  "success": true|false,
  "data": <response_data>
}
```

When `success` is `false`, the `data` field typically contains an error message.

---

## Device Models

Known device models:
- `FMC130` - Teltonika FMC130 (Machine Connect)
- `FMC640` - Teltonika FMC640
- `FMB920` - Teltonika FMB920
- Yabby Edge - Digital Matter Yabby Edge
- Scout - Digital Matter Scout

---

## Integration Usage Notes

### Data Update Flow

1. **Authentication**: Call `/login` to get token
2. **Device Discovery**: Call `/user/terminal/list` to get all devices
3. **Device Details**: Call `/user/terminal/edit-terminal` for each device
4. **Real-time Data**: Poll `/user/realtimetracking/latest-units-data` periodically

### Digital Outputs

The integration only reports output state (from the `Dout<N>Status` fields in
`get-all-units-details`, labelled via `relaySettings` in `edit-terminal`). Outputs are
switched in the NorthTracker web UI, which sends the full relay state at once:

```
POST /user/terminal/relaysetting/sendmsg-collection
{"imei": "...", "dout1": 1, "dout2": 0, "dout3": 0,
 "dout1_name": "Kylskåp", "dout2_name": "DOUT2", "dout3_name": "DOUT3",
 "dout1_auto_control_disable": 0, "dout2_auto_control_disable": 0}
```

### Token Management

- Tokens are valid for approximately 24 hours
- The integration refreshes tokens proactively before expiration
- Store credentials to re-authenticate if token expires

---

## Rate Limits

The API returns rate limit headers:
- `X-RateLimit-Limit` - Maximum requests per minute
- `X-RateLimit-Remaining` - Remaining requests
- `X-Retry-After` - Seconds until rate limit resets

---

## Endpoints Used by This Integration

All read-only - the integration never writes to the API.

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/login` | POST | Authentication |
| `/user/logout` | POST | Logout |
| `/user/terminal/get-all-units-details` | GET | Device list and full details |
| `/user/realtimetracking/latest-units-data` | GET | GPS/sensor data (paginated) |
| `/user/terminal/edit-terminal` | POST | Single device details, DIN/DOUT labels |
| `/user/terminal/get-unit-features` | POST | Device features (low battery alert) |
| `/user/terminal/access/lockstatus` | POST | Lock status |
| `/user/geofence/get/list` | GET | List geofences |

Note: `get-all-units-details` still works but the web client has moved to
`/user/terminal/get-units?device_type=...` and `/user/terminal/list`, so it is the most
likely candidate to be retired next.

---

## Write endpoints used by the web client

Not called by the integration; documented so the read-only fields above can be traced
back to where they are configured.

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/user/terminal/enable-features` | POST | Low battery alert and threshold |
| `/user/terminal/relaysetting/sendmsg-collection` | POST | Set all relay outputs at once |
| `/user/terminal/dout-control-via-din` | POST | Configure a DIN to drive a DOUT |
| `/user/geofence/state/group-update` | POST | Enable/disable a geofence |
| `/user/ble-settings/save-settings` | POST | Toggle BLE sensor readings |
| `/user/ble-settings/save-settings-params` | POST | BLE sensor thresholds/alerts |

---

## Endpoints NOT Yet Implemented

These endpoints exist but are not used by the integration:

| Endpoint | Purpose |
|----------|---------|
| `/user/terminal/get-dout-settings` | Relay labels, values and auto-control flags |
| `/user/terminal/get-auto-dout-settings` | DIN labels and DIN-to-DOUT automation |
| `/user/ble-settings/get-all-paired-sensors` | Paired BLE sensors, independent of realtime data |
| `/user/ble-settings/get-settings` | Per-sensor settings and thresholds |
| `/user/triplog/*` | Trip history |
| `/user/get-address` | Reverse geocoding |
| `/administration/*` | Account management |
| `/user/announcement` | System announcements |

---

## BLE Sensor Settings Endpoints

### GET /user/ble-settings/get-all-paired-sensors

Get all paired Bluetooth sensors for the account.

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "SerialNumber": "AABBCCDDEEFF",
      "PairedSlot": "1",
      "PairedImei": "123456789012345",
      "Name": "Engine Room Sensor"
    }
  ]
}
```

---

### POST /user/ble-settings/get-settings

Get settings for a specific BLE sensor.

**Request:**
```json
{
  "SerialNumber": "AABBCCDDEEFF"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "PairedImei": "123456789012345",
    "SerialNumber": "AABBCCDDEEFF",
    "PairedSlot": "1",
    "DoorSensor": {
      "Show": true,
      "Alert": true
    },
    "Temperature": {
      "Show": true,
      "Alert": false,
      "AlertAbove": 40,
      "AlertBelow": -20
    },
    "Humidity": {
      "Show": true,
      "Alert": false,
      "AlertAbove": 90,
      "AlertBelow": 10
    }
  }
}
```

**Fields:**
- `DoorSensor.Alert` - True to enable door/magnet sensor alerts
- `Temperature.Alert` - True to enable temperature alerts
- `Temperature.AlertAbove/AlertBelow` - Temperature thresholds in Celsius
- `Humidity.Alert` - True to enable humidity alerts
- `Humidity.AlertAbove/AlertBelow` - Humidity percentage thresholds

---

### POST /user/ble-settings/save-settings-params

Update BLE sensor settings (enable/disable alerts).

**Request:**
```json
{
  "PairedImei": "123456789012345",
  "SerialNumber": "AABBCCDDEEFF",
  "PairedSlot": "1",
  "DoorSensor": {
    "Show": true,
    "Alert": 1
  },
  "Temperature": {
    "Show": true,
    "Alert": false,
    "AlertAbove": 40,
    "AlertBelow": -20
  },
  "Humidity": {
    "Show": true,
    "Alert": false,
    "AlertAbove": 90,
    "AlertBelow": 10
  }
}
```

**Parameters:**
- `PairedImei` - IMEI of the GPS device the sensor is paired to
- `SerialNumber` - BLE sensor serial number (MAC address without colons)
- `PairedSlot` - Slot number (1-9)
- `DoorSensor.Alert` - Use `1` to enable, `false` to disable
- `Temperature.Alert/Humidity.Alert` - Boolean to enable/disable alerts

**Response:**
```json
{
  "success": true,
  "data": "Settings saved successfully"
}
```

---

### GET /user/terminal/get-ble-supporting-units

Get list of GPS units that support Bluetooth sensors.

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "ID": 12345,
      "Name": "My Boat",
      "Imei": "123456789012345",
      "BleEnabled": 1
    }
  ]
}
```

---

*Last updated: 2025*
*Source: HAR file capture from gps.northtracker.com*
