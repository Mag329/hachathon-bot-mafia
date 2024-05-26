# hackathon_mafia_bot:

Бот, позволяющий пользователям добавить его в группу и играть в мафию (бот - ведущий).

# Основные команды бота:

- `/start`
- `/start_game`
- `/rules`

# Инструкция по использованию бота
- Перейдите в бота по [ссылке](https://t.me/hackathon_mafia_bot) и нажмите СТАРТ
- Добавьте бота в группу, в которой планируете играть и дайте ему права администратора
## Необходимые права:
- delete messages
- ban users
- invite users via link

# Далее
- Пользуйтесь командами из Меню
- Используйте команду `/start_game` для начала игры
- Ход игры подробно описан в файле [ТЗ](https://github.com/alinkalina/hachathon-bot-mafia/blob/main/ТЗ.md)

# Инструкция по запуску проекта самостоятельно 

- Клонируйте репозиторий
- Добавьте необходимые библиотеки Python, зависимости прописаны в файле requirements.txt
- Переименуйте файл example.env в .env и поместите в него переменные:
  - `BOT_TOKEN` - Ваш токен Телеграм бота
- Перейдите в файл config.py и вставьте ссылку на своего бота:
  - `LINK_TO_BOT` - переменная, в которую нужно вставить ссылку
- Запустите файл `bot.py`
