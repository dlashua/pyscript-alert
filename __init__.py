import time
import math
import voluptuous as vol


MESSAGE_CONDITION = vol.Schema(
    vol.Any(
        {
            vol.Optional('condition', default="True"): str,
            vol.Required('message'): str,
        },
        # vol.All(
        #     str,
        #     lambda x: {"condition": "True", "message": message}
        # )
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

    vol.Optional('app'): __name__.split('.')[-1],
})

def seconds_human(seconds):
    seconds_in_min = 60
    seconds_in_hour = 60 * seconds_in_min
    seconds_in_day = 24 * seconds_in_hour

    ret = []
    r_seconds = seconds
    days = math.floor(r_seconds / seconds_in_day)
    r_seconds = r_seconds - (days * seconds_in_day)
    
    hours = math.floor(r_seconds / seconds_in_hour)
    r_seconds = r_seconds - (hours * seconds_in_hour)

    mins = math.floor(r_seconds / seconds_in_min)
    r_seconds = r_seconds - (mins * seconds_in_min)

    message = ''
    if days > 0:
        if days == 1:
            message += '1 day'
        else:
            message += f'{days} days'

        if hours == 0:
            pass
        elif hours == 1:
            message += f' and 1 hour'
        else:
            message += f' and {hours} hours'

        return message

    if hours > 0:
        if hours == 1:
            message += '1 hour'
        else:
            message += f'{days} hours'

        if mins == 0:
            pass
        elif mins == 1:
            message += f' and 1 minute'
        else:
            message += f' and {mins} minutes'

        return message

    if mins > 0:
        if mins == 1:
            message += '1 minute'
        else:
            message += f'{mins} minutes'

        if r_seconds == 0:
            pass
        else:
            message += f' and {round(r_seconds)} seconds'

        return message

    return f"{round(r_seconds)} seconds"


registered_triggers = []
registered_alerts = []

def make_alert(config):
    # Verify Config
    config = CONFIG_SCHEMA(config)
    # log.info(config)
    # return

    log.info(f'Loading Alert {config["name"]}')

    alert_entity = f'pyscript.alert_{config["name"]}'
    state.persist(
        alert_entity,
        default_value="off",
        default_attributes={
            "count": 0,
            "start_ts": 0
        }
    )

    registered_alerts.append(alert_entity)

    @task_unique(alert_entity)
    @state_trigger(f'True or {config["condition"]} or {config["mute"]}')
    @time_trigger('startup')
    def alert():
        condition_met = eval(config['condition'])
        if not condition_met:
            log.info(f'Alert {config["name"]} Ended')
            state.set(
                alert_entity,
                "off",
                count=0,
                start_ts=0
            )
            return

        mute_met = eval(config['mute'])
        if mute_met:
            log.info(f'Alert {config["name"]} Muted')
            state.set(
                alert_entity,
                "muted"
            )
            return
        
        log.info(f'Alert {config["name"]} Started')

        interval_seconds = config['interval'] * 60

        try: 
            alert_count = int(state.get(f'{alert_entity}.count'))
            alert_start_ts = int(state.get(f'{alert_entity}.start_ts'))
        except:
            alert_count = 0
            alert_start_ts = 0

        if alert_start_ts == 0:
            alert_start_ts = round(time.time())


        while condition_met:
            alert_time_seconds = round(time.time() - alert_start_ts)
            alert_time_minutes = round(alert_time_seconds / 60)
            alert_time_human = seconds_human(alert_time_seconds)

            if alert_time_seconds < 0:
                log.error(f'{alert_entity}: alert_time_seconds < 0: {alert_time_seconds}')

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

            message = eval(f"f'{message_tpl}'")

            if message:
                alert_count = alert_count + 1
                log.info(f'Sending Message: {message}')
                service.call(
                    "notify",
                    config["notifier"],
                    message=message
                )

            state.set(alert_entity, "on", start_ts=alert_start_ts, count=alert_count)

            wait = task.wait_until(
                state_trigger=f'not ({config["condition"]})',
                timeout = interval_seconds,
                state_check_now=True
            )

            if wait['trigger_type'] == 'state':
                condition_met = False

        state.set(
            alert_entity,
            "off",
            count=0,
            start_ts=0
        )

        if alert_count > 0:
            if config['done_message']:
                done_message_tpl = config['done_message']
                done_message = eval(f"f'{done_message_tpl}'")
                if done_message:
                    service.call(
                        "notify",
                        config["notifier"],
                        message=done_message
                    )                


    registered_triggers.append(alert)


def clean_alerts():
    task.sleep(5)
    
    all_pyscript = state.names(domain='pyscript')
    for entity in all_pyscript:
        if not entity.startswith('pyscript.alert_'):
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
    load_apps("alert", make_alert)
    load_apps_list('alert', make_alert)
    clean_alerts()