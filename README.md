# AVGear Matrix Switcher for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

A Home Assistant custom integration to control AVGear HDMI Matrix Switchers (AVG-CS4K-88-V2 and compatible models) via TCP/IP.

## Features

- **Output Routing**: Control which input is routed to each output using Select entities
- **Presets**: Save and recall up to 10 presets (0-9) with custom names
- **Quick Actions**: "All Through" and "All Off" buttons for common operations
- **Panel Lock**: Lock/unlock the front panel buttons remotely
- **Standby Control**: Put the matrix in/out of standby mode
- **EDID Management**: Per-input selection of the six built-in EDID profiles, a "Reset All EDID" button, plus services for copying a display's EDID onto an input, forcing PCM audio downmix, and dumping raw EDID hex
- **HDCP Management**: Per-input and per-output HDCP compliance switches, plus an "Auto HDCP Management" button
- **Diagnostic Sensors** _(disabled by default)_: Per-port cable-connection and HDCP-active binary sensors, per-output resolution sensors
- **Custom Input Names**: Name your inputs (e.g., "Blu-ray Player", "Cable Box") in integration options
- **Custom Preset Names**: Name your presets (e.g., "Movie Night", "Gaming Setup") in integration options
- **Configurable Polling**: Adjust the status update interval (default: 30 seconds)
- **Name Validation**: Max 50 characters per name, duplicate (case-insensitive) input/preset detection

## Supported Devices

- AVGear AVG-CS4K-88-V2 (8×8 HDMI Matrix)
- Other AVGear matrices using the same command protocol

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click the three dots menu and select "Custom repositories"
4. Add this repository URL: `https://github.com/maeneak/avgearip`
5. Select "Integration" as the category
6. Click "Add"
7. Search for "AVGear Matrix" and install it
8. Restart Home Assistant

### Manual Installation

1. Download the `custom_components/avgear_matrix` folder
2. Copy it to your Home Assistant's `custom_components` directory
3. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for "AVGear Matrix Switcher"
4. Enter the IP address and port (default: 4001) of your matrix
5. Click **Submit**

### Default Network Settings

The matrix typically ships with these defaults:
- **IP Address**: `192.168.0.178`
- **Port**: `4001` (cannot be changed)

## Entities

After setup, the integration creates the following entities:

### Select Entities (one per output)
- `select.avgear_matrix_output_1` through `output_8`
- Options: Custom input names (or Input 1-8 by default), Off
### Select Entity (route to all outputs)
- `select.avgear_matrix_route_to_all_outputs`
- Options: Custom input names (or Input 1-8 by default)

### Button Entities
- **Save Preset**: Saves current routing to the currently selected preset
- **All Through**: Route Input 1→Output 1, Input 2→Output 2, etc.
- **All Off**: Switch off all outputs

### Switch Entities
- **Panel Lock**: Lock/unlock front panel buttons
- **Standby**: Enable/disable standby mode
- **Input _N_ HDCP**: Per-input HDCP compliance setting (HDCPEN). Turn off to let a non-HDCP source pass through unencrypted.
- **Output _N_ HDCP**: Per-output HDCP compliance. Turn off for non-HDCP sinks (capture cards, older projectors). ⚠️ Protected content may refuse to play if you disable HDCP on a compliant display.

### EDID Controls

- **_Input N_ EDID** _(select)_: Choose one of six built-in EDID profiles per input — `1080p 2D 2CH`, `1080p 3D 2CH`, `1080p 2D Multichannel`, `1080p 3D Multichannel`, `4K 30Hz 2D`, `4K 60Hz 2D`. State is optimistic: after a Home Assistant restart the select is blank until you re-apply a profile.
- **Reset All EDID** _(button)_: Factory-restore every input's EDID.
- **Auto HDCP Management** _(button)_: Trigger the matrix's built-in auto HDCP routine.

### Diagnostic Sensors _(disabled by default)_

Enable individually via entity settings:

- **_Input N_ Connected**: Binary sensor — is an HDMI cable plugged in?
- **Output _N_ Connected**: Binary sensor — is a display plugged in?
- **_Input N_ HDCP Active**: Binary sensor — is the source currently sending encrypted content? (Distinct from the _Input N_ HDCP switch: the switch sets the HDCPEN compliance flag, this sensor reflects live negotiation.)
- **Output _N_ Resolution**: Sensor — current output resolution string (e.g., `1920x1080p`, `3840x2160p`).

### Services

- `avgear_matrix.save_preset`: Save current routing to preset 0–9.
- `avgear_matrix.copy_edid_from_output`: Copy the EDID from a display (output) onto an input so sources negotiate the display's native modes.
- `avgear_matrix.force_input_pcm`: Modify an input's EDID to advertise PCM audio only. One-way — to revert, re-apply a built-in profile or use Reset All EDID.
- `avgear_matrix.dump_edid`: Read raw EDID bytes as a hex string from an input, an output's display, or a built-in slot. Returns `{hex, length, source, number}`. Diagnostic tool for HDMI handshake troubleshooting.

Example — copy the living-room TV's EDID onto input 3:

```yaml
action:
  - service: avgear_matrix.copy_edid_from_output
    data:
      input: 3
      output: 1
```

## Options

After adding the integration, you can configure:

1. **Update Interval**: How often to poll the matrix for status (5-300 seconds, default: 30)
2. **Input Names**: Custom names for each input (e.g., "Blu-ray Player", "Cable Box") — max 50 characters, must be unique
3. **Preset Names**: Custom names for each preset (e.g., "Movie Night", "Gaming Setup") — max 50 characters, must be unique

> **Note**: Input names must be unique across all inputs, since they are used to identify which source to route. If duplicate names are detected, the options flow will show an error.

## Automation Examples

### Route input based on time of day

```yaml
automation:
  - alias: "Morning News on Living Room"
    trigger:
      - platform: time
        at: "07:00:00"
    action:
      - service: select.select_option
        target:
          entity_id: select.avgear_matrix_output_1
        data:
          option: "Cable Box"  # Uses custom input name
```

### Recall preset when scene is activated

```yaml
automation:
  - alias: "Movie Night Preset"
    trigger:
      - platform: state
        entity_id: scene.movie_night
    action:
      - service: select.select_option
        target:
          entity_id: select.avgear_matrix_preset
        data:
          option: "Movie Night"
```

### Turn off all outputs at night

```yaml
automation:
  - alias: "All Off at Midnight"
    trigger:
      - platform: time
        at: "00:00:00"
    action:
      - service: button.press
        target:
          entity_id: button.avgear_matrix_all_off
```

## Upgrading

For major updates, review release notes before upgrading. If a release notes entry indicates config-entry schema changes, remove and re-add the integration to refresh stored device metadata.

## Troubleshooting

### Cannot connect to the matrix

1. Verify the matrix is powered on and connected to your network
2. Check that the IP address is correct (default: `192.168.0.178`)
3. Ensure port 4001 is not blocked by a firewall
4. Try connecting with netcat: `nc 192.168.0.178 4001` and send `Status.`

### Status not updating

- Increase the polling interval in integration options
- Check the Home Assistant logs for connection errors
- Verify the matrix is responding to commands

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## License

MIT License - see LICENSE file for details.

## Disclaimer

This integration is not affiliated with or endorsed by AVGear. Use at your own risk.
