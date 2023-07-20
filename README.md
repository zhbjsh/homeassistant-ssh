# SSH Integration for Home Assistant

This custom integration allows you to control and monitor devices in Home Assistant by executing commands via SSH.

### Features

- Login with username/password or key file.
- Connect to multiple devices at the same time.
- Turn on devices by Wake on LAN.
- Configure all commands and settings from the UI.
- Default commands for Linux and Windows included and available without configuration.
- Generate sensor, binary sensor, text, select, number and switch entities.
- Get the value of multiple sensors from the output of a single command.
- Use dynamic sensors to automatically add/remove entities.
- Render commands and sensor values with templates.
- Poll sensors manually by calling a service.
- Include sensor values in commands and update them automatically when executing.

## Installation

Download the [latest release](https://github.com/zhbjsh/homeassistant-ssh/releases/latest) and copy the `custom_components/ssh` folder from the zip file to `config/custom_components/` on your Home Assistant installation.

## Device setup

Click on the _Add Integration_ button in _Settings_ -> _Devices & Services_ and select the _SSH_ integration.

##### Key authentication

Key files in the Home Assistant users `~/.ssh/` folder are used automatically. To use another location, enter the path to your _Key file_ (for example `/config/id_rsa`) and make sure the Home Assistant user has access to it.

##### Host key

When connecting to the device, the integration looks for its host key in `~/.ssh/known_hosts`. If the key is missing, you can choose to automatically save it to a _Host keys file_ by enabling the option _Automatically add key to host keys file_.

##### Default commands

Choose the operating system of your device to have a set of default commands available right after setup. This will create some sensors (CPU load, free memory, temperature, etc.) and makes it possible to shutdown and restart the device. The default commands can be modified or deleted later.

##### MAC address

After connecting to the device, setup will ask you to enter the MAC address of the device. Make sure the MAC address is correct, as it is used as unique ID of the device and to turn it on by Wake on LAN.

##### Name

Enter a name for the device to complete the setup. The name is used internally to generate entity IDs and can not be changed later.

## Device configuration

Each device can be configured individually by clicking on the _Configure_ button in _Settings_ -> _Devices & Services_.

##### Allow to turn the device off

To avoid unintentional shutdowns, this function is disabled by default. After enabling it, power button and [`ssh.turn_off`](#turn-off-sshturn_off) service can be used to turn the device off.

##### Update interval

The update interval is the time in seconds between updates of the device state. If the device disconnects (shown by the _SSH Status_ sensor), the integration will try to reconnect to it as long as it replies to ping requests (shown by the _Network Status_ sensor).

### Commands

The [action commands](#action-commands) and [sensor commands](#sensor-commands) of the device can be edited in YAML format inside the configuration window. Default commands selected during setup will show up here. You can modify them, delete them or add your own commands. Be careful when deleting commands, as all entities created by them will become unavailable.

You can test new commands with the [`ssh.execute_command`](#execute-command-sshexecute_command) service in the developer tools. The command output will be visible in the service response.

##### Include templates

[Templates](https://www.home-assistant.io/docs/configuration/templating/) can be used in commands (surrounded by two curly braces), same as with the [Command Line](https://www.home-assistant.io/integrations/command_line/#usage-of-templating-in-command) integration ([example](#action-command-with-template)).

##### Include sensors

Sensors of the same device can be accessed in commands with `#{my_sensor_key}`. The integration will then poll the required sensors once before every execution and include the returned values in the command ([example]()).

##### Include variables

Variables can be passed to action commands (but not in sensor commands) and accessed with `@{my_variable_name}`. Action commands that require variables can only be executed by calling the [`ssh.run_action`](#run-action-sshrun_action) service ([example](#action-command-with-variable)).

##### Configuration

| Name      | Description                 | Type    | Required | Default                       |
| --------- | --------------------------- | ------- | -------- | ----------------------------- |
| `command` | The command to execute.     | string  | yes      |                               |
| `timeout` | The timeout of the command. | integer | no       | Command timeout of the device |

### Action commands

Action commands are executed manually by pressing a button or calling the [`ssh.run_action`]() service. A button entity is created for every action command that doesn’t require variables. ([example](#action-command)).

##### Configuration

| Name           | Description                                             | Type                                                                                               | Required              | Default          |
| -------------- | ------------------------------------------------------- | -------------------------------------------------------------------------------------------------- | --------------------- | ---------------- |
| `name`         | The name of the created button entity.                  | string                                                                                             | If no `key` provided  |                  |
| `key`          | The action key (can be used with [`ssh.run_action`]()). | string                                                                                             | If no `name` provided | Slugified `name` |
| `device_class` | The device class of the button entity.                  | [device_class](https://www.home-assistant.io/docs/configuration/customizing-devices/#device-class) | no                    |                  |
| `icon`         | The icon of the button entity.                          | string                                                                                             | no                    |                  |
| `enabled`      | Set `false` to disable the entity initially.            | boolean                                                                                            | no                    | `true`           |

### Sensor commands

Sensor commands are executed automatically when the device connects or when their `scan_interval` has passed. Each sensor command contains a list of one or more sensors that receive their value from its output ([example](#sensor-command-with-static-sensor)).

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

Dynamic sensors are created with `dynamic: true`. They can get a variable number of values from the command output and create a "child sensor" for each one of them. To be able to use a dynamic sensor, each line of the command output must contain ID and value of a child sensor with either one or more spaces between them, or a `separator` defined with the sensor ([example](#sensor-command-with-dynamic-sensor)).

##### Controllable sensors

Both static and dynamic sensors can be made controllable by adding a `command_set` command to their configuration. This command is executed when the user changes the value of the entity in the UI. The new value will be passed to the command as variable and can be accessed with `@{value}`. For dynamic sensors, the ID of the current child sensor can be accessed with `@{id}`. Binary sensors can also use the two separate commands `command_on` and `command_off` instead of `command_set` ([example](#sensor-command-with-controllable-static-sensor)).

##### Configuration

| Name                            | Description                                                                      | Type                                                                                               | Required              | Default          |
| ------------------------------- | -------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- | --------------------- | ---------------- |
| `type`                          | The sensor type (`text`, `number` or `binary`).                                  | string                                                                                             | yes                   |                  |
| `name`                          | The name of the created entity.                                                  | string                                                                                             | If no `key` provided  |                  |
| `key`                           | The sensor key (can be included in commands).                                    | string                                                                                             | If no `name` provided | Slugified `name` |
| `dynamic`                       | Set `true` for a dynamic sensor.                                                 | boolean                                                                                            | no                    | `false`          |
| `separator`                     | Separator between ID and value in the command output (only for dynamic sensors). | string                                                                                             | no                    |                  |
| `value_template`                | Template to render the sensor value ([example](#sensor-command-with-static-sensor-and-value-template)).                                             | [template](https://www.home-assistant.io/docs/configuration/templating/)                           | no                    |                  |
| `command_set`                   | Command to set the sensor value, makes the sensor controllable.                  | string                                                                                             | no                    |                  |
| `unit_of_measurement`           | The sensor unit.                                                                 | string                                                                                             | no                    |                  |
| `suggested_unit_of_measurement` | The suggested unit of the entity.                                                | string                                                                                             | no                    |                  |
| `suggested_display_precision`   | The suggested display precision of the entity.                                   | integer                                                                                            | no                    |                  |
| `device_class`                  | The device class of the entity.                                                  | [device_class](https://www.home-assistant.io/docs/configuration/customizing-devices/#device-class) | no                    |                  |
| `icon`                          | The icon of the entity.                                                          | string                                                                                             | no                    |                  |
| `enabled`                       | Set `false` to disable the entity initially.                                     | boolean                                                                                            | no                    | `true`           |

#### Text type

Sensors with `type: text` appear as sensor (not controllable), text (without `options`) or select entities in Home Assistant.

##### Configuration

| Name      | Description                                                         | Type    | Required | Default |
| --------- | ------------------------------------------------------------------- | ------- | -------- | ------- |
| `minimum` | The minimum length of the sensor value.                             | integer | no       | `0`     |
| `maximum` | The maximum length of the sensor value.                             | integer | no       | `100`   |
| `pattern` | A regex pattern that the sensor value has to match.                 | string  | no       |         |
| `options` | A list of all possible sensor values (creates a select entity).     | list    | no       |         |
| `mode`    | Display mode (only for text entities, can be `text` or `password`). | string  | no       | `text`  |

#### Number type

Sensors with `type: number` appear as sensor (not controllable) or number entities in Home Assistant.

##### Configuration

| Name      | Description                                                                | Type           | Required | Default |
| --------- | -------------------------------------------------------------------------- | -------------- | -------- | ------- |
| `float`   | Set `true` to enable decimal places for the sensor value.                  | boolean        | no       | `false` |
| `minimum` | The minimum sensor value.                                                  | integer, float | no       | `0.0`   |
| `maximum` | The maximum sensor value.                                                  | integer, float | no       | `100.0` |
| `mode`    | Display mode (only for number entities, can be `auto`, `box` or `slider`). | string         | no       | `auto`  |

#### Binary type

Sensors with `type: binary` appear as binary sensor (not controllable) or switch entities in Home Assistant.

##### Configuration

| Name          | Description                                                                         | Type   | Required | Default |
| ------------- | ----------------------------------------------------------------------------------- | ------ | -------- | ------- |
| `command_on`  | Command to set the sensor value to `true` (will be used instead of `command_set`).  | string | no       |         |
| `command_off` | Command to set the sensor value to `false` (will be used instead of `command_set`). | string | no       |         |
| `payload_on`  | String to detect a `true` sensor value.                                             | string | no       |         |
| `payload_off` | String to detect a `false` sensor value.                                            | string | no       |         |

### Examples

#### Action command

A simple action command that doesn't require variables.

```yaml
- command: ~/script.sh
  name: Execute my script
  icon: mdi:script-text-play
```

#### Action command with template

An example of a command that uses a [template](https://www.home-assistant.io/docs/configuration/templating/).

```yaml
- command: echo 'Today will be {{ states("weather.forecast_home") }}' | mail -s "Weather" me@example.com
  name: Send weather forecast
  icon: mdi:cloud-arrow-right
```

#### Action command with variable

This command includes a variable. To execute it, [`ssh.run_action`]() has to be called with the key `add_note` and a value for `note`.

```yaml
- command: echo '@{note}' >> ~/notes.txt
  key: add_note
```

#### Sensor command with static sensor

A simple sensor command with one static sensor. The command returns a number on the first output line, which will be the value of the sensor.

```yaml
- command: who --count | awk -F "=" 'NR>1 {print $2}'
  scan_interval: 60
  sensors:
    - type: number
      name: Logged in users
      icon: mdi:account-multiple
```

```shell
# Example output:
2
```

#### Sensor command with static sensor and value template

This sensor uses a `value_template` to transform the command output from seconds to days.

```yaml
- command: cat /proc/uptime | awk '{print $1}'
  sensors:
    - type: number
      name: Uptime
      unit_of_measurement: d
      value_template: "{{ value | float  // 86400 }}"
```

```shell
# Example output:
248938.30
```

#### Sensor command with multiple static sensors

This command returns the values of four sensors, each on a new line. The sensors must be listed in the same order.

```yaml
- command: lscpu | awk -F ': +' '/^CPU\(s\)|^Vendor|^Model name|^CPU max/ {print $2}'
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
# Example output:
4
ARM
Cortex-A53
1512.0000
```

#### Sensor command with controllable static sensor

This command returns the current value of the `log_level` setting in a config file. The sensors `command_set` is used to change the value, which makes the sensor controllable and creates a select entity. Without the `options` list, a text entity would be generated.

```yaml
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
# Example output:
debug
```

#### Sensor command with dynamic sensor

Example of a sensor command with dynamic sensor. Each line of the output contains name and size of a file, separated by a comma. When files are added to the folder, new sensor entities are automatically generated in Home Assistant.

```yaml
- command: ls -lp /mnt/backup/ | awk 'NR>1 && !/\// {print $NF "," $5}'
  scan_interval: 600
  sensors:
    - type: number
      name: Backup
      dynamic: true
      separator: ","
      unit_of_measurement: B
      suggested_unit_of_measurement: MB
      device_class: data_size
      icon: mdi:file
```

```shell
# Example output:
notes.txt,108
script.sh,74
app.conf,384
```

#### Sensor command with controllable dynamic sensor

Dynamic sensors can be controllable as well. This command returns name and status of two services and creates a switch entity. To start or stop one of the services, `command_on` and `command_off` are used. The service names are used as ID's and can be accessed in both commands with `@{id}`.

```yaml
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
# Example output:
bluetooth.service,running
smbd.service,dead
```

## Services

The following services are available.

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

#### Turn on (ssh.turn_on)

Turn the selected devices on.

#### Turn off (ssh.turn_off)

Turn the selected devices off.
