terraform {
  required_providers {
    yandex = {
      source = "yandex-cloud/yandex"
    }
  }
  required_version = ">= 0.13"
}

provider "yandex" {
  token     = var.token
  cloud_id  = var.cloud_id
  folder_id = var.folder_id
  zone      = var.zone
}

resource "yandex_iam_service_account" "tsa" {
  name        = "tsa"
  folder_id   = var.folder_id
  description = "service account for management via terraform"

}

// назначение роли сервисному аккаунту на папку
resource "yandex_resourcemanager_folder_iam_member" "admin-account-iam" {
  folder_id = var.folder_id
  role      = "admin"
  member    = "serviceAccount:${yandex_iam_service_account.tsa.id}"
}

// генерация статического ключа доступа для сервисного аккаунта
resource "yandex_iam_service_account_static_access_key" "tsa-key" {
  service_account_id = yandex_iam_service_account.tsa.id
  description        = "static access key for sa-terraform"
}

// хранит оригинальные фотографии
resource "yandex_storage_bucket" "vvot43-photos" {
  bucket     = "vvot43-photos"
  access_key = yandex_iam_service_account_static_access_key.tsa-key.access_key
  secret_key = yandex_iam_service_account_static_access_key.tsa-key.secret_key
  acl        = "private"
  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["PUT", "POST"]
    allowed_origins = ["*"]
  }
}

// хранит обрезанные фото лиц
resource "yandex_storage_bucket" "vvot43-faces" {
  bucket     = "vvot43-faces"
  access_key = yandex_iam_service_account_static_access_key.tsa-key.access_key
  secret_key = yandex_iam_service_account_static_access_key.tsa-key.secret_key
  acl        = "private"
  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["PUT", "POST"]
    allowed_origins = ["*"]
  }
}

// очередь с заданиями на обрезание фотографии (ключ, координаты прямоугольника)
resource "yandex_message_queue" "vvot43-tasks" {
  name       = "vvot43-tasks"
  access_key = yandex_iam_service_account_static_access_key.tsa-key.access_key
  secret_key = yandex_iam_service_account_static_access_key.tsa-key.secret_key
}


resource "yandex_ydb_database_serverless" "vvot43-db-photo-face" {
  name                = "vvot43-db-photo-face"
  folder_id           = var.folder_id
  deletion_protection = false
  serverless_database {
    storage_size_limit = var.disk_size
  }
}

// в этой таблице хранится инфа, к какой оригинальной фотографии относится лицо
resource "yandex_ydb_table" "photo-faces" {
  path              = "photo-faces"
  connection_string = yandex_ydb_database_serverless.vvot43-db-photo-face.ydb_full_endpoint

  column {
    type     = "Utf8"
    name     = "id"
    not_null = true
  }

  column {
    type     = "Utf8"
    name     = "photo"
    not_null = false
  }

  column {
    type     = "Utf8"
    name     = "face"
    not_null = false
  }
  
  column {
    type     = "Bool"
    name     = "named"
    not_null = false
  }

  primary_key = ["id"]
}

// обнаружиевает лица и создает задания в MQ {objet_key:coordinates}
resource "yandex_function" "vvot43-face-detection" {
  name               = "vvot43-face-detection"
  user_hash          = "face detection function"
  runtime            = "python312"
  entrypoint         = "index.handler"
  memory             = var.memory
  execution_timeout  = "10"
  service_account_id = yandex_iam_service_account.tsa.id
  environment = {
    folder_id = var.folder_id
    token      = var.token
    bucket     = "vvot43-photos"
    access_key = yandex_iam_service_account_static_access_key.tsa-key.access_key
    secret_key = yandex_iam_service_account_static_access_key.tsa-key.secret_key
    yandex_queue_url = var.yandex_queue_url
  }

  content {
    zip_filename = "./handlers/face-detection/face-detection.zip"
  }
}

// кадрирует лица и сохраняет с рандомным ключом в бд
resource "yandex_function" "vvot43-face-cut" {
  name               = "vvot43-face-cut"
  user_hash          = "cutting function"
  runtime            = "python312"
  entrypoint         = "index.handler"
  memory             = var.memory
  execution_timeout  = "10"
  service_account_id = yandex_iam_service_account.tsa.id
  environment = {
    token                = var.token
    bucket               = "vvot43-photos"
    access_key           = yandex_iam_service_account_static_access_key.tsa-key.access_key
    secret_key           = yandex_iam_service_account_static_access_key.tsa-key.secret_key
    mqName               = yandex_message_queue.vvot43-tasks.name
    ydbConnetctionString = yandex_ydb_table.photo-faces.connection_string
    cloud_id             = var.cloud_id
    folder_id            = var.folder_id
    YDB_ENDPOINT         = yandex_ydb_database_serverless.vvot43-db-photo-face.ydb_full_endpoint
  }

  content {
    zip_filename = "./handlers/face-cut/face-cut.zip"
  }
}

// функция-вебхук для тг бота
resource "yandex_function" "vvot43-boot" {
  name               = "vvot43-boot"
  user_hash          = "first function"
  runtime            = "python312"
  entrypoint         = "index.handler"
  memory             = var.memory
  execution_timeout  = "10"
  service_account_id = yandex_iam_service_account.tsa.id
  environment = {
    token      = var.token
    access_key = yandex_iam_service_account_static_access_key.tsa-key.access_key
    secret_key = yandex_iam_service_account_static_access_key.tsa-key.secret_key
    cloud_id   = var.cloud_id
    folder_id  = var.folder_id
    apigw_id   = yandex_api_gateway.vvot43-apigw.id
    bot_token  = var.bot_token
    YDB_ENDPOINT = yandex_ydb_database_serverless.vvot43-db-photo-face.ydb_full_endpoint
  }

  content {
    zip_filename = "./handlers/boot/boot.zip"
  }
}

resource "yandex_function_iam_binding" "function-iam" {
  function_id = yandex_function.vvot43-boot.id
  role        = "functions.functionInvoker"
  members = [
    "system:allUsers",
  ]
}

// установка vvot43-boot вебхуком для тг бота
data "http" "tg-webhook" {
  url = "https://api.telegram.org/bot${var.bot_token}/setWebhook?url=https://functions.yandexcloud.net/${yandex_function.vvot43-boot.id}"
}

resource "yandex_api_gateway" "vvot43-apigw" {
  folder_id   = var.folder_id
  name        = "vvot43-apigw"
  description = "<описание API-шлюза>"
  labels = {
    label       = "label"
    empty-label = ""
  }

  spec = <<-EOT
    openapi: "3.0.0"
    info:
      version: 1.0.0
      title: Test API
    paths:
      /{photo}:
        get:
          summary: for /find command response
          parameters:
            - name: photo
              in: path
              required: true
              schema:
                type: string
          x-yc-apigateway-integration:
            type: object_storage
            bucket: vvot43-photos
            object: '{photo}'
            service_account_id: ${yandex_iam_service_account.tsa.id}

      /face/{face}:
        get:
          summary: for /getface command response
          parameters:
            - name: face
              in: path
              required: true
              schema:
                type: string
          x-yc-apigateway-integration:
            type: object_storage
            bucket: vvot43-faces
            object: '{face}'
            service_account_id: ${yandex_iam_service_account.tsa.id}
  EOT
}