#!/usr/bin/env python3
"""Home Assistant -> MQTT -> IoTConnect Bridge (Option A + per-device variables + fixed commands).

Telemetry (MQTT -> IoTConnect)
- Subscribes to clean topics:
    - ha/lights/#      (your per-device automations)
    - ha/metrics/#     (your metrics automations)
    - homeassistant/status
- Expects JSON payloads like:
    {"value": 1, "source": "switch.bar_lamp"}

Per-device telemetry keys (optional but recommended in IoTConnect template):
- bar_lamp        (0/1)
- kitchen_lights  (0/1)

Commands (IoTConnect -> HA)
- Accepts BOTH command names:
    - set-ha-light
    - set-ha-entity
- Args:
    1) entity_id: e.g. switch.bar_lamp or light.kitchen_lights
    2) state: on/off/1/0/true/false
    3) brightness: optional 0-255 for lights

NOTE: Replace placeholders before running:
- HA_TOKEN
- IoTConnect config/cert/key files (must be present in working directory)
"""

import json
import sys
from typing import Any, Dict, Optional

import requests
import paho.mqtt.client as mqtt

from avnet.iotconnect.sdk.lite import Client, DeviceConfig, Callbacks, C2dCommand
from avnet.iotconnect.sdk.sdklib.mqtt import C2dAck


# ---------------------------- USER CONFIG ----------------------------

HA_BASE_URL = "http://homeassistant.local:8123"
HA_TOKEN = "REPLACE_WITH_LONG_LIVED_ACCESS_TOKEN"

MQTT_HOST = "homeassistant.local"
MQTT_PORT = 1883
MQTT_USER = "mqtt"
MQTT_PASSWORD = "mqtt"

MQTT_TOPICS = [
    ("ha/lights/#", 0),
    ("ha/metrics/#", 0),
    ("homeassistant/status", 0),
]

IOTC_DEVICE_CONFIG_JSON = "iotcDeviceConfig.json"
IOTC_DEVICE_CERT_PEM = "device-cert.pem"
IOTC_DEVICE_PKEY_PEM = "device-pkey.pem"

# Dedicated per-device keys (avoid "one value field for everything")
ENTITY_TO_KEY = {
    "switch.bar_lamp": "bar_lamp",
    "light.kitchen_lights": "kitchen_lights",
}
TOPIC_TO_KEY = {
    "ha/lights/bar_lamp": "bar_lamp",
    "ha/lights/kitchen_lights": "kitchen_lights",
}


# ---------------------------- INTERNALS ----------------------------

HA_HEADERS = {
    "Authorization": f"Bearer {HA_TOKEN}",
    "Content-Type": "application/json",
}

iotc: Optional[Client] = None


def ensure_iotc_connected() -> None:
    assert iotc is not None
    if not iotc.is_connected():
        print("(re)connecting to IoTConnect...")
        iotc.connect()
        if not iotc.is_connected():
            print("Unable to connect to IoTConnect")
            sys.exit(2)


def ha_call_service(domain: str, service: str, payload: Dict[str, Any]) -> requests.Response:
    url = f"{HA_BASE_URL}/api/services/{domain}/{service}"
    return requests.post(url, headers=HA_HEADERS, json=payload, timeout=10)


def coerce_on_off(val: Any) -> Optional[bool]:
    """Convert common on/off representations into bool."""
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        if val == 1:
            return True
        if val == 0:
            return False
    if isinstance(val, str):
        v = val.strip().lower()
        if v in ("on", "true", "1", "yes"):
            return True
        if v in ("off", "false", "0", "no"):
            return False
    return None


def parse_mqtt_payload(payload_raw: str) -> Dict[str, Any]:
    """Parse payload, prefer JSON dict."""
    try:
        parsed = json.loads(payload_raw)
        if isinstance(parsed, dict):
            return dict(parsed)
        return {"value": parsed}
    except Exception:
        return {"value": payload_raw}


def add_per_device_key(telemetry: Dict[str, Any]) -> None:
    """Add bar_lamp/kitchen_lights numeric keys when recognized."""
    src = telemetry.get("source")
    topic = telemetry.get("ha_topic")

    key = None
    if isinstance(src, str) and src in ENTITY_TO_KEY:
        key = ENTITY_TO_KEY[src]
    elif isinstance(topic, str) and topic in TOPIC_TO_KEY:
        key = TOPIC_TO_KEY[topic]

    if not key:
        return

    state_bool = coerce_on_off(telemetry.get("value"))
    if state_bool is None:
        v = telemetry.get("value")
        if isinstance(v, (int, float)) and v in (0, 1):
            telemetry[key] = int(v)
        return

    telemetry[key] = 1 if state_bool else 0


# ---------------------------- IoTConnect callbacks ----------------------------

def on_command(msg: C2dCommand) -> None:
    """Handle IoTConnect command -> Home Assistant service call."""
    assert iotc is not None
    print("Received command:", msg.command_name, msg.command_args, msg.ack_id)

    if msg.command_name not in ("set-ha-light", "set-ha-entity"):
        if msg.ack_id is not None:
            iotc.send_command_ack(msg, C2dAck.CMD_FAILED, "Not implemented")
        return

    if len(msg.command_args) < 2:
        if msg.ack_id is not None:
            iotc.send_command_ack(msg, C2dAck.CMD_FAILED, "Expected: entity_id, state[, brightness]")
        return

    entity_id = str(msg.command_args[0]).strip()
    desired = msg.command_args[1]
    desired_bool = coerce_on_off(desired)

    brightness: Optional[int] = None
    if len(msg.command_args) >= 3 and msg.command_args[2] is not None:
        try:
            brightness = int(msg.command_args[2])
        except Exception:
            brightness = None

    if "." not in entity_id:
        if msg.ack_id is not None:
            iotc.send_command_ack(msg, C2dAck.CMD_FAILED, "Invalid entity_id (expected domain.object_id)")
        return

    domain = entity_id.split(".", 1)[0]

    if desired_bool is None:
        if msg.ack_id is not None:
            iotc.send_command_ack(msg, C2dAck.CMD_FAILED, f"Invalid state: {desired}")
        return

    try:
        if domain == "switch":
            svc = "turn_on" if desired_bool else "turn_off"
            r = ha_call_service("switch", svc, {"entity_id": entity_id})

        elif domain == "light":
            if desired_bool:
                payload = {"entity_id": entity_id}
                if brightness is not None:
                    payload["brightness"] = max(0, min(255, brightness))
                r = ha_call_service("light", "turn_on", payload)
            else:
                r = ha_call_service("light", "turn_off", {"entity_id": entity_id})

        else:
            if msg.ack_id is not None:
                iotc.send_command_ack(msg, C2dAck.CMD_FAILED, f"Unsupported domain: {domain}")
            return

        if r.status_code in (200, 201):
            if msg.ack_id is not None:
                iotc.send_command_ack(
                    msg,
                    C2dAck.CMD_SUCCESS_WITH_ACK,
                    f"Set {entity_id} to {'on' if desired_bool else 'off'}",
                )
        else:
            if msg.ack_id is not None:
                iotc.send_command_ack(msg, C2dAck.CMD_FAILED, f"HA HTTP {r.status_code}: {r.text}")

    except Exception as exc:
        if msg.ack_id is not None:
            iotc.send_command_ack(msg, C2dAck.CMD_FAILED, f"Exception: {exc}")


def on_disconnect(reason: str, disconnected_from_server: bool) -> None:
    print("Disconnected%s. Reason: %s" % (" from server" if disconnected_from_server else "", reason))


# ---------------------------- MQTT callbacks ----------------------------

def on_mqtt_connect(client: mqtt.Client, userdata: Any, flags: Dict[str, Any], rc: int) -> None:
    print("Connected to MQTT with rc=", rc)
    for topic, qos in MQTT_TOPICS:
        client.subscribe(topic, qos)
    print("Subscribed to:", [t for t, _ in MQTT_TOPICS])


def on_mqtt_message(client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
    assert iotc is not None

    topic = msg.topic
    payload_raw = msg.payload.decode(errors="ignore")

    print("MQTT message:", topic, "=", payload_raw)

    telemetry: Dict[str, Any] = {
        "ha_topic": topic,
        "payload_raw": payload_raw,
    }

    telemetry.update(parse_mqtt_payload(payload_raw))

    # Add per-device numeric keys when recognized
    add_per_device_key(telemetry)

    ensure_iotc_connected()
    iotc.send_telemetry(telemetry)

    # Debug: show what we sent
    print("> ", {"d": [{"d": telemetry}]})


# ---------------------------- Main ----------------------------

def main() -> None:
    global iotc

    device_config = DeviceConfig.from_iotc_device_config_json_file(
        device_config_json_path=IOTC_DEVICE_CONFIG_JSON,
        device_cert_path=IOTC_DEVICE_CERT_PEM,
        device_pkey_path=IOTC_DEVICE_PKEY_PEM,
    )

    iotc = Client(
        config=device_config,
        callbacks=Callbacks(
            command_cb=on_command,
            disconnected_cb=on_disconnect,
        ),
    )

    ensure_iotc_connected()

    m = mqtt.Client()
    m.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    m.on_connect = on_mqtt_connect
    m.on_message = on_mqtt_message

    print("Awaiting MQTT connection establishment...")
    m.connect(MQTT_HOST, MQTT_PORT, 60)

    print("Starting MQTT loop...")
    m.loop_forever()


if __name__ == "__main__":
    main()
