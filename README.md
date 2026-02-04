# AVGear Matrix Switcher for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

A Home Assistant custom integration to control AVGear HDMI Matrix Switchers (AVG-CS4K-88-V2 and compatible models) via TCP/IP.

## Features

- **Output Routing**: Control which input is routed to each output using Select entities
- **Presets**: Save and recall up to 10 presets (0-9)
- **Quick Actions**: "All Through" and "All Off" buttons for common operations
- **Panel Lock**: Lock/unlock the front panel buttons remotely
- **Standby Control**: Put the matrix in/out of standby mode
- **Custom Names**: Configure custom names for each output in the integration options
- **Configurable Polling**: Adjust the status update interval (default: 30 seconds)

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
- Options: Input 1-8, Off
### Select Entity (route to all outputs)
- `select.avgear_matrix_route_to_all_outputs`
- Options: Input 1-8

### Button Entities
- **Recall Preset 0-9**: Recall saved routing configurations
- **Save Preset 0-9**: Save current routing to a preset
- **All Through**: Route Input 1→Output 1, Input 2→Output 2, etc.
- **All Off**: Switch off all outputs

### Switch Entities
- **Panel Lock**: Lock/unlock front panel buttons
- **Standby**: Enable/disable standby mode

## Options

After adding the integration, you can configure:

1. **Update Interval**: How often to poll the matrix for status (5-300 seconds, default: 30)
2. **Output Names**: Custom names for each output (e.g., "Living Room TV", "Bedroom TV")

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
          option: "Input 2"
```

### Recall preset when scene is activated

```yaml
automation:
  - alias: "Movie Night Preset"
    trigger:
      - platform: state
        entity_id: scene.movie_night
    action:
      - service: button.press
        target:
          entity_id: button.avgear_matrix_recall_preset_1
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
