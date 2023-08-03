from configparser import ConfigParser
import psycopg2
import logging

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
    """ Connect to the PostgreSQL database server """
    conn = None
    try:
        # read connection parameters
        conn = get_database_connection()
		
        # create a cursor
        cur = conn.cursor()
        
	    # execute a statement
        log.info('PostgreSQL database version:')
        db_version = execute_select_statement(cur, 'SELECT version()')
        log.info(db_version)
	    # close the communication with the PostgreSQL
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        log.error(error)
    finally:
        if conn is not None:
            conn.close()
            log.info('Database connection closed.')

def execute_select_statement(cur, statement):
    cur.execute(statement)

        # display the PostgreSQL database server version
    return cur.fetchall()

def execute_modify_statement(cur, statement):
    cur.execute(statement)

        # display the PostgreSQL database server version
    return cur.statusmessage()

def get_database_connection():
    # connect to the PostgreSQL server
    log.info('Connecting to the PostgreSQL database...')
    return psycopg2.connect(**config())