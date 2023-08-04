from peewee import *
import logging
from configparser import ConfigParser

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

def get_database_connection() -> PostgresqlDatabase:
    # connect to the PostgreSQL server
    log.info('Connecting to the PostgreSQL database...')
    return PostgresqlDatabase(
        **config()
    )

class UnknownField(object):
    def __init__(self, *_, **__): pass

class BaseModel(Model):
    class Meta:
        database = get_database_connection()

class User(BaseModel):
    id = BigAutoField(column_name='ID',primary_key=True)
    is_bot = BooleanField(column_name='IS_BOT', null=True)
    mention = CharField(column_name='MENTION', null=True)
    username = CharField(column_name='USERNAME', null=True)

    class Meta:
        table_name = 'USER'

class Guild(BaseModel):
    description = CharField(column_name='DESCRIPTION', null=True)
    id = BigAutoField(column_name='ID',primary_key=True)
    name = CharField(column_name='NAME', null=True)
    owner = ForeignKeyField(column_name='OWNER_ID', field='id', model=User, null=True)

    class Meta:
        table_name = 'GUILD'

class Channel(BaseModel):
    guild = ForeignKeyField(column_name='GUILD_ID', field='id', model=Guild, null=True)
    id = BigAutoField(column_name='ID',primary_key=True)
    mention = CharField(column_name='MENTION', null=True)
    name = CharField(column_name='NAME', null=True)
    parent = ForeignKeyField(column_name='PARENT_ID', field='id', model='self', null=True)
    type = CharField(column_name='TYPE', null=True)

    class Meta:
        table_name = 'CHANNEL'

class Authorized(BaseModel):
    channel = ForeignKeyField(column_name='CHANNEL_ID', field='id', model=Channel, null=True)
    id = BigAutoField(column_name='ID')
    user = ForeignKeyField(column_name='USER_ID', field='id', model=User, null=True)

    class Meta:
        table_name = 'AUTHORIZED'

class Emoji(BaseModel):
    id = BigAutoField(column_name='ID',primary_key=True)
    mention = CharField(column_name='MENTION', null=True)
    name = CharField(column_name='NAME', null=True)
    url = CharField(column_name='URL', null=True)
    url_name = CharField(column_name='URL_NAME', null=True)
    guild = ForeignKeyField(column_name='GUILD_ID', field='id', model=Guild, null=True)

    class Meta:
        table_name = 'EMOJI'

class Event(BaseModel):
    creator = ForeignKeyField(column_name='CREATOR_ID', field='id', model=User, null=True)
    description = CharField(column_name='DESCRIPTION', null=True)
    guild = ForeignKeyField(column_name='GUILD_ID', field='id', model=Guild, null=True)
    id = BigAutoField(column_name='ID',primary_key=True)
    name = CharField(column_name='NAME', null=True)
    start_time = DateTimeField(column_name='START_TIME', null=True)
    status = IntegerField(column_name='STATUS', null=True)

    class Meta:
        table_name = 'EVENT'

class Message(BaseModel):
    author = ForeignKeyField(column_name='AUTHOR_ID', field='id', model=User, null=True)
    channel = ForeignKeyField(column_name='CHANNEL_ID', field='id', model=Channel, null=True)
    content = CharField(column_name='CONTENT', null=True)
    edited_at = DateTimeField(column_name='EDITED_AT', null=True)
    guild = ForeignKeyField(column_name='GUILD_ID', field='id', model=Guild, null=True)
    id = BigAutoField(column_name='ID',primary_key=True)
    sent_at = DateTimeField(column_name='SENT_AT', null=True)
    type = IntegerField(column_name='TYPE', null=True)

    class Meta:
        table_name = 'MESSAGE'

class Track(BaseModel):
    channel = ForeignKeyField(column_name='CHANNEL_ID', field='id', model=Channel, null=True)
    creator = ForeignKeyField(column_name='CREATOR_ID', field='id', model=User, null=True)
    custom = BooleanField(column_name='CUSTOM', constraints=[SQL("DEFAULT false")], null=True)
    event = ForeignKeyField(column_name='EVENT_ID', field='id', model=Event, null=True)
    id = BigAutoField(column_name='ID',primary_key=True)
    message = ForeignKeyField(column_name='MESSAGE_ID', field='id', model=Message, null=True)

    class Meta:
        table_name = 'TRACK'

class Roster(BaseModel):
    id = BigAutoField(column_name='ID',primary_key=True)
    track = ForeignKeyField(column_name='TRACK_ID', field='id', model=Track, null=True)
    updated_at = DateTimeField(column_name='UPDATED_AT', null=True)

    class Meta:
        table_name = 'ROSTER'

class RosterEntry(BaseModel):	
    created_at = DateTimeField(column_name='CREATED_AT', null=True)	
    emoji = ForeignKeyField(column_name='EMOJI_ID', field='id', model=Emoji, null=True)	
    id = IntegerField(column_name='ID', constraints=[SQL("DEFAULT nextval('\"ROSTER_ENTRY_ID_seq\"'::regclass)")])	
    main = BooleanField(column_name='MAIN', constraints=[SQL("DEFAULT false")], null=True)	
    roster = ForeignKeyField(column_name='ROSTER_ID', field='id', model=Roster)	
    status = IntegerField(column_name='STATUS', constraints=[SQL("DEFAULT 1")], null=True)	
    updated_at = DateTimeField(column_name='UPDATED_AT', null=True)	
    user = ForeignKeyField(column_name='USER_ID', field='id', model=User, null=True)

    class Meta:
        table_name = 'ROSTER_ENTRY'
        indexes = (
            ((), True),
        )
        primary_key = CompositeKey('id', 'roster')
