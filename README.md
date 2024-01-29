!!!Время жизни IAM-токена — не больше 12 часов, но рекомендуется запрашивать его чаще, например каждый час!!!

CLI конфиг терраформа:
New-Item -ItemType Directory -Force -Path "$env:APPDATA"
New-Item -ItemType File -Force -Path "$env:APPDATA\terraform.rc"

Установка расположения конфиг файла в переменную окружения:
$Env:TF_CLI_CONFIG_FILE=C:\Users\useraname\AppData\terraform.rc 

обновление iam токена
$IAM_TOKEN=yc iam create-token
curl.exe -H "Authorization: Bearer $IAM_TOKEN" https://resource-manager.api.cloud.yandex.net/resource-manager/v1/clouds
_______________________________________________________________________________________________

создание сервисного аккаунта и назначение роли:
yc iam service-account create --name terraform-sa
yc resource-manager folder add-access-binding vvot43 --role admin --subject serviceAccount:aje0vi6mhkm76itber2m

Создайте авторизованный ключ для сервисного аккаунта и запишите его файл:
yc iam key create --service-account-name terraform-sa --folder-name vvot43 --output key.json

Создайте профиль CLI для выполнения операций от имени сервисного аккаунта.
yc config profile create terraform-sa

Задайте конфигурацию профиля:
yc config set service-account-key key.json
yc config set cloud-id b1g71e95h51okii30p25
yc config set folder-id b1g7rlm620k8mplrm2sk

Добавьте аутентификационные данные в переменные окружения:
$Env:YC_TOKEN=$(yc iam create-token)
$Env:YC_CLOUD_ID=$(yc config get cloud-id)
$Env:YC_FOLDER_ID=$(yc config get folder-id)

_______________________________________________________________________________________________

# Подключаем провайдер
terraform init

Проверьте конфигурацию командой:
terraform validate

Отформатируйте файлы конфигураций в текущем каталоге и подкаталогах:
terraform fmt

Если в конфигурации есть ошибки, Terraform на них укажет:
terraform plan

Чтобы создать ресурсы выполните команду:
terraform apply

Чтобы удалить ресурсы, созданные с помощью Terraform:
terraform destroy

_______________________________________________________________________________________________

auth to Container Registry:
docker login \
  --username oauth \
  --password <OAuth-токен> \
  cr.yandex


yc serverless function invoke d4e0o8ssi9ac******* -d '{"queryStringParameters": {"name": "username"}}'
