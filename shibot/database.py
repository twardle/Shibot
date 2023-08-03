from configparser import ConfigParser
import psycopg2
import logging
import peewee

log = logging.getLogger(__name__)
info_handler = logging.FileHandler('log/shibot.log')
info_handler.setLevel(logging.INFO)
log.addHandler(info_handler)
error_handler = logging.FileHandler('log/shibot_error.log')
error_handler.setLevel(logging.ERROR)
log.addHandler(error_handler)

def config(filename='cfg/database.ini', section='postgresql'):
    parser = ConfigParser()
    # read config file
    parser.read(filename)

    if not parser.has_section(section):
        raise ImportError('Section {0} not found in the {1} file'.format(section, filename))

    params = parser.items(section)
    return {param[0]: param[1] for param in params}

def version():
    # read connection parameters
    db : peewee.PostgresqlDatabase = get_database_connection()
    
    with db:
        cursor = db.execute_sql('SELECT version()')
        log.info(cursor.fetchone())

def get_database_connection() -> peewee.PostgresqlDatabase:
    # connect to the PostgreSQL server
    log.info('Connecting to the PostgreSQL database...')
    return peewee.PostgresqlDatabase(
        **config()
    )