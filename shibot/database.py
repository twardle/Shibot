
from peewee import *
import logging
from shibot import model as em

log = logging.getLogger(__name__)
info_handler = logging.FileHandler('log/shibot.log')
info_handler.setLevel(logging.INFO)
log.addHandler(info_handler)
error_handler = logging.FileHandler('log/shibot_error.log')
error_handler.setLevel(logging.ERROR)
log.addHandler(error_handler)

def version():
    # read connection parameters
    db : PostgresqlDatabase = em.get_database_connection()
    
    with db:
        cursor = db.execute_sql('SELECT version()')
        log.info(cursor.fetchone())

def sample_query():
    query = em.Guild.select()
    
    log.info(query)
    
    for guild in query:
        log.info(guild.name)