import logging.config
from pythonjsonlogger import jsonlogger
from services.service import get_plugin_info


##This is to add custom keys
class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        log_record['level'] = record.levelname
        log_record['instance'] = str(get_plugin_info().instance_id)
        log_record['plugin_name'] = str(get_plugin_info().name)
        log_record['plugin_version'] = str(get_plugin_info().version)
        log_record['plugin_version'] = str(get_plugin_info().version)
        # log_record['plugin_id'] = str(get_plugin_info().id)


LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'rich.logging.RichHandler',
            'formatter': 'detailed',
        },
        'console2': {
            'class': 'logging.StreamHandler',
            'formatter': 'json',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'app.log',
            'maxBytes': 1024 * 1024 * 5,  # 5 MB
            'backupCount': 5,
            'formatter': 'json',
        },
        # 'logstash': {
        #     'class': 'logstash.TCPLogstashHandler',
        #     'host': 'your_logstash_host',  # Replace with your Logstash host
        #     'port': 5000,  # Replace with your Logstash port
        #     'version': 1,
        #     'message_type': 'python-logstash',
        #     'formatter': 'logstash',
        # },
    },
    'formatters': {
        'json': {
            '()': CustomJsonFormatter,
            'format': "(asctime)s  [%(levelname)s] %(filename)s:%(lineno)d  %(name)s: %(message)s",
        },
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        },
        'detailed': {
            'format': '%(asctime)s [%(levelname)s] %(name)s %(filename)s:%(lineno)d - %(message)s',
        },
    },
    'root': {
        'level': 'INFO',
        'handlers': ['console', 'file'],
    },
    'loggers': {
        'uvicorn': {
            'level': 'INFO',
            'handlers': ['console'],
            'propagate': False
        },
    },
}


def setup_logging():
    logging.config.dictConfig(LOGGING_CONFIG)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)