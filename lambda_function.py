import boto3
import logging
import os

target_var_name = 'MIRROR_TARGET_ID'
filter_var_name = 'MIRROR_FILTER_ID'
skip_tags_var_name = 'MIRROR_SKIP_TAGS'
log_level_var_name = 'LAMBDA_LOG_LEVEL'

logging.basicConfig()
logger = logging.getLogger()
logger.setLevel(os.getenv(log_level_var_name, 'WARNING'))

ec2 = boto3.client('ec2')


class Config:
    target_id: list
    filter_id: str
    skip_tags: dict

    def __init__(self, target_id, filter_id, skip_tags):
        if target_id != None:
            self.target_id = target_id
        else:
            raise Exception('{} variable is empty'.format(target_var_name))
        if filter_id != None:
            self.filter_id = filter_id
        else:
            raise Exception('{} variable is empty'.format(filter_var_name))
        self.skip_tags = {}
        if skip_tags != None:
            tag_list = skip_tags.split(',')
            for tag in tag_list:
                kv = tag.split('=')
                if len(kv[0]) > 0:
                    if len(kv) == 2:
                        self.skip_tags[kv[0]] = kv[1]
                    else:
                        self.skip_tags[kv[0]] = None


class Instance:
    network_interfaces: str
    instance_id: str


config = Config(target_id=os.getenv(target_var_name, None),
                filter_id=os.getenv(filter_var_name, None),
                skip_tags=os.getenv(skip_tags_var_name, None))


def start_session(network_interface_id, session_number):
    logger.info('Setting up a mirror session for interface: %s, target: %s and filter: %s',
                network_interface_id, config.target_id, config.filter_id)

    response = ec2.create_traffic_mirror_session(NetworkInterfaceId=network_interface_id,
                                                 TrafficMirrorTargetId=config.target_id,
                                                 TrafficMirrorFilterId=config.filter_id,
                                                 SessionNumber=session_number)

    logger.info('Traffic mirror session has been started: %s', response)


def get_available_session_number(interface_id):
    interface_filter = {
        'Name': 'network-interface-id', 'Values': [interface_id]}
    interface_mirror_sessions = ec2.describe_traffic_mirror_sessions(
        Filters=[interface_filter])['TrafficMirrorSessions']
    session_exists = any(map(lambda a:
                             a['TrafficMirrorTargetId'] == config.target_id and
                             a['TrafficMirrorFilterId'] == config.filter_id and
                             a['NetworkInterfaceId'] == interface_id, interface_mirror_sessions))
    if session_exists:
        logging.info('A session exists for interface %s and target %s',
                     interface_id, config.target_id)
        return None
    else:
        return len(interface_mirror_sessions) + 1


def get_instance_id(event):
    if 'detail-type' in event.keys() and 'EC2 Instance State-change Notification' in event['detail-type']:
        return event['detail']['instance-id']
    else:
        return None


def get_instance_config(instance_id):
    response = ec2.describe_instances(InstanceIds=[instance_id])
    if len(response['Reservations']) == 0:
        return None
    instance = Instance()
    instance.instance_id = instance_id
    instance.network_interfaces = list(
        map(lambda x: x['NetworkInterfaceId'], response['Reservations'][0]['Instances'][0]['NetworkInterfaces']))
    return instance


def get_list_instances_to_skip():
    skip_instances = []
    for k, v in config.skip_tags.items():
        skip_filter = []
        if v != None:
            skip_filter.append({'Name': 'tag:{}'.format(k), 'Values': [v]})
        else:
            skip_filter.append({'Name': 'tag-key', 'Values': [k]})
        response = ec2.describe_instances(Filters=skip_filter)
        logging.info('Got response (%s) for key %s', response, k)
        for reservation in response['Reservations']:
            skip_instances.extend(
                map(lambda x: x['InstanceId'], reservation['Instances'])
            )
    logging.info('Instances (%s) match tags', ', '.join(skip_instances))
    return skip_instances


def lambda_handler(event, context):
    logger.info('Processing event: %s', event)
    instances_to_skip = get_list_instances_to_skip()
    instance_id = get_instance_id(event)
    if instance_id in instances_to_skip:
        logger.warning('Instance %s has been skipped because of tags %s',
                       instance_id, config.skip_tags)
        return

    instance = get_instance_config(instance_id)
    if not instance:
        logger.warning(
            'The event is invalid or instance is not found: %s', event)
        return

    logger.info('Got the instance config: %s', instance_id)
    for interface_id in instance.network_interfaces:
        new_session_number = get_available_session_number(interface_id)
        if new_session_number != None:
            try:
                start_session(interface_id, new_session_number)
            except Exception as e:
                logger.error('Failed to setup traffic mirror session for interface %s: %s',
                             interface_id, e)
