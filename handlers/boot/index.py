import logging
import os
import json
from telegram import Update, Bot, Message, PhotoSize
import ydb
import ydb.iam

BOT_TOKEN = os.environ['bot_token']
APIGW_ID = os.environ['apigw_id']
ERROR_MESSAGE = 'Ошибка'

# Create a Bot instance
bot = Bot(token=BOT_TOKEN)

def execute_query(session, query):
    # Create the transaction and execute query.
    logging.info(f"EXECUTING: {query}")
    return session.transaction().execute(
        query,
        commit_tx=True,
        settings=ydb.BaseRequestSettings().with_timeout(3).with_operation_timeout(2)
    )


def get_unnamed_face():
    try:
        endpoint, database = os.environ['YDB_ENDPOINT'].split('/?database=')
        driver = ydb.Driver(
            endpoint=endpoint,
            database=database,
            credentials=ydb.AccessTokenCredentials(os.environ['token'])
        )
        with driver:
            driver.wait(fail_fast=True, timeout=10)
            with ydb.SessionPool(driver) as pool:
                result = execute_query(session=pool.acquire(), query=f"SELECT face FROM `photo-faces` WHERE named = false LIMIT 1")
                facekey = result[0].rows[0].face
                logging.info(f"RESULT: {facekey}")
                return facekey

    except Exception as e:
        print(f"Error occurred: {e}")
        return None


def find_photos(name):
    try:
        endpoint, database = os.environ['YDB_ENDPOINT'].split('/?database=')
        driver = ydb.Driver(
            endpoint=endpoint,
            database=database,
            credentials=ydb.AccessTokenCredentials(os.environ['token'])
        )
        with driver:
            # wait until driver become initialized
            driver.wait(fail_fast=True, timeout=10)
            with ydb.SessionPool(driver) as pool:
                result = execute_query(session=pool.acquire(), query=f"SELECT photo FROM `photo-faces` WHERE named = true and face = '{name}'")
                photo_keys = [row.photo for row in result[0].rows]
                return photo_keys

    except Exception as e:
        print(f"Error occurred: {e}")
        return None


def rename_ydb(newFacekey, oldFacekey):
    try:
        endpoint, database = os.environ['YDB_ENDPOINT'].split('/?database=')
        driver = ydb.Driver(
            endpoint=endpoint,
            database=database,
            credentials=ydb.AccessTokenCredentials(os.environ['token'])
        )
        with driver:
            # wait until driver become initialized
            driver.wait(fail_fast=True, timeout=10)
            with ydb.SessionPool(driver) as pool:
                session = pool.acquire()
                return execute_query(session, f"UPDATE `photo-faces` SET named = true, face = '{newFacekey}' WHERE face = '{oldFacekey}' AND named = false")
                
    except Exception as e:
        print(f"Error occurred: {e}")
        return None


async def handle(update: Update):
    bot = update.get_bot()

    if update.message.text.startswith('/start'):
        # тут можно сообщение отправить с инструкцией
        return {
            'statusCode': 200
        }

    if update.message.text.startswith('/getface'):
        # найдем лицо без имени
        facekey = get_unnamed_face()

        # если лицо нашлось
        if facekey != None:
            logging.info(f"FACEKEY: {facekey}")

            # Send face photo
            face_url = f"https://{APIGW_ID}.apigw.yandexcloud.net/face/{facekey}"
            return await bot.send_photo(chat_id=update.message.chat_id, photo=face_url, caption = facekey)

    elif update.message.text.startswith('/find'):
        # Get the parameters of the /find command
        name = update.message.text.removeprefix('/find ')
        if name != '':
            # найдем все фото, где есть {name}
            photo_names = find_photos(f"{name}.jpg")
            logging.info(f"PHOTOS: {photo_names}")

            if len(photo_names) > 0:
                for photo_name in photo_names:
                    # Send photo
                    photo_url = f"https://{APIGW_ID}.apigw.yandexcloud.net/{photo_name}"
                    await bot.send_photo(chat_id=update.message.chat_id, photo=photo_url)

                return
        
        return await bot.send_message(chat_id=update.message.chat_id, text=f"Фотографии с {{ {name.removeprefix('.jpg')} }} не найдены")

    # если это ответ на сообщение
    elif update.message.reply_to_message != None:
        # сообщение, на которое был дан ответ
        reply = update.message.reply_to_message
        newFacekey = update.message.text + ".jpg"
        oldFacekey = reply.caption
        logging.info(f"newFacekey: {newFacekey}")
        logging.info(f"oldFacekey: {oldFacekey}")

        rename_res = rename_ydb(newFacekey=newFacekey, oldFacekey=oldFacekey)

        if rename_res is not None:
            return await bot.send_message(chat_id=update.message.chat_id, text="переименовано.")

    # smth undefined
    return await bot.send_message(chat_id=update.message.chat_id, text=ERROR_MESSAGE)


async def handler(event, context):
    logging.getLogger().setLevel(logging.DEBUG)

    # ловим обновление
    update = Update.de_json(data=json.loads(event['body']), bot=bot)
    
    # если это НЕ текстовое сообщение
    if update.message.text is None:
        await bot.send_message(chat_id=update.message.chat_id, text=ERROR_MESSAGE)
        return {
            'statusCode': 200
        }
    
    # обработка команд
    await handle(update)

    return {
        'statusCode': 200
    }