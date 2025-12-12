# Run the bridge as a systemd service

> This is for a standard Linux host (Debian/Ubuntu/Raspberry Pi OS, etc.).
> If you run the bridge *inside* the Home Assistant "Advanced SSH" add-on container,
> systemd is not available there. In that case, run the bridge manually or run it
> on a separate Linux host.

## Install location

This unit file assumes the bridge lives at:

- `/opt/home-assistant-iotconnect-bridge/ha_iotc_bridge.py`
- plus IoTConnect credential files in the same directory:
  - `iotcDeviceConfig.json`
  - `device-cert.pem`
  - `device-pkey.pem`

## Install steps

Copy repo contents into place:

```bash
sudo mkdir -p /opt/home-assistant-iotconnect-bridge
sudo cp -r ./* /opt/home-assistant-iotconnect-bridge/
sudo chmod +x /opt/home-assistant-iotconnect-bridge/ha_iotc_bridge.py
```

Install the unit file:

```bash
sudo cp /opt/home-assistant-iotconnect-bridge/systemd/ha-iotc-bridge.service /etc/systemd/system/ha-iotc-bridge.service
sudo systemctl daemon-reload
```

Enable and start:

```bash
sudo systemctl enable ha-iotc-bridge.service
sudo systemctl start ha-iotc-bridge.service
```

Check status and logs:

```bash
sudo systemctl status ha-iotc-bridge.service
sudo journalctl -u ha-iotc-bridge.service -f
```

Restart after changing HA_TOKEN in `ha_iotc_bridge.py`:

```bash
sudo systemctl restart ha-iotc-bridge.service
```

Stop / disable:

```bash
sudo systemctl stop ha-iotc-bridge.service
sudo systemctl disable ha-iotc-bridge.service
```
