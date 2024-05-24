import telebot

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import BOT_TOKEN, LINK_TO_BOT, SHORT_RULES, FULL_RULES, COMMANDS, MIN_PLAYERS, ROLES, CONTENT_TYPES

from database import (add_user, add_group, is_group_playing, add_user_to_games, is_user_playing,
                      change_group_state, check_user_exists, increase_session, get_players_list,
                      get_user_current_group_chat_id, update_user_data, get_user_data, get_alive_users,
                      get_users_with_role)

import random
import threading
from telebot.storage import StateMemoryStorage
from telebot import custom_filters
from telebot.handler_backends import StatesGroup, State


class MyStates(StatesGroup):
    message_to_delete = "message to delete"
    mafia_chat = 'chat for mafia'
    msg_with_buttons = State()


storage = StateMemoryStorage()

bot = telebot.TeleBot(token=BOT_TOKEN, state_storage=storage)
bot.add_custom_filter(custom_filters.StateFilter(bot))


@bot.message_handler(commands=["start"], chat_types=["supergroup"])
def handle_group_start(message):
    add_group(message.chat.id)

    if is_group_playing(message.chat.id):
        bot.delete_message(message.chat.id, message.message_id)
        return

    # создаем кнопку для перехода в чат с ботом
    return_to_private_btn = InlineKeyboardButton(text="Чат с ботом", url=LINK_TO_BOT)
    keyboard = InlineKeyboardMarkup().add(return_to_private_btn)

    text = ("Привет! Я бот, позволяющий играть в мафию. Если хотите начать игру, "
            "то используйте команду /start_game.\n\n"
            "Перед началом игры прошу вас убедиться, что все игроки написали мне /start в личные сообщения.\n\n")

    full_text = text + "<b>Правила:</b>\n" + SHORT_RULES  # добавляем краткие правила к приветственному сообщению

    bot.send_message(message.chat.id, full_text, reply_markup=keyboard, parse_mode="html")


@bot.message_handler(commands=["start"], chat_types=["private"])
def handle_private_start(message):
    add_user(message.chat.id)

    user_id = message.from_user.id
    link_to_group = get_group_link(user_id)

    text = ("Привет! Я бот, позволяющий играть в мафию. Здесь ты можешь ознакомиться с правилами игры "
            "по команде /rules или можешь вернуться в группу.")

    if link_to_group:
        # создаем кнопку для перехода в группу
        return_to_group_btn = InlineKeyboardButton(text="Вернуться в группу", url=link_to_group)
        keyboard = InlineKeyboardMarkup().add(return_to_group_btn)

        bot.send_message(message.chat.id, text, reply_markup=keyboard)

    else:
        bot.send_message(message.chat.id, text)


def get_group_link(user_id):
    group_id = get_user_current_group_chat_id(user_id)

    if group_id:
        link_to_group = bot.export_chat_invite_link(chat_id=group_id)  # Создаем ссылку для группы

        return link_to_group


@bot.message_handler(commands=["rules"])
def send_rules(message):
    if message.chat.type == "private":
        bot.send_message(message.chat.id, FULL_RULES, parse_mode="html")

    else:
        return_to_private_btn = InlineKeyboardButton(text="Чат с ботом", url=LINK_TO_BOT)
        keyboard = InlineKeyboardMarkup().add(return_to_private_btn)
        bot.send_message(message.chat.id, "Для того, чтобы узнать полные правила "
                                          "используйте команду /rules в чате со мной.", reply_markup=keyboard)


# обработка нажатия на кнопку "Готов!"
@bot.callback_query_handler(func=lambda call: call.data == "ready")
def ready_handler(call):
    user_id = call.from_user.id
    c_id = call.message.chat.id
    m_id = call.message.message_id

    if not check_user_exists(user_id):
        return_to_private_btn = InlineKeyboardButton(text="Чат с ботом", url=LINK_TO_BOT)
        keyboard = InlineKeyboardMarkup().add(return_to_private_btn)

        bot.send_message(call.message.chat.id, f"{call.from_user.username}, "
                                               f"пожалуйста, напишите /start в чате со мной.",
                         reply_markup=keyboard)

    elif is_user_playing(user_id):
        bot.answer_callback_query(call.id, "Вы уже присоединились к игре")

    else:
        add_user_to_games(call.message.chat.id, user_id)

        ready_user_ids = get_players_list(c_id)
        ready_user_names = []

        for user_id in ready_user_ids:
            user_name = bot.get_chat_member(c_id, user_id).user.username
            ready_user_names.append(user_name)

        markup = InlineKeyboardMarkup()
        play_button = InlineKeyboardButton("Готов!", callback_data="ready")
        markup.add(play_button)

        text = ("Нажмите на кнопку, когда будете готовы!\n\n"
                "Присоединившиеся игроки:\n")

        for i, user_name in enumerate(ready_user_names):
            text += f"{i + 1}. {user_name}\n"

        bot.edit_message_text(text=text, chat_id=c_id, message_id=m_id, reply_markup=markup)


# функция для проверки комиссара
def check_commissar(message):
    user_chat_id = message.from_user.id
    group_chat_id = get_user_current_group_chat_id(user_chat_id)

    chosen_player_id = get_user_data(user_chat_id, group_chat_id, "choice")
    chosen_player_role = get_user_data(chosen_player_id, group_chat_id, "role")

    if chosen_player_role == "Мафия":
        bot.send_message(user_chat_id,
                         f"Игрок {bot.get_chat_member(group_chat_id, chosen_player_id).user.username} - мафия!")
    else:
        bot.send_message(user_chat_id,
                         f"Игрок {bot.get_chat_member(group_chat_id, chosen_player_id).user.username} - мирный житель!")


# функция чата мафии
@bot.message_handler(state=MyStates.message_to_delete)
def delete_forbidden_messages(message):
    user_chat_id = message.from_user.id
    group_chat_id = get_user_current_group_chat_id(user_chat_id)

    if message.chat.type == 'supergroup':
        bot.delete_message(group_chat_id, message.message_id)


@bot.message_handler(state=MyStates.mafia_chat)
def mafia_chat(message):
    user_chat_id = message.from_user.id
    group_chat_id = get_user_current_group_chat_id(user_chat_id)

    mafia_chat_ids = get_users_with_role(group_chat_id, 'Мафия')
    for mafia_chat_id in mafia_chat_ids:
        if mafia_chat_id != user_chat_id:
            bot.send_message(mafia_chat_id, f"{message.from_user.username}: {message.text}")


# таймер для комиссара
def start_commissar_timer(message, delay=30):
    def end_commissar_stage():
        check_commissar(message)
        make_day_stage(message)

        link_to_group = get_group_link(commissar_chat_id)

        # создаем кнопку для перехода в группу
        return_to_group_btn = InlineKeyboardButton(text="Вернуться в группу", url=link_to_group)
        return_to_group_keyboard = InlineKeyboardMarkup().add(return_to_group_btn)

        # with bot.retrieve_data(mafia_chat_id, mafia_chat_id) as data:
        #     msg_with_button_id = data["msg_with_button_id"]
        #
        #     bot.edit_message_text(chat_id=commissar_chat_id, message_id=msg_with_button_id,
        #                           text="Возвращайтесь в группу",
        #                           reply_markup=return_to_group_keyboard)

        make_day_stage(message)

    group_chat_id = message.chat.id

    alive_players = get_alive_users(group_chat_id)
    for chat_id in alive_players:
        bot.set_state(chat_id, MyStates.message_to_delete, group_chat_id)

    commissar_chat_id = get_users_with_role(group_chat_id, 'Комиссар')

    threading.Timer(delay, end_commissar_stage).start()


# функция ночного таймера
def start_night_timer(message, delay=60):
    def end_night_stage():

        for mafia_chat_id in mafia_chat_ids:
            if mafia_chat_id in alive_players:
                choice = get_user_data(mafia_chat_id, group_chat_id, "choice")

                if choice is None:
                    link_to_group = get_group_link(mafia_chat_id)

                    # создаем кнопку для перехода в группу
                    return_to_group_btn = InlineKeyboardButton(text="Вернуться в группу", url=link_to_group)
                    return_to_group_keyboard = InlineKeyboardMarkup().add(return_to_group_btn)

                    with bot.retrieve_data(mafia_chat_id, mafia_chat_id) as data:
                        msg_with_button_id = data["msg_with_button_id"]

                        bot.edit_message_text(chat_id=mafia_chat_id, message_id=msg_with_button_id,
                                              text="Этой ночью вы никого не выбрали!",
                                              reply_markup=return_to_group_keyboard)

        for alive_chat_id in alive_players:
            # bot.send_message(group_chat_id, "Мафия закончила обсуждение.")
            bot.delete_state(alive_chat_id, alive_chat_id)
            bot.delete_state(alive_chat_id, group_chat_id)

        killed_player = count_votes(group_chat_id, mafia_chat_ids)

        if killed_player is not None:
            update_user_data(killed_player, group_chat_id, "killed", 1)
            bot.send_message(group_chat_id,
                             f"Мафия убила игрока {bot.get_chat_member(group_chat_id, killed_player).user.username}")
        else:
            bot.send_message(group_chat_id, "Мафия не смогла договориться и никого не убила")

        start_commissar_timer(message)

    group_chat_id = message.chat.id

    alive_players = get_alive_users(group_chat_id)
    for chat_id in alive_players:
        bot.set_state(chat_id, MyStates.message_to_delete, group_chat_id)

    mafia_chat_ids = get_users_with_role(group_chat_id, 'Мафия')
    for mafia_chat_id in mafia_chat_ids:

        if len(mafia_chat_ids) > 1:
            bot.send_message(mafia_chat_id, "Даю вам минуту на то, чтобы обсудить свой выбор!")
            bot.set_state(mafia_chat_id, MyStates.mafia_chat, mafia_chat_id)

    threading.Timer(delay, end_night_stage).start()


# функция ночной фазы
def make_night_stage(message):
    group_chat_id = message.chat.id
    user_chat_ids = get_alive_users(group_chat_id)
    mafia_chat_ids = get_users_with_role(group_chat_id, 'Мафия')

    for user_id in user_chat_ids:
        update_user_data(user_id, group_chat_id, param="choice", data=None)

    return_to_private_btn = InlineKeyboardButton(text="Чат с ботом", url=LINK_TO_BOT)
    return_to_private_keyboard = InlineKeyboardMarkup().add(return_to_private_btn)

    bot.send_message(group_chat_id, "Наступила ночь! Мафия, просыпайтесь и выберите жертву!",
                     reply_markup=return_to_private_keyboard)

    for mafia_chat_id in mafia_chat_ids:
        markup = InlineKeyboardMarkup()
        for user_chat_id in user_chat_ids:
            if user_chat_id != mafia_chat_id and user_chat_id not in mafia_chat_ids:
                btn = InlineKeyboardButton(text=bot.get_chat_member(group_chat_id, user_chat_id).user.username,
                                           callback_data=user_chat_id)
                markup.add(btn)
        if mafia_chat_id in user_chat_ids:
            msg_with_button = bot.send_message(mafia_chat_id, "Выберите жертву!", reply_markup=markup)

            bot.set_state(mafia_chat_id, MyStates.msg_with_buttons, mafia_chat_id)

            with bot.retrieve_data(mafia_chat_id, mafia_chat_id) as data:
                data['msg_with_button_id'] = msg_with_button.message_id

    commissar_chat_id = get_users_with_role(group_chat_id, 'Комиссар')[0]
    markup = InlineKeyboardMarkup()
    for user_chat_id in user_chat_ids:
        if user_chat_id != commissar_chat_id:
            btn = InlineKeyboardButton(text=bot.get_chat_member(group_chat_id, user_chat_id).user.username,
                                       callback_data=user_chat_id)
            markup.add(btn)
    if commissar_chat_id in user_chat_ids:
        msg_with_button = bot.send_message(commissar_chat_id, "Проверьте роль игрока!", reply_markup=markup)

        bot.set_state(commissar_chat_id, MyStates.msg_with_buttons, commissar_chat_id)

        with bot.retrieve_data(commissar_chat_id, commissar_chat_id) as data:
            data['msg_with_button_id'] = msg_with_button.message_id

    start_night_timer(message)


# функция назначения ролей для игры
def assign_roles(group_chat_id):
    user_chat_ids = get_players_list(group_chat_id)
    num_players = len(user_chat_ids)
    num_mafia = num_players // 3
    num_citizens = num_players - num_mafia - 1

    roles = []
    for role in ROLES:
        if role == "Мафия":
            for i in range(num_mafia):
                roles.append(role)
        elif role == "Комиссар":
            roles.append(role)
        else:
            for i in range(num_citizens):
                roles.append(role)

    random.shuffle(roles)

    for chat_id, role in zip(user_chat_ids, roles):
        update_user_data(chat_id, group_chat_id, "role", role)
        bot.send_message(chat_id, f"Ваша роль - {role}")


# функция таймера для начала игры
def start_game_timer(message, sent_message, delay=30):
    def timer_func():
        joined_players = len(get_players_list(message.chat.id))

        if joined_players < MIN_PLAYERS:
            bot.send_message(message.chat.id, "Недостаточно игроков для начала игры! Начните набор заново!")

            change_group_state(message.chat.id, 0)

        else:
            assign_roles(message.chat.id)
            make_night_stage(message)

        bot.delete_message(message.chat.id, sent_message.message_id)

    threading.Timer(delay, timer_func).start()


# функция начала игры
@bot.message_handler(commands=["start_game"], chat_types=["supergroup"])
def start_game_handler(message):
    c_id = message.chat.id

    add_group(c_id)

    if is_group_playing(c_id):
        bot.send_message(c_id, "Игра уже начата!")

    else:
        change_group_state(c_id, 1)

        increase_session(c_id)

        bot.send_message(c_id, "Началась подготовка к игре!")

        markup = InlineKeyboardMarkup()
        play_button = InlineKeyboardButton("Готов!", callback_data="ready")
        markup.add(play_button)

        sent_message = bot.send_message(c_id, "Нажмите на кнопку, когда будете готовы!", reply_markup=markup)
        start_game_timer(message, sent_message)


@bot.callback_query_handler(func=lambda call: call.data.isdigit())
def process_user_votes(call):
    c_id = call.message.chat.id
    m_id = call.message.message_id

    try:

        voted_user_id = call.from_user.id
        chosen_user_id = int(call.data)

        group_chat_id = get_user_current_group_chat_id(voted_user_id)

        update_user_data(voted_user_id, group_chat_id, "choice", chosen_user_id)

        link_to_group = get_group_link(voted_user_id)

        # создаем кнопку для перехода в группу
        return_to_group_btn = InlineKeyboardButton(text="Вернуться в группу", url=link_to_group)
        return_to_group_keyboard = InlineKeyboardMarkup().add(return_to_group_btn)

        chosen_user_name = bot.get_chat_member(group_chat_id, chosen_user_id).user.username

        bot.edit_message_text(chat_id=c_id, message_id=m_id, text=f"Ваш выбор: {chosen_user_name}",
                              reply_markup=return_to_group_keyboard)

    except IndexError:
        bot.edit_message_text(chat_id=c_id, message_id=m_id, text=f"Кажется, кнопка устарела", reply_markup=None)


def count_votes(group_chat_id, voted_users):
    votes = {}

    for chat_id in voted_users:
        choice = get_user_data(chat_id, group_chat_id, "choice")
        if choice is not None:
            if choice in votes:
                votes[choice] += 1
            else:
                votes[choice] = 1
    if votes.values():
        max_votes = max(votes.values())
    else:
        max_votes = 0

    killed_player = [player for player, votes in votes.items() if votes == max_votes]

    if len(killed_player) != 1:
        killed_player = None
    else:
        killed_player = killed_player[0]

    return killed_player


def start_voting_timer(message, delay=30):
    def timer_func():
        c_id = message.chat.id

        bot.send_message(c_id, "Голосование завершено!")

        # получаем статус и user_id
        alive_user_ids = get_alive_users(c_id)
        voting_result = count_votes(c_id, alive_user_ids)

        for alive_user_chat_id in alive_user_ids:
            choice = get_user_data(alive_user_chat_id, c_id, "choice")

            if choice is None:
                link_to_group = get_group_link(alive_user_chat_id)

                # создаем кнопку для перехода в группу
                return_to_group_btn = InlineKeyboardButton(text="Вернуться в группу", url=link_to_group)
                return_to_group_keyboard = InlineKeyboardMarkup().add(return_to_group_btn)

                with bot.retrieve_data(alive_user_chat_id, alive_user_chat_id) as data:
                    msg_with_button_id = data["msg_with_button_id"]

                    bot.edit_message_text(chat_id=alive_user_chat_id, message_id=msg_with_button_id,
                                          text="Сегодня вы решили никого не выгонять.",
                                          reply_markup=return_to_group_keyboard)

        if not voting_result:
            bot.send_message(c_id, "Жители решили никого не убивать сегодня.")

        else:
            killed_user_id = voting_result

            killed_user_name = bot.get_chat_member(c_id, killed_user_id).user.username

            killed_user_role = get_user_data(killed_user_id, c_id, 'role')

            if killed_user_role.lower() == "мафия":
                text = "Он был мафией."

            else:
                text = "Он не был мафией."

            bot.send_message(c_id, f"Сегодня был изгнан игрок {killed_user_name}.\n\n" + text)

            update_user_data(voting_result, message.chat.id, "killed", 1)

        mafia_chat_ids = get_users_with_role(c_id, 'Мафия')

        pieceful_player_ids = sorted(list(set(alive_user_ids) - set(mafia_chat_ids)))

        if len(pieceful_player_ids) <= len(mafia_chat_ids):
            make_results(c_id, "mafia", mafia_chat_ids)

            return

        elif len(mafia_chat_ids) == 0:
            make_results(c_id, "pieceful_players", pieceful_player_ids)

            return

        make_night_stage(message)

    threading.Timer(delay, timer_func).start()


def make_voting(message, alive_users):
    alive_players_keyboard = InlineKeyboardMarkup()

    for user_info in alive_users:  # создаем клавиатуру, где у каждой кнопки text - имя юзера, data - его тг айди
        btn = InlineKeyboardButton(text=user_info[1], callback_data=user_info[0])
        alive_players_keyboard.add(btn)

    return_to_private_btn = InlineKeyboardButton(text="Чат с ботом", url=LINK_TO_BOT)
    return_to_private_keyboard = InlineKeyboardMarkup().add(return_to_private_btn)

    bot.send_message(message.chat.id, "Настало время голосования! Всех живых игроков прошу перейти в чат со мной.",
                     reply_markup=return_to_private_keyboard)

    for user_info in alive_users:
        user_id = user_info[0]
        msg_with_button = bot.send_message(user_id, "Пришло время кого-нибудь изгнать! "
                                                    "У вас есть 30 секунд на то, чтобы сделать выбор",
                                           reply_markup=alive_players_keyboard)

        bot.set_state(user_id, MyStates.msg_with_buttons, user_id)

        with bot.retrieve_data(user_id, user_id) as data:
            data['msg_with_button_id'] = msg_with_button.message_id

    start_voting_timer(message)


def start_discussion_timer(message, alive_users, delay=180):
    def timer_func():
        make_voting(message, alive_users)

    threading.Timer(delay, timer_func).start()


def make_day_stage(message):
    c_id = message.chat.id

    alive_user_ids = get_alive_users(c_id)
    alive_user_names = []

    for user_id in alive_user_ids:
        update_user_data(user_id, c_id, "choice", None)

        user_name = bot.get_chat_member(c_id, user_id).user.username
        alive_user_names.append(user_name)  # добавляем имена пользователей в список

    mafia_chat_ids = get_users_with_role(c_id, 'Мафия')

    pieceful_player_ids = sorted(list(set(alive_user_ids) - set(mafia_chat_ids)))

    if len(pieceful_player_ids) <= len(mafia_chat_ids):
        make_results(c_id, "mafia", mafia_chat_ids)

        return

    elif len(mafia_chat_ids) == 0:
        make_results(c_id, "pieceful_players", pieceful_player_ids)

        return

    text = "Этой ночью остались в живых:\n\n"

    for i, user_name in enumerate(alive_user_names):  # выводим список пользователей с нумерацией
        text += f"{i + 1}. {user_name}\n"

    bot.send_message(c_id, text)

    bot.send_message(c_id, "Настало время для обсуждения! Даю вам 3 минуты!")

    alive_users = []

    for i in range(len(alive_user_ids)):
        alive_users.append([alive_user_ids[i], alive_user_names[i]])  # Нужно для кнопок в голосовании

    start_discussion_timer(message, alive_users)


def make_results(chat_id, winners_team, winners_list):
    winners_names = []

    if winners_team == "mafia":
        text = "Мафия выиграла!\n\n"

    else:
        text = "Мирные жители смогли побороть мафию!\n\n"

    text += "Победившие игроки:\n"

    for user_id in winners_list:
        user_name = bot.get_chat_member(chat_id, user_id).user.username
        winners_names.append(user_name)  # добавляем имена пользователей в список

    for i, user_name in enumerate(winners_names):
        text += f"{i + 1}. {user_name}\n"

    bot.send_message(chat_id, text)

    change_group_state(chat_id, 0)


@bot.message_handler(commands=['delete'], chat_types=['supergroup'])
def deleting_state(message):
    change_group_state(message.chat.id, 0)


@bot.message_handler(content_types=CONTENT_TYPES, chat_types=['supergroup'])
def deleting_messages(message):
    user_id = message.from_user.id
    group_chat_id = get_user_current_group_chat_id(user_id)
    is_group_in_game = is_group_playing(group_chat_id)

    if is_group_in_game:
        alive_players = get_alive_users(message.chat.id)
        user_id = message.from_user.id

        if user_id not in alive_players:
            bot.delete_message(message.chat.id, message.message_id)


if __name__ == "__main__":
    bot.set_my_commands(COMMANDS)  # Добавляем команды в меню

    bot.infinity_polling()
