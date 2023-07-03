# SSH Integration for Home Assistant

This integration allows you to control and monitor devices in Home Assistant by executing commands via SSH connection.

### Features

- Authentication by username/password or SSH key file.
- Multiple devices can be connected at the same time.
- Detection of the devices with ping when they are not connected.
- Setup via user interface, no settings in configuration.yaml necessary.
- Default command sets for Linux and Windows are included and available without additional configuration.
- Services, buttons, sensors and switches are created similarly to the [Command Line](https://www.home-assistant.io/integrations/command_line) Integration.
- Templates can be used to format commands and their output.
- Each sensor command can provide data for multiple sensor entities.
- Dynamic sensors can dynamically add/remove sensor entities in Home Assistant depending on the command output.
- Sensors can be polled manually using a service.
- Devices can be turned on by Wake on LAN if supported by the hardware.

## Device setup

You can add a new device for this integration by clicking on the _Add Integration_ button in _Settings_ -> _Devices & Services_.

### Options

- Default command set

  Select the default command set depending on the operating system of the device. If you choose _None_, no entities besides the _Network_ and _SSH_ sensors will be available initially.

- SSH key file

  If you want to use key authentication with the device, enter the path to the key file in the option _SSH key file_. Make sure your Home Assistant user has access to this file.

- SSH host key file

  If your system doesn't know the host key of the device, enable the option _Add unknown host key to host keys file_ and make sure your Home Assistant user has access to this file. After setup this file will be used to identify the device when connecting to it.

## Device configuration

Each device can be configured individually by clicking on its _Configure_ button in _Settings_ -> _Devices & Services_.

### Options

- Allow to turn the device off

  After enabling this option, you can use the power button and the [`turn_off`](#service-sshturn_off) service to turn the device off.

- Update interval

  The interval in seconds between updates of the device state (shown by the binary sensors _Network_ and _SSH_).

### Commands

There are two kind of commands: [Action commands](#action-commands) and [sensor commands](#sensor-commands). If you have selected a default command set during setup, the included commands will show up in the device configuration window. You can modify them or add new ones for your device.

#### Configuration variables

| Name      | Description                 | Type    | Required | Default                |
| --------- | --------------------------- | ------- | -------- | ---------------------- |
| `command` | The command to execute.     | string  | yes      |                        |
| `timeout` | The timeout of the command. | integer | no       | Device command timeout |

#### Templates

Templates can be used to render commands in the same way as with the [Command Line](https://www.home-assistant.io/integrations/command_line/#usage-of-templating-in-command) integration.

#### Sensor values

By writing sensor keys in curly braces you can include the current value of a sensor in a command. If the value of the sensor is unknown, the integration will try to poll the sensor once before executing the command.

#### Context

If you put any variable in curly braces that is not the key of a sensor, you have to provide it with a `context` dictionary when executing the command. This is is only possible for action commands and not for sensor commands. If an action requires context, it won't appear as button entity in Home Assistant and can only be executed with the [`run_action`](#service-sshrun_action) service.

### Action commands

Action commands are used to create button entities in Home Assistant.
When a action command doesn't require [context](#context), it will appear as button entity in Home Assistant. Action commands with context can be executed with [`run_action`](#service-sshrun_action).

#### Configuration variables

| Name           | Description                                                                                                                     | Type   | Required              | Default               |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------- | ------ | --------------------- | --------------------- |
| `name`         | The name of the action.                                                                                                         | string | If no `key` provided  |                       |
| `key`          | The key of the action.                                                                                                          | string | If no `name` provided | Generated from `name` |
| `device_class` | The device class of the [button](https://developers.home-assistant.io/docs/core/entity/button#available-device-classes) entity. | string | no                    |                       |
| `icon`         | The icon of the entity.                                                                                                         | string | no                    |                       |

### Sensor commands

Sensor commands contain a list of one or more [sensors](#sensors) that will update every time the command executes. This happens when the device connects, when the `scan_interval` has passed or when one of the sensors gets polled manually with the [`poll_sensor`](#service-sshpoll_sensor) service.

#### Configuration variables

| Name            | Description                                                                                            | Type    | Required | Default |
| --------------- | ------------------------------------------------------------------------------------------------------ | ------- | -------- | ------- |
| `scan_interval` | The scan interval. If not provided, the command will only execute once every time the device connects. | integer | no       |         |
| `sensors`       | A list of [sensors](#sensors).                                                                         | list    | yes      |         |

### Sensors

Sensors are used to create sensor, binary sensor, switch, number, text and select entities in Home Assistant.

#### Configuration variables

| Name                  | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                   | Type    | Required              | Default               |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- | --------------------- | --------------------- |
| `type`                | The type of the sensor (can be `text`, `number` or `binary`).                                                                                                                                                                                                                                                                                                                                                                                                 | string  | yes                   |
| `name`                | The name of the sensor.                                                                                                                                                                                                                                                                                                                                                                                                                                       | string  | If no `key` provided  |                       |
| `key`                 | The key of the sensor.                                                                                                                                                                                                                                                                                                                                                                                                                                        | string  | If no `name` provided | Generated from `name` |
| `dynamic`             | Creates a dynamic sensor when set to `true`.                                                                                                                                                                                                                                                                                                                                                                                                                  | boolean | no                    | false                 |
| `separator`           | Separates the data on each line of the command output (only relevant for dynamic sensors).                                                                                                                                                                                                                                                                                                                                                                    | string  | no                    |                       |
| `unit_of_measurement` | The unit of the sensor.                                                                                                                                                                                                                                                                                                                                                                                                                                       | string  | no                    |                       |
| `value_template`      | Template to generate the value from the command output.                                                                                                                                                                                                                                                                                                                                                                                                       | string  | no                    |                       |
| `command_set`         | Command to set the value of the sensor (will create a text, select, number or switch entity).                                                                                                                                                                                                                                                                                                                                                                 | string  | no                    |                       |
| `device_class`        | Device class (only relevant for [sensor](https://developers.home-assistant.io/docs/core/entity/sensor#available-device-classes), [binary sensor](https://developers.home-assistant.io/docs/core/entity/binary-sensor#available-device-classes), [number](https://developers.home-assistant.io/docs/core/entity/number#available-device-classes) or [switch](https://developers.home-assistant.io/docs/core/entity/switch#available-device-classes) entities). | string  | no                    |                       |
| `icon`                | Icon of the entity                                                                                                                                                                                                                                                                                                                                                                                                                                            | string  | no                    |                       |

### Text sensors

Text sensors are created by with `type: text`.
Without `command_set`: Sensor entity.
With `command_set`: Text entity.
With `command_set` and `options`: Select entity.

#### Configuration variables

| Name      | Description                                                                          | Type    | Required | Default |
| --------- | ------------------------------------------------------------------------------------ | ------- | -------- | ------- |
| `minimum` | The minimum length of the sensor value (only applies to text entities).              | integer | no       | 0       |
| `maximum` | The maximum length of the sensor value (only applies to text entities).              | integer | no       | 100     |
| `pattern` | A regex pattern that the sensor value has to match (only applies to text entities).  | string  | no       |         |
| `options` | A list of all possible sensor values (will turn a text entity into a select entity). | list    | no       |         |
| `mode`    | Display mode (only applies to text entities, can be `text` or `password`).           | string  | no       | `text`  |

### Number sensors

Number sensors are created by with `type: number`.
Without `command_set`: Sensor entity.
With `command_set`: Number entity.

#### Configuration variables

| Name      | Description                                                                       | Type       | Required | Default |
| --------- | --------------------------------------------------------------------------------- | ---------- | -------- | ------- |
| `integer` | Defines the sensor value as integer.                                              | boolean    | no       | `false` |
| `minimum` | The minimum sensor value (only applies to number entities).                       | int, float | no       | 0.0     |
| `maximum` | The maximum sensor value (only applies to number entities).                       | int, float | no       | 100.0   |
| `mode`    | Display mode (only applies to number entities, can be `auto`, `box` or `slider`). | string     | no       | `auto`  |

### Binary sensors

Binary sensors are created by with `type: binary`.
Without `command_set`/`command_on` & `command_off`: Binary sensor entity.
With `command_set`/`command_on` & `command_off`: Switch entity.

#### Configuration variables

| Name          | Description                                 | Type   | Required | Default |
| ------------- | ------------------------------------------- | ------ | -------- | ------- |
| `command_on`  | Command to set the sensor value to `true`.  | string | no       |         |
| `command_off` | Command to set the sensor value to `false`. | string | no       |         |
| `payload_on`  |                                             | string | no       |         |
| `payload_off` |                                             | string | no       |         |

#### Static sensors ([examples](#number-of-logged-in-users-single-static-sensor))

Static sensors are created by default. They can extract a fixed number of values from the command output. There can be multiple static sensors in one sensor command and each line of the command output is used to get the value for one of them. Static sensors must be defined in the same order as they appear in the command output.

#### Dynamic sensors ([examples](#files-in-backup-folder-dynamic-sensor))

Dynamic sensors are created by setting `dynamic: true`. They can extract a variable number of values from the command output. There can only be one dynamic sensor per sensor command. Each line of the command output is used to get value and name of one "child sensor". Values and names must be separated by either one or more spaces or a `separator` defined in the dynamic sensor. All child sensors of a dynamic sensor share the attributes of their "parent" (`value_type`, `unit_of_measurement`, etc.).

## Examples

### Action commands

#### Backup a folder

```yaml
command: rsync -Aax --log-file='~/backup.log' '~/my_folder' '/mnt/backup/'
name: Backup my folder
timeout: 30
```

#### Execute a script

```yaml
command: ~/my_script.sh
name: Execute my script
icon: mdi:bash
```

### Sensor commands

#### Number of logged in users (single static sensor)

```yaml
command: who --count | awk -F "=" 'NR>1 {{print $2}}'
interval: 60
sensors:
  - name: Logged in users
  - value_type: int
  - icon: mdi:account
```

#### CPU information (multiple static sensors)

```yaml
command: lscpu | awk -F ":" '/^Architecture|^CPU\(s\)|^Model name|^CPU max|^CPU min/ {{print $2}}'
sensors:
  - name: CPU architecture
  - name: CPU number
    value_type: int
  - name: CPU model name
  - name: CPU MHz max.
    value_type: float
  - name: CPU MHz min.
    value_type: float
```

#### Files in a folder (dynamic sensor)

```yaml
command: ls -lp /mnt/backup | awk 'NR>1 && !/\// {{print $5 / 10^6 "|" $NF}}'
interval: 600
sensors:
  - key: file
    dynamic: true
    value_type: float
    unit_of_measurement: MB
    separator: "|"
    icon: mdi:file
    device_class: data_size
```

#### Systemd services (dynamic sensor with switch commands)

```yaml
command: systemctl -a | awk '/bluetooth.service|smbd.service/ {{print $4 "|" $1}}'
interval: 300
sensors:
  - key: service
    dynamic: true
    value_type: bool
    command_on: systemctl start {id}
    command_off: systemctl stop {id}
    payload_on: running
    separator: "|"
```

## Services

### `ssh.turn_on`

Turn the device on.

### `ssh.turn_off`

Turn the device off.

### `ssh.execute_command`

Execute a command on the device. Event: `ssh_command_executed`.

| Data attribute | Description                     | Type    | Required |
| -------------- | ------------------------------- | ------- | -------- |
| `command`      | Command to execute              | string  | yes      |
| `context`      | Variables to format the command | mapping | no       |
| `timeout`      | Timeout of the command          | integer | no       |

### `ssh.run_action`

Run an action command on the device.

| Data attribute | Description                     | Type    | Required |
| -------------- | ------------------------------- | ------- | -------- |
| `key`          | Key of the action command       | string  | yes      |
| `context`      | Variables to format the command | mapping | no       |

### `ssh.poll_sensor`

Poll a sensor on the device.
