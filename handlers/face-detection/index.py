import boto3
import logging
import os
import base64
import json
import requests
import base64
from io import BytesIO
from PIL import Image
from requests.structures import CaseInsensitiveDict
import uuid


def encode_file(file):
    file_content = file.read()
    return base64.b64encode(file_content).decode('utf-8')


def get_bbox(raw_bbox):
    vertices = raw_bbox['vertices']
    left = min(point['x'] for point in vertices)
    bottom = max(point['y'] for point in vertices)
    right = max(point['x'] for point in vertices)
    top = min(point['y'] for point in vertices)
    return (int(left), int(top), int(right), int(bottom))


def yv_api(data):
    body = {
        "folderId": os.environ['folder_id'],
        "analyze_specs": [{
            "content": data,
            "features": [{
                "type": "FACE_DETECTION"
            }]
        }]
    }

    headers = CaseInsensitiveDict()
    headers["Authorization"] = "Bearer " + os.environ['token']
    headers["Content-Type"] = "application/json"
    response = requests.post('https://vision.api.cloud.yandex.net/vision/v1/batchAnalyze', headers=headers, json=body)
    response.raise_for_status()
    return response.json()['results'][0]['results'][0]['faceDetection']['faces']


def post_task(queue_url, task_body):
    session = boto3.Session(aws_access_key_id = os.environ['access_key'], aws_secret_access_key = os.environ['secret_key'])
    sqs =  session.client(
        service_name='sqs',
        endpoint_url='https://message-queue.api.cloud.yandex.net',
        region_name='ru-central1'
    )
    response = sqs.send_message(
        QueueUrl=queue_url,
        DelaySeconds=10,
        MessageAttributes={},
        MessageBody=json.dumps(task_body)
    )
    return response


def handler(event, context):
    object_key = event['messages'][0]['details']['object_id']
    
    # если файл не формата '.jpg' - игнорим
    if (str(object_key).endswith('.jpg') == False):
        return {
            'statusCode': 200,
            'body': 'not jpg'
        }

    # получение объекта из бакета
    bucket_name = event['messages'][0]['details']['bucket_id']
    session = boto3.Session(aws_access_key_id = os.environ['access_key'], aws_secret_access_key = os.environ['secret_key'])
    s3 = session.client(
        service_name='s3',
        endpoint_url='https://storage.yandexcloud.net'
    )
    obj = s3.get_object(Bucket = bucket_name, Key = object_key)
    file_size = obj['ContentLength']

    # проверка на превышение допустимого размера в 1 Мб    
    if (int(file_size) > 1000000 ):
        s3.delete_object(obj)
        return {
            'statusCode': 200,
            'body': 'unsupported size'
        }

    # отправка запроса в Yandex Vision для определения координат лиц
    encoded_image = encode_file(obj['Body'])
    faces = yv_api(encoded_image)

    # обработка ответа от Yandex Vision и публикация заданий для обрезки фото в YMQ
    for face in faces:
        # task = CaseInsensitiveDict() #!!!!!!!!!!!!!!!!!!!
        bbox = get_bbox(raw_bbox=face['boundingBox'])
        task = {
            'id': uuid.uuid4().int,
            'obj_key' : object_key,
            'bbox' : bbox
        }

        #send to MQ
        yandex_queue_url = os.environ['yandex_queue_url']
        response = post_task(yandex_queue_url, task)
        logging.info(response)

    return {
        'statusCode': 200
    }