# alert

## What Does it Do?

`alert` is a replacement for built-in Home Assistant Alerts. It provides more features than the native integration, is easier to configure complex scenarios, and the alert status will be maintained through a Home Assistant restart.

## Using it!

This works as an "app" in `pyscript`. Therefore, pyscript is required and configuration is done through Home Assistant's `configuration.yaml` file.

You can see a [full configuration example](config.sample.yaml) in this repository.

These are the configuration keys:

> **name** (required)
>
> The unique name for this alert. If two alerts have the same name, they will conflict with each other.
>
> ```
> name: my_alert
> ```

> **condition** (required)
> 
> The condition for this alert. When this is `True` the alert will be active.
>
> ```
> condition: input_boolean.test_1 == 'on'
> ```

> **interval** (required)
> 
> Time in **minutes** between each alert.
>
> ```
> minutes: 5
> ```

> **notifier** (required)
>
> The name of the `notify.` service that should be used for notifications. The domain should not be included.
> 
> ```
> notifier: my_notifier
> ```

> **message** (required)
> 
> In it's simplest form, it is a string to send as a notification at each interval.
>
> ```
> message: Your front door is open.
> ```
>
> Alternately, variables can be included in the message. They are `alert_time_seconds`, `alert_time_minutes`, `alert_count`, and `alert_time_human`.
> 
> ```
> message: Your front door has been open for {alert_time_human}.
> ```
>
> A more complex value for message can evaluate condtions and send a paricular message based on those conditions. A `list` of `dict`s is used for this functionality.
>
> ```
> message:
>   - condition: alert_count == 0
>     message: Your Front Door is Open
>   - condition: alert_count > 0 and alert_count < 100
>     message: Your Front Door has been Open for {alert_time_human}
>   - condition: alert_count >= 100
>     message: Your Front Door has been Open for a long time. Have you run away to Neverland?
> ```

> **mute** (optional)
>
> A condition that will mute this alert. When `True`, the alert will still be active but not sending notifications. As soon as the mute condition is `False`, a notification will be sent.



## Requirements

* [PyScript custom_component](https://github.com/custom-components/pyscript)

## Install

### Install this script
```
# get to your homeassistant config directory
cd /config

cd pyscript
mkdir -p apps/
cd apps
git clone https://github.com/dlashua/pyscript-alert alert
```

### Edit `configuration.yaml`

```yaml
pyscript:
  apps:    
    alert:
      - name: test_one
        condition: input_boolean.test_1 == 'on'
        mute: input_boolean.test_2 == 'on'
        interval: 5
        message:
          - condition: alert_count == 1
            message: Test One is On. Please Turn it Off.
          - condition: alert_count > 1
            message: Test One has been On for {alert_time_human}. Please Turn it off.
        notifier: my_notify
```

### Reload PyScript
