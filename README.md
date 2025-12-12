# Home Assistant IoTConnect Bridge

A reproducible reference implementation to bridge **Home Assistant** telemetry and control into **Avnet IoTConnect**.

This project shows how to:

- Publish Home Assistant “things” (entities) into MQTT in a clean, analytics-friendly way
- Bridge MQTT telemetry into IoTConnect using the **IoTConnect Python Lite SDK**
- Receive IoTConnect cloud-to-device commands and control Home Assistant via the REST API (example: switch/light on/off)

> This repo intentionally contains **no personal names and no credentials**. All secrets are placeholders.

---

## Repo layout

- `ha_iotc_bridge.py` - MQTT -> IoTConnect telemetry bridge + C2D command handler
- `requirements.txt` - Python dependencies for the bridge
- `examples/` - Home Assistant YAML snippets you can paste/import
- `systemd/` - Optional systemd service unit + instructions (for Linux hosts)

---

## Architecture

```text
Home Assistant -> (Automations + MQTT) -> Mosquitto -> ha_iotc_bridge.py -> IoTConnect
                                            ^
                                            |
                                     IoTConnect Commands
                                            |
                                       Home Assistant API
```

---

## Step-by-step setup

### 1) Flash Home Assistant OS (Raspberry Pi 5)

Helpful screenshots (public links):

**Raspberry Pi Imager start screen**  
![Raspberry Pi Imager start screen](https://www.home-assistant.io/images/installation/rpi_imager_start.png "Raspberry Pi Imager start screen")

**Home Assistant OS selection (Raspberry Pi)**  
![Home Assistant OS selection (Raspberry Pi)](https://www.home-assistant.io/images/installation/rpi-ha.webp "Home Assistant OS selection (Raspberry Pi)")

**Select SD card / storage**  
![Select SD card / storage](https://www.home-assistant.io/images/installation/rpi-select-sd-card.png "Select SD card / storage")

**Choose Next / continue setup**  
![Choose Next / continue setup](https://www.home-assistant.io/images/installation/rpi_choose_next.png "Choose Next / continue setup")

After boot, open:

```text
http://homeassistant.local:8123
```

Complete onboarding.

---

### 2) Enable SSH (Advanced SSH & Web Terminal add-on)

Install via:

**Settings -> Add-ons -> Add-on Store** -> search **Advanced SSH & Web Terminal**.

Example configuration screen:

**Advanced SSH & Web Terminal add-on configuration**  
![Advanced SSH & Web Terminal add-on configuration](https://community-assets.home-assistant.io/original/4X/4/c/e/4ce34674bae7d3fbb99c54ecba528d0432f0b1fb.jpeg "Advanced SSH & Web Terminal add-on configuration")

Notes:
- Do **not** include leading/trailing spaces in the username (it can break user creation).
- Prefer SSH keys if you plan to expose access beyond your LAN.

---

### 3) Install Mosquitto broker add-on

Install **Mosquitto broker** from the add-on store.

Example configuration screen:

**Mosquitto broker add-on configuration**  
![Mosquitto broker add-on configuration](https://community-assets.home-assistant.io/original/3X/5/c/5c510c23d557dfdd69eb86d88f726bd887d7e2b2.png "Mosquitto broker add-on configuration")

Minimal config:

```yaml
logins:
  - username: mqtt
    password: mqtt
require_certificate: false
customize:
  active: false
```

---

### 4) Configure the Home Assistant MQTT integration

Go to **Settings -> Devices & Services -> MQTT**.

Typical settings:
- Discovery enabled
- Birth topic: `homeassistant/status` payload `online`
- Will topic: `homeassistant/status` payload `offline`

> In newer Home Assistant versions, the MQTT “Listen to a topic” tool is not under Developer Tools; it lives under the MQTT integration/config pages.

---

### 5) Option A telemetry: publish numeric state (recommended for IoTConnect)

IoTConnect works best with typed numeric telemetry. For switches/lights, publish 0/1.

#### Bar lamp (TP-Link HS103 plug)
- Entity ID: `switch.bar_lamp`

Automation action payload:

```yaml
{"value": {{ 1 if is_state('switch.bar_lamp', 'on') else 0 }},
 "source": "switch.bar_lamp"}
```

Topic (example): `ha/lights/bar_lamp`

#### Kitchen lights (TP-Link HS220 dimmer)
- Entity ID: `light.kitchen_lights`

Automation action payload:

```yaml
{"value": {{ 1 if is_state('light.kitchen_lights', 'on') else 0 }},
 "source": "light.kitchen_lights"}
```

Topic (example): `ha/lights/kitchen_lights`

Automation UI screenshots (generic references):

**Automation UI example (screenshot 1)**  
![Automation UI example (screenshot 1)](https://community-assets.home-assistant.io/original/4X/5/e/6/5e6758592afd8b5bb538f83dc539f7872061c852.png "Automation UI example (screenshot 1)")

**Automation UI example (screenshot 2)**  
![Automation UI example (screenshot 2)](https://community-assets.home-assistant.io/original/4X/6/6/a/66a88ff2a1957e7617a3dd3bb2d30bf44d862bee.png "Automation UI example (screenshot 2)")

See the ready-to-copy YAML in:
- `examples/automation_switch_bar_lamp.yaml`
- `examples/automation_light_kitchen_lights.yaml`
- `examples/automation_outdoor_temp.yaml`

---

### 6) (Optional) mqtt_statestream

If you want “lots of entity state” mirrored to MQTT automatically, Home Assistant can publish entity state
via `mqtt_statestream`.

Example snippet is included at `examples/sample_configuration.yaml`.

> Note: mqtt_statestream publishes many *strings/timestamps/metadata* topics. Those are great for debugging,
> but don’t always map cleanly to typed IoTConnect attributes. Option A (above) is recommended for analytics.

---

### 7) Create a Home Assistant Long-Lived Access Token

This token is required for IoTConnect -> Home Assistant control (REST API calls).

Profile page screenshot (public link):

**Profile page (Long-Lived Access Tokens section)**  
![Profile page (Long-Lived Access Tokens section)](https://www.home-assistant.io/images/docs/authentication/profile.png "Profile page (Long-Lived Access Tokens section)")

Steps:
- Click your user (lower-left) -> **Profile**
- Scroll to **Long-Lived Access Tokens**
- Create a token and copy it (HA only shows it once)

Set the token in `ha_iotc_bridge.py`:

```python
HA_TOKEN = "REPLACE_WITH_LONG_LIVED_ACCESS_TOKEN"
```

---

### 8) Install bridge dependencies

On the machine where you run the bridge:

```bash
python3 -m pip install -r requirements.txt
```

This bridge needs these local IoTConnect files next to `ha_iotc_bridge.py`:

- `iotcDeviceConfig.json`
- `device-cert.pem`
- `device-pkey.pem`

---

### 9) Run the bridge

```bash
python3 ha_iotc_bridge.py
```

You should see MQTT messages and a “sent telemetry” debug print.

---

### 10) Dedicated variables per device (bar lamp / kitchen lights)

If you only use a single `value` field in IoTConnect, multiple sources will compete.
This bridge also emits dedicated numeric fields:

- `bar_lamp` (0/1)
- `kitchen_lights` (0/1)

based on:
- `source == switch.bar_lamp` or topic `ha/lights/bar_lamp`
- `source == light.kitchen_lights` or topic `ha/lights/kitchen_lights`

In IoTConnect device template telemetry, add (recommended):
- `bar_lamp` (Number)
- `kitchen_lights` (Number)

Optionally also add for debugging:
- `value` (Number)
- `source` (String)
- `ha_topic` (String)
- `payload_raw` (String)

---

## IoTConnect commands (control)

This bridge supports the following command names (either works):
- `set-ha-light`
- `set-ha-entity`

Arguments:
1) `entity_id` (example: `switch.bar_lamp` or `light.kitchen_lights`)
2) `state` (`on/off/1/0/true/false`)
3) `brightness` (optional 0-255 for lights)

Examples:
- Turn plug OFF:
  - `["switch.bar_lamp", "off"]`
- Turn dimmer ON at half brightness:
  - `["light.kitchen_lights", "on", "128"]`

---

## Troubleshooting

### HA HTTP 401 Unauthorized (token issue)

If you see:

```text
HA HTTP 401: 401: Unauthorized
```

it means the Home Assistant REST call is not authenticated.

**Fast validation from the bridge host:**

```bash
TOKEN='PASTE_YOUR_LONG_LIVED_ACCESS_TOKEN_HERE'
curl -s -o /dev/null -w "%{http_code}
"   -H "Authorization: Bearer $TOKEN"   http://homeassistant.local:8123/api/
```

Expected:
- `200` = token is valid
- `401` = token is wrong/revoked/malformed (create a new Long-Lived Access Token)

Also verify you are controlling the correct domain:
- HS103 plug is `switch.bar_lamp` (not `light.bar_lamp`)

If running as a service, restart it after updating the token:
```bash
sudo systemctl restart ha-iotc-bridge.service
```

---

## Run as a service (optional)

See:
- `systemd/README.md`
- `systemd/ha-iotc-bridge.service`
