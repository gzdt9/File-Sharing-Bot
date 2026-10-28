#(©)CodeXBotz

import secrets

import pymongo, os
from config import DB_URI, DB_NAME

dbclient = pymongo.MongoClient(DB_URI)
database = dbclient[DB_NAME]
user_data = database['users']
file_codes = database['file_codes']
file_codes.create_index('code', unique=True)

async def present_user(user_id : int):
    found = user_data.find_one({'_id': user_id})
    return bool(found)

async def add_user(user_id: int):
    user_data.insert_one({'_id': user_id})
    return

async def full_userbase():
    user_docs = user_data.find()
    user_ids = []
    for doc in user_docs:
        user_ids.append(doc['_id'])
        
    return user_ids

async def del_user(user_id: int):
    user_data.delete_one({'_id': user_id})
    return


async def create_file_code(message_id: int) -> str:
    """Create a short, unguessable pickup code for one channel message."""
    for _ in range(10):
        code = secrets.token_urlsafe(6).replace('-', '').replace('_', '').upper()[:8]
        try:
            file_codes.insert_one({'code': code, 'message_id': message_id})
            return code
        except pymongo.errors.DuplicateKeyError:
            continue
    raise RuntimeError('Could not create a unique pickup code')


async def get_file_message_id(code: str):
    record = file_codes.find_one({'code': code.upper()})
    return record['message_id'] if record else None
