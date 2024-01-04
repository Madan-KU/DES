import os
import sys
import yaml
import logging


def configure_logger(config_path='parameters.yaml'):
    with open(config_path, 'r') as file:
        config = yaml.safe_load(file)

    log_file_path = config['logging']['log_file']

    log_dir = os.path.dirname(log_file_path)
    os.makedirs(log_dir, exist_ok=True)

    logging.basicConfig(level=config['logging']['level'],
                        format='%(asctime)s [%(levelname)s] [%(filename)s:%(lineno)d] - %(message)s',
                        handlers=[logging.FileHandler(log_file_path),
                                  logging.StreamHandler()])


    logging.Logger.manager.setLoggerClass(logging.Logger)
    logging.addLevelName(logging.INFO, 'INFO')
    logging.addLevelName(logging.DEBUG, 'DEBUG')
    logging.addLevelName(logging.WARNING, 'WARNING')
    logging.addLevelName(logging.ERROR, 'ERROR')
    logging.addLevelName(logging.CRITICAL, 'CRITICAL')

    class InfoFilter(logging.Filter):
        def filter(self, record):
            record.filename = os.path.splitext(os.path.basename(record.filename))[0]
            return True

    logging.getLogger().addFilter(InfoFilter())
