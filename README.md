# SSH Integration for Home Assistant

This integration allows you to control and monitor devices in Home Assistant through a SSH connection.

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

#### Default command set

Select the default command set depending on the operating system of the device. If you choose _None_, no entities besides the _Network_ and _SSH_ sensors will be available initially.

#### SSH key file

If you want to use key authentication with the device, enter the path to the key file in the option _SSH key file_. Make sure your Home Assistant user has access to this file.

#### SSH host key file

If your system doesn't know the host key of the device, enable the option _Add unknown host key to host keys file_ and make sure your Home Assistant user has access to this file. After setup this file will be used to identify the device when connecting to it.

## Device configuration

Each device can be configured individually by clicking on its _Configure_ button in _Settings_ -> _Devices & Services_.

#### Allow to turn the device off

After enabling this option, you can use the power button and the `turn_off` service to turn the device off.

#### Update interval

The interval in seconds between updates of the device state (shown by the binary sensors _Network_ and _SSH_).

#### Service commands

Commands used to generate services and button entities in Home Assistant ([details](#service-commands-1)).

#### Sensor commands

Commands used to generate sensor, binary sensor and switch entities in Home Assistant ([details](#sensor-commands-1)).

## Commands

If you have selected a default command set during setup, the included commands will show up in the device configuration window. You can modify those or add new ones for your device.

#### Templates

Templates can be used to render commands in the same way as with the [Command Line](https://www.home-assistant.io/integrations/command_line/#usage-of-templating-in-command) integration.

#### Sensor values

Insert sensor values of the device by writing sensor keys in curly braces.

#### Context

If you put something in curly braces that is not the key of a sensor, you have to provide it with a `context` dictionary when executing the command. This is is only possible for service commands and not for sensor commands. If a service requires context, it won't appear as button entity in Home Assistant and can only be executed with `call_service`.

### Service commands ([examples](#service-command-examples))

As long as a service command doesn't require any context, its service will appear as a button entity in Home Assistant. In case the command does require context, the service can be used by calling the `call_service` service with the key and context.

| Name           | Description                 | Type    | Required     |
| -------------- | --------------------------- | ------- | ------------ |
| `command`      | Command to execute          | string  | yes          |
| `name`         | Name of the service         | string  | no           |
| `key`          | Key of the service          | string  | (if no name) |
| `timeout`      | Timeout of the command      | integer | no           |
| `device_class` | Device class of the service | string  | no           |
| `icon`         | Icon of the service         | string  | no           |

### Sensor commands ([examples](#sensor-command-examples))

Every sensor command contains a list of one or more sensors. These sensors will be updated every time the command executes. This happens when the device connects, when the `scan_interval` has passed or when one of the sensors gets polled manually by the `poll_sensor` service.

| Name            | Description                                       | Type    | Required |
| --------------- | ------------------------------------------------- | ------- | -------- |
| `command`       | Command to execute                                | string  | yes      |
| `sensors`       | Sensors extracted from the output of this command | list    | yes      |
| `timeout`       | Timeout of the command                            | integer | no       |
| `scan_interval` | Scan interval of the sensor command               | integer | no       |

### Sensors

As long as the `value_type` of a sensor is not set to `bool`, it will appear as a sensor entity in Home Assistant. If it is set to `bool`, either a binary sensor or a switch entity will appear (switches need to have both `on_command` and `off_command` defined).

#### Static sensors ([examples](#number-of-logged-in-users-single-static-sensor))

Static sensors are created by default. There can be multiple static sensors per sensor command and each line of the command output is used to get the value for one of them. Thats why static sensors need to be defined in the same order as they appear in the command output.

#### Dynamic sensors ([examples](#files-in-backup-folder-dynamic-sensor))

Dynamic sensors are created by setting `dynamic: true` and there can only be one dynamic sensor per sensor command. Each line of the command output is used to get the name and value of one "child sensor". Names and values must be separated by either one or more spaces or a `separator` defined in the dynamic sensor. All child sensors of a dynamic sensor share the attributes of their "parent" (`value_type`, `unit_of_measurement` and so on).

| Name                  | Description                                                               | Type                   | Required     |
| --------------------- | ------------------------------------------------------------------------- | ---------------------- | ------------ |
| `name`                | Name of the sensor                                                        | string                 | no           |
| `key`                 | Key of the sensor                                                         | string                 | (if no name) |
| `dynamic`             | Set to `true` to create a dynamic sensor                                  | boolean                | no           |
| `value_type`          | Value type of the sensor, set to `bool` to create a binary sensor         | `int`, `float`, `bool` | no           |
| `unit_of_measurement` | Unit of the sensor                                                        | string                 | no           |
| `value_template`      | Template to generate the sensor value from the command output             | string                 | no           |
| `command_on`          | Command to switch the sensor on<br/>(only works with `value_type: bool`)  | string                 | no           |
| `command_off`         | Command to switch the sensor off<br/>(only works with `value_type: bool`) | string                 | no           |
| `payload_on`          | String to detect a `true` value<br/>(only works with `value_type: bool`)  | string                 | no           |
| `payload_off`         | String to detect a `false` value<br/>(only works with `value_type: bool`) | string                 | no           |
| `separator`           | Separator between names and values<br/>(only works with `dynamic: true`)  | string                 | no           |
| `device_class`        | Device class of the sensor                                                | string                 | no           |
| `icon`                | Icon of the sensor                                                        | string                 | no           |

### Service command examples

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

### Sensor command examples

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

#### Some systemd services (dynamic sensor with switch commands)

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
