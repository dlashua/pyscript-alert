"""Alert"""
# pylint: disable=eval-used,bare-except

import time
# import math
import voluptuous as vol  # pylint: disable=import-error

APP_NAME = __name__.split('.')[-1]

MESSAGE_CONDITION = vol.Schema(
    vol.Any(
        {
            vol.Optional('condition', default="True"): str,
            vol.Required('message'): str,
        },
        # str,
    )
)

CONFIG_SCHEMA = vol.Schema({
    vol.Required('name'): str,
    vol.Required('condition'): str,
    vol.Required('interval'): vol.Any(int, float),
    vol.Required('notifier'): str,
    vol.Required('message'): vol.Any(str, [str, MESSAGE_CONDITION]),
    vol.Optional('mute', default="False"): str,
    vol.Optional('done_message', default=''): str,
    vol.Optional('delay', default=0): vol.Any(int, float),

    vol.Optional('app'): APP_NAME,
})


def seconds_human(seconds):
    seconds_in_min = 60
    seconds_in_hour = 60 * seconds_in_min
    seconds_in_day = 24 * seconds_in_hour

    days = seconds / seconds_in_day
    hours = seconds / seconds_in_hour
    mins = seconds / seconds_in_min

    message = ''
    if days >= 1:
        days = round(days)
        if days == 1:
            message += '1 day'
        else:
            message += f'{days} days'

        return message

    if hours >= 1:
        hours = round(hours)
        if hours == 1:
            message += '1 hour'
        else:
            message += f'{hours} hours'

        return message

    if mins >= 1:
        mins = round(mins)
        if mins == 1:
            message += '1 minute'
        else:
            message += f'{mins} minutes'

        return message

    seconds = round(seconds)
    if seconds == 1:
        return "1 second"

    return f'{seconds} seconds'


registered_triggers = []
registered_alerts = []


def make_alert(config):
    # Verify Config
    config = CONFIG_SCHEMA(config)
    # log.info(config)
    # return

    alert_entity = f'pyscript.{APP_NAME}_{config["name"]}'

    log.info(f'{alert_entity}: Loading')

    state.persist(
        alert_entity,
        default_value="off",
        default_attributes={
            "count": 0,
            "start_ts": 0,
            "last_notify_ts": 0,
        }
    )

    registered_alerts.append(alert_entity)

    @task_unique(alert_entity)
    @state_trigger(f'True or {config["condition"]} or {config["mute"]}')
    @time_trigger('startup')
    def alert():
        try:
            alert_count = float(state.get(f'{alert_entity}.count'))
            alert_start_ts = float(state.get(f'{alert_entity}.start_ts'))
            alert_last_notify_ts = float(
                state.get(f'{alert_entity}.last_notify_ts')
            )
        except:
            alert_count = 0.0
            alert_start_ts = 0.0
            alert_last_notify_ts = 0.0

        condition_met = eval(config['condition'])
        if not condition_met:
            if alert_start_ts > 0:
                log.info(f'{alert_entity}: Ended')

            if alert_count > 0:
                if config['done_message']:
                    done_message_tpl = config['done_message']
                    done_message = eval(f'f"{done_message_tpl}"')
                    if done_message:
                        service.call(
                            "notify",
                            config["notifier"],
                            message=done_message
                        )

            state.set(
                alert_entity,
                "off",
                count=0,
                start_ts=0,
                last_notify_ts=0,
            )

            return

        if alert_start_ts <= 0:
            if config['delay'] > 0:
                log.info(f'{alert_entity}: Delay {config["delay"]}')
                state.set(
                    alert_entity,
                    "delay",
                    count=0,
                    start_ts=0,
                    last_notify_ts=0,
                )
                task.sleep(config['delay'])
            alert_start_ts = time.time()

        mute_met = eval(config['mute'])
        if mute_met:
            log.info(f'{alert_entity}: Muted')
            state.set(
                alert_entity,
                "muted",
                count=alert_count,
                start_ts=alert_start_ts,
                last_notify_ts=alert_last_notify_ts,
            )
            return

        log.info(f'{alert_entity}: Started')

        interval_seconds = config['interval'] * 60

        state.set(
            alert_entity,
            "on",
            start_ts=alert_start_ts,
            count=alert_count,
            last_notify_ts=alert_last_notify_ts,
        )

        while condition_met:
            time_now = time.time()

            alert_next_notify_ts = alert_last_notify_ts + interval_seconds

            if time_now <= alert_next_notify_ts:
                remaining_seconds = round(alert_next_notify_ts - time_now)
                log.info(
                    f'{alert_entity}: Waiting {remaining_seconds} seconds'
                )
                wait = task.wait_until(
                    state_trigger=f'not ({config["condition"]})',
                    timeout=remaining_seconds,
                    state_check_now=True
                )

                if wait['trigger_type'] == 'state':
                    condition_met = False
                    return

            time_now = time.time()
            alert_time_seconds = round(time_now - alert_start_ts)
            alert_time_minutes = (  # pylint: disable=unused-variable
                round(alert_time_seconds / 60)
            )
            alert_time_human = (  # pylint: disable=unused-variable
                seconds_human(alert_time_seconds)
            )

            if alert_time_seconds < 0:
                log.error(
                    f'{alert_entity}: alert_time_seconds < 0: {alert_time_seconds}'
                )

            message_tpl = ''
            if isinstance(config['message'], str):
                message_tpl = config['message']
            else:
                for message_option in config['message']:
                    if isinstance(message_option, str):
                        message_tpl = message_option
                        break

                    message_option_eval = eval(message_option['condition'])
                    if message_option_eval:
                        message_tpl = message_option['message']
                        break
            try:
                message = eval(f'f"{message_tpl}"')
            except Exception as e:
                log.error(
                    f'{alert_entity}: Error in template eval. {message_tpl}'
                )
                raise e

            alert_last_notify_ts = time.time()

            state.set(
                alert_entity,
                "on",
                start_ts=alert_start_ts,
                count=alert_count,
                last_notify_ts=alert_last_notify_ts,
            )

            if message:
                alert_count = alert_count + 1
                log.info(f'Sending Message #{alert_count}: {message}')
                service.call(
                    "notify",
                    config["notifier"],
                    message=message
                )

    registered_triggers.append(alert)


def clean_alerts():
    task.sleep(5)

    all_pyscript = state.names(domain='pyscript')
    for entity in all_pyscript:
        if not entity.startswith(f'pyscript.{APP_NAME}_'):
            continue

        if entity in registered_alerts:
            continue

        log.info(f'Cleaning Alert {entity}')
        task.unique(entity)
        state.set(
            entity,
            "unavailable",
        )


##########
# Helpers
##########
def load_apps(app_name, factory):
    if "apps" not in pyscript.config:
        return

    if app_name not in pyscript.config['apps']:
        return

    for app in pyscript.config['apps'][app_name]:
        factory(app)


def load_apps_list(app_name, factory):
    if "apps_list" not in pyscript.config:
        return

    for app in pyscript.config['apps_list']:
        if 'app' in app:
            if app['app'] == app_name:
                factory(app)


##########
# Startup
##########
@time_trigger('startup')
def load():
    load_apps(APP_NAME, make_alert)
    load_apps_list(APP_NAME, make_alert)
    clean_alerts()
