variable "cloud_id" {
  type = string
}

variable "yandex_queue_url" {
  type = string
}

variable "folder_id" {
  type = string
}

variable "token" {
  type = string
}

variable "bot_token" {
  type    = string
}

variable "zone" {
  type    = string
  default = "ru-central1-b"
}


variable "cores" {
  type    = number
  default = 2
}

variable "memory" {
  type    = number
  default = 128
}

variable "disk_size" {
  type    = number
  default = 5
}

variable "timeout_create" {
  default = "10m"
}

variable "timeout_delete" {
  default = "10m"
}

