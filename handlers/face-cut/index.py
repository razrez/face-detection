import boto3
import os
import base64
import json
import io
import base64
from io import BytesIO
from PIL import Image
import ydb
import ydb.iam


def encode_file(file):
    file_content = file.read()
    return base64.b64encode(file_content).decode('utf-8')


def decode_file(encoded_file):
    decoded_file = base64.b64decode(encoded_file)
    return decoded_file


def crop_image(encoded_image, bbox):
    decoded_image = decode_file(encoded_image)
    image = Image.open(io.BytesIO(decoded_image))
    if (bbox[3] < bbox[1]):
      bbox = (bbox[0], bbox[3], bbox[2], bbox[1],)
    cropped_image = image.crop(bbox)
    return cropped_image


def save_image(image, key_name):
    bucket_name = 'vvot43-faces'
    session = boto3.Session(aws_access_key_id = os.environ['access_key'], aws_secret_access_key = os.environ['secret_key'])
    s3 = session.client(
        service_name='s3',
        endpoint_url='https://storage.yandexcloud.net'
    )

    buffer = BytesIO()
    image.save(buffer, format='JPEG')
    buffer.seek(0)
    
    # Upload the image to the S3 bucket
    s3.upload_fileobj(buffer, bucket_name, key_name)
   

# парсим yandex_ydb_database_serverless.vvot43-db-photo-face.ydb_full_endpoint и инициализурем драйвер
endpoint, database = os.environ['YDB_ENDPOINT'].split('/?database=')
driver = ydb.Driver(
        endpoint=endpoint,
        database=database,
        credentials=ydb.AccessTokenCredentials(os.environ['token'])
    )


def execute_query(session, id_val, photo_val, face_val, ):
    # Create the transaction and execute query.
    query = f"INSERT INTO `photo-faces` (id, photo, face, named) VALUES ('{id_val}', '{photo_val}', '{face_val}', false)"
    return session.transaction().execute(
        query,
        commit_tx=True,
        settings=ydb.BaseRequestSettings().with_timeout(3).with_operation_timeout(2)
    )

  
def handler(event, context):
    message = event['messages'][0]['details']['message']['body']
    message_body = json.loads(message)

    # достанем фото для обрезки лица
    bucket_name = 'vvot43-photos'
    session = boto3.Session(aws_access_key_id = os.environ['access_key'], aws_secret_access_key = os.environ['secret_key'])
    s3 = session.client(
        service_name='s3',
        endpoint_url='https://storage.yandexcloud.net'
    )
    obj = s3.get_object(Bucket = bucket_name, Key = message_body['obj_key'])
    encoded_image = encode_file(obj['Body'])
    
    # обррезаем лицо
    bbox = message_body['bbox']
    cropped_image = crop_image(encoded_image=encoded_image, bbox=bbox)
    uniqId = message_body['id']

    # сохраняем лицо в бакет vvot43-faces
    key = str(uniqId) + ".jpg"
    save_image(image=cropped_image, key_name=key)
    
    # сохраняем инфу в бд
    with driver:
        # wait until driver become initialized
        driver.wait(fail_fast=True, timeout=10)

        # Initialize the session pool instance and enter the context manager.
        # The context manager automatically stops the session pool.
        # On the session pool termination all YDB sessions are closed.
        with ydb.SessionPool(driver) as pool:
            # Execute the query with the `retry_operation_helper` the.
            # The `retry_operation_sync` helper used to help developers
            # to retry YDB specific errors like locks invalidation.
            # The first argument of the `retry_operation_sync` is a function to retry.
            # This function must have session as the first argument.
            execute_query(session=pool.acquire(), id_val=uniqId, photo_val=message_body['obj_key'], face_val=key)

    return {
        'statusCode': 200
    }