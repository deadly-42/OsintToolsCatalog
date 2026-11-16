# OsintToolsCatalog

Каталог OSINT-инструментов в терминале: **10 категорий, 300+ ссылок** и встроенный мини-поиск публичных профилей по нику на **127 сайтах**.

Поставьте звезду что б продвинуть пост ❤️

## Установка

```bash
Способ 1: 

pip install git
python -m pip install .
python -m pip install git+https://github.com/deadly-42/OsintToolsCatalog.git
python -m osinttoolscatalog

Способ 2:

pip install git
git clone https://github.com/deadly-42/OsintToolsCatalog.git
cd OsintToolsCatalog
python -m pip install .
python -m osinttoolscatalog
```

## Запуск (главное меню)

```bash
python -m osinttoolscatalog

Запустить мини-поиск от разработчика (deadly-42)
python -m osinttoolscatalog search username (без @)
```

Откроется меню: введите цифру от 0 до 10 (0 — выход).

## Команды

```bash
python -m osinttoolscatalog list                 # список категорий
python -m osinttoolscatalog list 3               # инструменты категории 3
python -m osinttoolscatalog search ник           # мини-поиск по нику
python -m osinttoolscatalog search ник --details --all -o results.json
python -m osinttoolscatalog check-links          # проверить ссылки каталога
python -m osinttoolscatalog version
```

В конце `search` выводится итог: в скольких источниках аккаунт найден, в скольких не найден и по скольким определить не удалось (защита сайта, лимиты, сеть). Находки по умолчанию перепроверяются случайным несуществующим ником, чтобы отсечь сайты, которые отвечают «найден» на любой ник (`--no-verify` отключает).

## Что в каталог не входит

Сервисы, которые по номеру, имени или нику выдают личность владельца, адрес, дату рождения или данные из утечек (пробивные сервисы, боты, People-Search). Номера анализируются только технически (формат, оператор, регион, спам-репутация), адреса — только как гео-данные.

## Ограничения

- Мини-поиск проверяет только открытые страницы профилей, не обходит авторизацию, CAPTCHA и лимиты. Результаты предварительные: возможны ложные срабатывания и пропуски.
- Сайты меняются: запускайте `osintcatalog check-links`, часть ссылок со временем устаревает. Статус «ЗАЩИТА» означает, что сайт не пускает автоматические запросы, а не что ссылка мертва.
- Используйте инструменты только для своих данных, разрешённых проверок и законных целей.

Данные: `osinttoolscatalog/data/catalog.json` (каталог), `osinttoolscatalog/data/sources.json` (сайты для поиска по нику).

Лицензия: MIT.
