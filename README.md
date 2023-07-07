# SSH Integration for Home Assistant

This integration allows you to control and monitor devices in Home Assistant by executing commands via SSH connection.

### Features

- Authentication with username/password or key file.
- Connect multiple devices at the same time.
- Use commands to create sensor, binary sensor, text, select, number and switch entities.
- Default commands are included and available without configuration.
- Commands and sensor values can be generated with templates.
- Define multiple sensors for a single command.
- Automatically add/remove entities with dynamic sensors.
- Poll sensors manually by service.
- Turn on devices by Wake on LAN.

## Installation

## Device setup

Click on the Add Integration button in Settings -> Devices & Services and select the SSH integration.

##### Authentication

Login with username and password is supported as well as authentication with a key. The integration will try to find a key file on the local system, otherwise a user defined file can be used.

##### Host key

When connecting to the device for the first time, the integration will look for its key in the local known_hosts file. If the key is unknown, you can choose to save it to a file by enabling “Add unknown host key to host keys file”. The host keys file will then be used to identify the device when connecting to it. Make sure the Home Assistant user has access to it.

##### Default Commands

Choose the matching operating system if you want to have a set of default commands available for the device initially (recommended). The default commands can be modified or deleted later.

##### MAC address

After establishing a SSH connection, the setup will ask you to enter the MAC address of the device. The MAC address will be used as unique ID, as well as to wake up the device by Wake on LAN.

##### Name

Enter a name for the device in the last step to complete the setup. The name will be used to generate entity ID’s for the device and can not be changed later.

## Device configuration

Each device can be configured individually by clicking on the Configure button in Settings -> Devices & Services.

##### Allow to turn the device off

To avoid unintentional shutdowns of remote devices, the function to turn off the device is disabled by default. After activating it, power button and ssh.turn_off service can be used to turn the device off.

##### Update interval

The interval in seconds between updates of the device state. If the device is disconnected (shown by the SSH sensor) the integration will try to reconnect to it as long as it replies to ping requests (shown by the Network sensor).

### Commands

The available action and sensor commands of the device can be edited in the configuration window. The default commands selected during setup will show up here. You can modify them, delete them or add new ones.

##### Templates

Templates can be used to render commands same as with the Command Line integration (example).

##### Sensor values

The current value of a sensor can be included in a command by writing its key in curly braces. If the value is unknown, the integration will try to poll the sensor once before executing the command (example).

##### Variables

Any variable in curly braces that is not a sensor key must be provided when executing the command. This is is only possible for action commands but not for sensor commands (example).

##### Configuration variables

| Name      | Description                 | Type    | Required | Default                       |
| --------- | --------------------------- | ------- | -------- | ----------------------------- |
| `command` | The command to execute.     | string  | yes      |                               |
| `timeout` | The timeout of the command. | integer | no       | Command timeout of the device |

### Action commands

Action commands are executed manually by pressing a button or calling the ssh.run_action service in Home Assistant. A button entity is created for every action command that doesn’t require variables. (examples).

##### Configuration variables

| Name           | Description                                         | Type   | Required              | Default          |
| -------------- | --------------------------------------------------- | ------ | --------------------- | ---------------- |
| `name`         | The name of the button entity.                      | string | If no `key` provided  |                  |
| `key`          | The action key (can be used with `ssh.run_action`). | string | If no `name` provided | Slugified `name` |
| `device_class` | The device class of the button entity.              | string | no                    |                  |
| `icon`         | The icon of the button entity.                      | string | no                    |                  |

### Sensor commands

Sensor commands are executed automatically after connecting to the device or when their scan_interval has passed. Each sensor command contains a list of one or more sensors that get their value from the output of the command (examples).

##### Configuration variables

| Name            | Description                                                                                            | Type    | Required | Default |
| --------------- | ------------------------------------------------------------------------------------------------------ | ------- | -------- | ------- |
| `scan_interval` | The scan interval. If not provided, the command will only execute once every time the device connects. | integer | no       |         |
| `sensors`       | A list of sensors.                                                                                     | list    | yes      |         |

### Sensors

Sensors are updated every time their command gets executed. Depending on their configuration, they can appear as sensor, binary sensor, switch, number, text or select entities in Home Assistant.

##### Static sensors

Static sensors are created by default. Each static sensor extracts its value from one line of the command output. Therefore, they must be defined in the right order (example).

##### Dynamic sensors

Dynamic sensors are created by setting `dynamic: true`. A dynamic sensor extracts a variable number of values from the command output and creates a “child sensor” for each of them. To be able to use a dynamic sensor, each line of the command output must contain ID, value (and optional name) of a child sensor, separated by either one or more spaces or a separator defined with the sensor (example).

##### Controllable sensors

Both static sensors and dynamic sensors can be made controllable by adding `command_set` to their configuration. This command is executed when the user changes the value of the entity. The new value will be passed to the command as value variable. For binary sensors, `command_on` and `command_off` can be used instead of command_set (example).

##### Configuration variables

| Name                  | Description                                                                            | Type    | Required              | Default          |
| --------------------- | -------------------------------------------------------------------------------------- | ------- | --------------------- | ---------------- |
| `type`                | The sensor type (can be `text`, `number` or `binary`).                                 | string  | yes                   |                  |
| `name`                | The name of the entity.                                                                | string  | If no `key` provided  |                  |
| `key`                 | The sensor key (can be used to in commands).                                           | string  | If no `name` provided | Slugified `name` |
| `dynamic`             | Set `true` to create a dynamic sensor.                                                 | boolean | no                    | `false`          |
| `separator`           | Separator between ID, value and name in the command output (only for dynamic sensors). | string  | no                    |                  |
| `unit_of_measurement` | The unit of the sensor.                                                                | string  | no                    |                  |

#### Text type

Sensors with `type: text` appear as sensor (if not controllable), text (without options) or select entities in Home Assistant.

##### Configuration variables

| Name      | Description                                                         | Type    | Required | Default |
| --------- | ------------------------------------------------------------------- | ------- | -------- | ------- |
| `minimum` | The minimum length of the sensor value.                             | integer | no       | `0`     |
| `maximum` | The maximum length of the sensor value.                             | integer | no       | `100`   |
| `pattern` | A regex pattern that the sensor value has to match.                 | string  | no       |         |
| `options` | A list of all possible sensor values (creates a select entity).     | list    | no       |         |
| `mode`    | Display mode (only for text entities, can be `text` or `password`). | string  | no       | `text`  |

#### Number type

Sensors with `type: number` appear as sensor (if not controllable) or number entities in Home Assistant.

##### Configuration variables

| Name      | Description                                                                | Type           | Required | Default |
| --------- | -------------------------------------------------------------------------- | -------------- | -------- | ------- |
| `float`   | Defines the sensor value as float.                                         | boolean        | no       | `false` |
| `minimum` | The minimum sensor value.                                                  | integer, float | no       | `0.0`   |
| `maximum` | The maximum sensor value.                                                  | integer, float | no       | `100.0` |
| `mode`    | Display mode (only for number entities, can be `auto`, `box` or `slider`). | string         | no       | `auto`  |

#### Binary type

Sensors with `type: binary` appear as binary sensor (if not controllable) or switch entities in Home Assistant.

#### Configuration variables

| Name          | Description                                                                       | Type   | Required | Default |
| ------------- | --------------------------------------------------------------------------------- | ------ | -------- | ------- |
| `command_on`  | Command to set the sensor value to `true` (will be used instead of command_set).  | string | no       |         |
| `command_off` | Command to set the sensor value to `false` (will be used instead of command_set). | string | no       |         |
| `payload_on`  | String to detect a `true` sensor value.                                           | string | no       |         |
| `payload_off` | String to detect a `false` sensor value.                                          | string | no       |         |

### Examples

##### Action command

```yaml
command: ~/my_script.sh
name: Execute script
icon: mdi:bash
```

##### Action command with template

```yaml
command: echo "The weather today is {{ states("weather.forecast_home") }}" | mail -s "Weather forecast" me@example.com
name: Send weather forecast
```

##### Action command with variable

```yaml
command: echo {note} >> my_notes.txt
name: Add note
```

##### Sensor command (static sensor)

```yaml
command: who --count | awk -F "=" 'NR>1 {{print $2}}'
interval: 60
sensors:
  - type: number
    name: Logged in users
    icon: mdi:account
```

##### Sensor command with sensor value (static sensor)

```yaml
command: /sys/class/net/{interface}/device/power/wakeup
  sensors:
    - type: binary
      name: Wake on LAN
      payload_on: enabled
```

##### Sensor command with value template (static sensor)

##### Sensor command (multiple static sensors)

```yaml
command: lscpu | awk -F ":" '/^Architecture|^CPU\(s\)|^Model name|^CPU max|^CPU min/ {{print $2}}'
sensors:
  - type: text
    name: CPU architecture
  - type: number
    name: CPU number
    integer: true
  - type: text
    name: CPU model name
  - type: number
    name: CPU MHz max.
  - type: number
    name: CPU MHz min.
```

##### Sensor command (controllable static sensor)

```yaml
command: cat app.conf | awk -F "=" '/^log_level/ {{print $2}}'
sensors:
  - type: text
    name: Log level
    options: - warning - info - debug
    command_set: sed -i "s|^log_level=.\*|log_level={value}|" app.conf
```

##### Sensor command (dynamic sensor)

```yaml
command: ls -lp /mnt/backup | awk 'NR>1 && !/\// {{print $5 / 10^6 "|" $NF}}'
interval: 300
sensors:
  - type: number
    name: File
    dynamic: true
    separator: "|"
    unit_of_measurement: MB
    device_class: data_size
    icon: mdi:file
```

##### Sensor command (controllable dynamic sensor)

```yaml
command: systemctl -a | awk '/bluetooth.service|smbd.service/ {{print $4 "|" $1}}'
interval: 300
sensors:
  - type: binary
    key: systemctl
    dynamic: true
    separator: "|"
    command_on: systemctl start {id}
    command_off: systemctl stop {id}
    payload_on: running
```

## Services

The following services are available.

#### Turn on (ssh.turn_on)

Turn the selected devices on.

#### Turn off (ssh.turn_off)

Turn the selected devices off.

#### Execute command (ssh.execute_command)

Execute a command on the selected devices.

##### Data

| Name        | Description                       | Type    | Required | Default                       |
| ----------- | --------------------------------- | ------- | -------- | ----------------------------- |
| `command`   | The command to execute.           | string  | yes      |                               |
| `timeout`   | The timeout of the command.       | integer | no       | Command timeout of the device |
| `variables` | Variables to pass to the command. | map     | no       |                               |

#### Run action (ssh.run_action)

Run an action on the selected devices.

##### Data

| Name        | Description                       | Type   | Required | Default |
| ----------- | --------------------------------- | ------ | -------- | ------- |
| `key`       | The key of the action command.    | string | yes      |         |
| `variables` | Variables to pass to the command. | map    | no       |         |

#### Poll sensor (ssh.poll_sensor)

Poll one or more sensors.
