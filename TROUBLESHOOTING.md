    # Troubleshooting

    ## HA HTTP 401 Unauthorized

    If the bridge logs show:

    ```text
    HA HTTP 401: 401: Unauthorized
    ```

    Home Assistant rejected the REST request. Common causes:
    - HA_TOKEN is still the placeholder or was copied incorrectly
    - Token was revoked (create a new Long-Lived Access Token)
    - The bridge service wasn't restarted after you updated the token

    Validate token from the bridge host:

    ```bash
    TOKEN='PASTE_YOUR_LONG_LIVED_ACCESS_TOKEN_HERE'
    curl -s -o /dev/null -w "%{http_code}
"       -H "Authorization: Bearer $TOKEN"       http://homeassistant.local:8123/api/
    ```

    Expected:
    - 200 -> OK
    - 401 -> token is invalid

    Also verify entity domain:
    - A TP-Link HS103 plug will typically be `switch.<name>` (example: `switch.bar_lamp`)
    - A dimmer is typically `light.<name>` (example: `light.kitchen_lights`)

    ## Service restart (systemd)

    If running via systemd:

    ```bash
    sudo systemctl restart ha-iotc-bridge.service
    sudo journalctl -u ha-iotc-bridge.service -n 100
    ```
