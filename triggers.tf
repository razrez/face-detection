// триггер срабатывает при загрузке файла в бакет vvot43-photos
resource "yandex_function_trigger" "vvot43-photos" {
  name        = "vvot43-photos"
  description = "on create invokes handler vvot43-face-detection"
  object_storage {
    batch_cutoff = 1
    batch_size   = "1"
    create       = true
    delete       = false
    update       = false
    bucket_id    = yandex_storage_bucket.vvot43-photos.id
  }

  function {
    id                 = yandex_function.vvot43-face-detection.id
    service_account_id = yandex_iam_service_account.tsa.id
  }

}

resource "yandex_function_trigger" "vvot43-task" {
  name        = "vvot43-task"
  description = "invokes handler vvot43-face-cut to unload mq"
  message_queue {
    queue_id           = yandex_message_queue.vvot43-tasks.arn
    service_account_id = yandex_iam_service_account.tsa.id
    batch_cutoff       = 10
    batch_size         = 1
  }

  function {
    id                 = yandex_function.vvot43-face-cut.id
    service_account_id = yandex_iam_service_account.tsa.id
  }
}