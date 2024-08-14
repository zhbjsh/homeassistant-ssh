[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

# SSH Integration for Home Assistant

This custom integration allows you to control and monitor devices in Home Assistant by executing terminal commands via SSH. It uses the [paramiko](https://www.paramiko.org) library and works in a similar way as the official [Command Line](https://www.home-assistant.io/integrations/command_line/#usage-of-templating-in-command) integration.

### Features

- SSH authentication with username/password or key file.
- Connect to multiple devices at the same time.
- Generate sensor, binary sensor, text, select, number and switch entities.
- Default commands for Linux and Windows included and available without configuration.
- Edit all commands and settings from the UI.
- Get the value of multiple sensors from the output of a single command.
- Use dynamic sensors to automatically add/remove entities.
- Render commands and sensor values with templates.
- Poll sensors manually by calling a service.
- Include sensor values in commands and update them automatically when executing.
- Turn on devices by Wake on LAN.

## Installation

##### From HACS

Install [HACS](https://hacs.xyz/docs/setup/download) and open it in Home Assistant. Select _Integrations_ and add a custom repository by clicking on the three dots on the top right corner. Enter `https://github.com/zhbjsh/homeassistant-ssh` as _Repository_ and select _Integration_ as _Category_. You can now search for the _SSH_ integration and download it.

##### From Github

Download the [latest release](https://github.com/zhbjsh/homeassistant-ssh/releases/latest) and copy the `custom_components/ssh` folder from the zip file to `config/custom_components/` on your Home Assistant installation. Don't forget to restart Home Assistant after you're done.

## Device setup

Click on the _Add Integration_ button in _Settings_ -> _Devices & Services_ and select the _SSH_ integration.

##### Authentication

Authentication can be done with Username & Password or you can use Key-Based Authentication.

###### Username & Password authentication

Simply enter them in the configuration dialog.

###### Key authentication

Key files in the Home Assistant users `~/.ssh/` folder are used automatically. To use another location, enter the path to your file (for example `/config/id_rsa`) and make sure the Home Assistant user has access to it.

##### Host key

When connecting to the device, the integration looks for its host key in `~/.ssh/known_hosts`. If the key is missing, you can choose to automatically save it to a _Host keys file_ by enabling the option _Automatically add key to host keys file_.

##### Default commands

Choose the option that matches your device to have a set of default commands available after setup. This will create some sensors (CPU load, free memory, temperature, etc.) and makes it possible to shutdown and restart the device. The default commands can be modified or deleted later.

##### MAC address

After connecting to the device, setup asks you to enter the MAC address of the device. Make sure the MAC address is correct, as it is used as unique ID and to turn the device on by Wake on LAN.

##### Name

Enter a name for the device to complete the setup. The name is used to generate entity IDs and can not be changed later.

## Device configuration

Devices can be configured by clicking on the _Configure_ button in _Settings_ -> _Devices & Services_.

##### Allow to turn the device off

To avoid unintentional shutdowns, this function is disabled by default. After enabling it, power button and [`ssh.turn_off`](#turn-off-sshturn_off) service can be used to turn the device off.

##### Reset default commands

Select this option to reset all actions/sensors whose keys are included in the default commands and update them to their newest version.

##### Update interval

The update interval is the time in seconds between updates of the device state. If the device disconnects (shown by the _SSH Status_ sensor), the integration will try to reconnect to it as long as it replies to ping requests (shown by the _Network Status_ sensor).

##### Command timeout

The command timeout is the time in seconds that the integration waits for a command to complete. Generally commands should be short (maximum a couple seconds), as they are executed one after another and block the next command while they are running.

### Commands

[Action commands](#action-commands) and [sensor commands](#sensor-commands) of the device can be edited in the configuration window. This is where the default commands from the setup will show up. You can modify them, delete them or add new commands. Be careful when deleting commands, as all entities created by them will become unavailable.

You can test new commands with the [`ssh.execute_command`](#execute-command-sshexecute_command) service in the developer tools, where the service response will show you the output.

##### Include templates

[Templates](https://www.home-assistant.io/docs/configuration/templating) can be used in commands, same as with the [Command Line](https://www.home-assistant.io/integrations/command_line/#usage-of-templating-in-command) integration ([example](#send-the-weather-forecast)).

##### Include sensors

Sensors of the same device can be accessed in commands with `&{my_sensor_key}`. The integration will poll the required sensors once before every execution and include their values in the command ([example](#ip-address)).

##### Include variables

Variables can be passed to action commands (but not sensor commands) and accessed with `@{my_variable_name}`. Action commands that require variables can only be executed by calling the [`ssh.run_action`](#run-action-sshrun_action) service ([example](#add-a-note-to-a-file)).

##### Configuration

| Name      | Description                 | Type    | Required | Default                       |
| --------- | --------------------------- | ------- | -------- | ----------------------------- |
| `command` | The command to execute.     | string  | yes      |                               |
| `timeout` | The timeout of the command. | integer | no       | Command timeout of the device |

### Action commands

Action commands are executed manually by pressing a button or calling the [`ssh.run_action`](#run-action-sshrun_action) service. A button entity is created for each action command that doesn’t require variables. ([example](#execute-a-script)).

##### Configuration

| Name                              | Description                                                                                                           | Type    | Required               | Default          |
| --------------------------------- | --------------------------------------------------------------------------------------------------------------------- | ------- | ---------------------- | ---------------- |
| `name`                            | The name of the entity.                                                                                               | string  | If no `key` specified  |                  |
| `key`                             | The action key (can be used with [`ssh.run_action`](#run-action-sshrun_action)).                                      | string  | If no `name` specified | Slugified `name` |
| `device_class`                    | The [device class](https://www.home-assistant.io/docs/configuration/customizing-devices/#device-class) of the entity. | string  | no                     |
| `icon`                            | The icon of the entity.                                                                                               | string  | no                     |                  |
| `entity_registry_enabled_default` | Set `false` to disable the entity by default.                                                                         | boolean | no                     | `true`           |

### Sensor commands

Sensor commands are executed automatically when the device connects or when their `scan_interval` has passed. Each sensor command contains a list of one or more sensors that receive their value from its output ([example](#number-of-logged-in-users)).

##### Configuration

| Name            | Description                                                                                  | Type    | Required | Default |
| --------------- | -------------------------------------------------------------------------------------------- | ------- | -------- | ------- |
| `scan_interval` | The scan interval. Without it, the command will only execute every time the device connects. | integer | no       |         |
| `sensors`       | A list of sensors.                                                                           | list    | yes      |         |

### Sensors

Sensors are updated every time their command executes. Depending on type and configuration, they can appear as sensor, binary sensor, switch, number, text or select entities in Home Assistant.

##### Static sensors

Static sensors are created by default. Each static sensor gets its value from one line of the command output. Static sensors must therefore be defined in the right order ([example](#sensor-command-with-multiple-static-sensors)).

##### Dynamic sensors

Dynamic sensors are created with `dynamic: true`. They can get a variable number of values from the command output and create a "child sensor" for each one of them. To be able to use a dynamic sensor, each line of the command output must contain ID and value of a child sensor with either one or more spaces between them, or a `separator` defined with the sensor ([example](#files-in-a-folder)).

##### Controllable sensors

Both static and dynamic sensors can be made controllable by adding a `command_set` command to their configuration. This command is executed when the user changes the value of the entity. The new value will be passed to the command as variable and can be accessed with `@{value}`. For dynamic sensors, the ID of the current child sensor can be accessed with `@{id}`. Binary sensors can also have the two separate commands `command_on` and `command_off` instead of `command_set` ([example](#setting-in-a-config-file)).

##### Configuration

| Name                              | Description                                                                                                                      | Type    | Required               | Default          |
| --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | ------- | ---------------------- | ---------------- |
| `type`                            | The sensor type (`text`, `number` or `binary`).                                                                                  | string  | yes                    |                  |
| `name`                            | The name of the entity.                                                                                                          | string  | If no `key` specified  |                  |
| `key`                             | The sensor key (can be used in commands).                                                                                        | string  | If no `name` specified | Slugified `name` |
| `dynamic`                         | Set `true` to create a dynamic sensor.                                                                                           | boolean | no                     | `false`          |
| `separator`                       | Separator between ID and value in the command output (only for dynamic sensors).                                                 | string  | no                     |                  |
| `unit_of_measurement`             | The unit of the sensor value.                                                                                                    | string  | no                     |                  |
| `value_template`                  | [Template](https://www.home-assistant.io/docs/configuration/templating) to render the sensor value ([example](#uptime-in-days)). | string  | no                     |                  |
| `command_set`                     | Command to set the sensor value (creates a controllable sensor).                                                                 | string  | no                     |                  |
| `device_class`                    | The [device class](https://www.home-assistant.io/docs/configuration/customizing-devices/#device-class) of the entity.            | string  | no                     |                  |
| `icon`                            | The icon of the entity.                                                                                                          | string  | no                     |                  |
| `entity_registry_enabled_default` | Set `false` to disable the entity by default.                                                                                    | boolean | no                     | `true`           |
| `suggested_unit_of_measurement`   | The suggested unit of the entity.                                                                                                | string  | no                     |                  |
| `suggested_display_precision`     | The suggested display precision of the entity.                                                                                   | integer | no                     |                  |

#### Text type

Sensors with `type: text` appear as [sensor](https://www.home-assistant.io/integrations/sensor) (not controllable), [text](https://www.home-assistant.io/integrations/text) (without `options`) or [select](https://www.home-assistant.io/integrations/select) entities in Home Assistant.

##### Configuration

| Name      | Description                                                                                                                                   | Type    | Required | Default |
| --------- | --------------------------------------------------------------------------------------------------------------------------------------------- | ------- | -------- | ------- |
| `minimum` | The minimum length of the sensor value.                                                                                                       | integer | no       | `0`     |
| `maximum` | The maximum length of the sensor value.                                                                                                       | integer | no       | `100`   |
| `pattern` | A regex pattern that the sensor value has to match.                                                                                           | string  | no       |         |
| `options` | A list of all possible sensor values (use with `command_set` to create a [select](https://www.home-assistant.io/integrations/select) entity). | list    | no       |         |
| `mode`    | Display mode (only for text entities, can be `text` or `password`).                                                                           | string  | no       | `text`  |

#### Number type

Sensors with `type: number` appear as [sensor](https://www.home-assistant.io/integrations/sensor) (not controllable) or [number](https://www.home-assistant.io/integrations/number) entities in Home Assistant.

##### Configuration

| Name      | Description                                                                | Type           | Required | Default |
| --------- | -------------------------------------------------------------------------- | -------------- | -------- | ------- |
| `float`   | Set `true` to enable decimal places for the sensor value.                  | boolean        | no       | `false` |
| `minimum` | The minimum sensor value.                                                  | integer, float | no       | `0.0`   |
| `maximum` | The maximum sensor value.                                                  | integer, float | no       | `100.0` |
| `mode`    | Display mode (only for number entities, can be `auto`, `box` or `slider`). | string         | no       | `auto`  |

#### Binary type

Sensors with `type: binary` appear as [binary sensor](https://www.home-assistant.io/integrations/binary_sensor) (not controllable) or [switch](https://www.home-assistant.io/integrations/switch) entities in Home Assistant.

##### Configuration

| Name          | Description                                                                         | Type   | Required | Default |
| ------------- | ----------------------------------------------------------------------------------- | ------ | -------- | ------- |
| `command_on`  | Command to set the sensor value to `true` (will be used instead of `command_set`).  | string | no       |         |
| `command_off` | Command to set the sensor value to `false` (will be used instead of `command_set`). | string | no       |         |
| `payload_on`  | String to detect a `true` sensor value.                                             | string | no       |         |
| `payload_off` | String to detect a `false` sensor value.                                            | string | no       |         |

### Examples

#### Execute a script

A simple action command that doesn't require variables.

```yaml
# Action command
- command: ~/script.sh
  name: Execute my script
  icon: mdi:script-text-play
```

#### Send the weather forecast

An example of a command that uses a [template](https://www.home-assistant.io/docs/configuration/templating).

```yaml
# Action command with template
- command: echo 'Today will be {{ states("weather.forecast_home") }}' | mail -s "Weather" me@example.com
  name: Send weather forecast
  icon: mdi:weather-partly-cloudy
```

#### Add a note to a file

This command includes a variable. To execute it, [`ssh.run_action`](#run-action-sshrun_action) has to be called with the key `add_note` and a value for `note`.

```yaml
# Action command with variable
- command: echo '@{note}' >> ~/notes.txt
  key: add_note
```

#### Number of logged in users

A simple sensor command with one static sensor. The command returns a number on the first line, which will be the value of the sensor.

```yaml
# Sensor command with static sensor
- command: who --count | awk -F "=" 'NR>1 {print $2}'
  scan_interval: 60
  sensors:
    - type: number
      name: Logged in users
      icon: mdi:account-multiple
```

```shell
# Example output
2
```

#### Uptime in days

In this command, the sensor uses a `value_template` to transform the command output from seconds to days.

```yaml
# Sensor command with static sensor and value template
- command: cat /proc/uptime | awk '{print $1}'
  sensors:
    - type: number
      name: Uptime
      unit_of_measurement: d
      value_template: "{{ value | float  // 86400 }}"
```

```shell
# Example output
248938.30
```

#### IP address

This sensor command includes the value of another sensor with the key `network_interface`.

```yaml
# Sensor command with static sensor and value of another sensor
- command: ip addr show &{network_interface} | awk '/inet/ {print $2}' | cut -f1  -d'/'
  sensors:
    - type: text
      name: IP address
```

```shell
# Example output
192.168.0.123
```

#### CPU information

This command returns the values of four sensors, each on a new line. The sensors must be listed in the same order.

```yaml
# Sensor command with multiple static sensors
- command: 'lscpu | awk -F '': +'' ''/^CPU\(s\)|^Vendor|^Model name|^CPU max/ {print $2}'''
  sensors:
    - type: number
      name: CPU count
    - type: text
      name: CPU vendor
    - type: text
      name: CPU model
    - type: number
      name: CPU MHz max.
```

```shell
# Example output
4
ARM
Cortex-A53
1512.0000
```

#### Setting in a config file

This command returns the current value of the `log_level` setting in a config file. The sensors `command_set` is used to change the value, which makes the sensor controllable and creates a select entity. Without the `options` list, a text entity would be generated.

```yaml
# Sensor command with controllable static sensor
- command: cat /etc/app.conf | awk -F "=" '/^log_level/ {print $2}'
  sensors:
    - type: text
      name: Log level
      command_set: sed -i "s|^log_level=.*|log_level=@{value}|" /etc/app.conf
      options:
        - warning
        - info
        - debug
```

```shell
# Example output
debug
```

#### Files in a folder

Example of a sensor command with dynamic sensor. Each line of the output contains name and size of a file, separated by a comma. When files are added to the folder, new sensor entities are automatically generated in Home Assistant.

```yaml
# Sensor command with dynamic sensor
- command: ls -lp /path/to/folder/ | awk 'NR>1 && !/\// {print $NF "," $5}'
  scan_interval: 600
  sensors:
    - type: number
      name: File
      dynamic: true
      separator: ","
      unit_of_measurement: B
      suggested_unit_of_measurement: MB
      suggested_display_precision: 3
      device_class: data_size
      icon: mdi:file
```

```shell
# Example output
notes.txt,108
script.sh,74
app.conf,384
```

#### Systemd services

Dynamic sensors can be controllable as well. This command returns name and status of two services and creates a switch entity. To start or stop one of the services, `command_on` and `command_off` are used. The service names are used as ID's and can be accessed in both commands with `@{id}`.

```yaml
# Sensor command with controllable dynamic sensor
- command: systemctl -a | awk '/bluetooth.service|smbd.service/ {print $1 "," $4}'
  scan_interval: 300
  sensors:
    - type: binary
      key: service
      dynamic: true
      separator: ","
      command_on: systemctl start @{id}
      command_off: systemctl stop @{id}
      payload_on: running
```

```shell
# Example output
bluetooth.service,running
smbd.service,dead
```

## Services

The following services are available.

#### Execute command (`ssh.execute_command`)

Execute a command on the selected devices.

##### Data

| Name        | Description                       | Type    | Required | Default                       |
| ----------- | --------------------------------- | ------- | -------- | ----------------------------- |
| `command`   | The command to execute.           | string  | yes      |                               |
| `timeout`   | The timeout of the command.       | integer | no       | Command timeout of the device |
| `variables` | Variables to pass to the command. | map     | no       |                               |

#### Run action (`ssh.run_action`)

Run an action on the selected devices.

##### Data

| Name        | Description                       | Type   | Required | Default |
| ----------- | --------------------------------- | ------ | -------- | ------- |
| `key`       | The action key.                   | string | yes      |         |
| `variables` | Variables to pass to the command. | map    | no       |         |

#### Poll sensor (`ssh.poll_sensor`)

Poll one or more sensors.

#### Turn on (`ssh.turn_on`)

Turn the selected devices on.

#### Turn off (`ssh.turn_off`)

Turn the selected devices off.

#### Restart (`ssh.restart`)

Restart the selected devices.
