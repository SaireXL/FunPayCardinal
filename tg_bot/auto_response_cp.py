"""
В данном модуле описаны функции для ПУ конфига авто-ответчика.
Модуль реализован в виде плагина.
"""

from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from cardinal import Cardinal

from tg_bot import utils, keyboards, CBT

from telebot.types import InlineKeyboardButton as Button
from telebot import types
import datetime
import logging


logger = logging.getLogger("TGBot")


def init_auto_response_cp(cardinal: Cardinal, *args):
    tg = cardinal.telegram
    bot = tg.bot

    def check_command_exists(command_index: int, message_obj: types.Message, reply_mode: bool = True) -> bool:
        """
        Проверяет, существует ли команда с переданным индексом.
        Если команда не существует - отправляет сообщение с кнопкой обновления списка команд.

        :param command_index: индекс команды.

        :param message_obj: экземпляр Telegram-сообщения.

        :param reply_mode: режим ответа на переданное сообщение.
        Если True - отвечает на переданное сообщение,
        если False - редактирует переданное сообщение.

        :return: True, если команда существует, False, если нет.
        """
        if command_index > len(cardinal.RAW_AR_CFG.sections()) - 1:
            update_button = types.InlineKeyboardMarkup().add(Button("🔄 Обновить",
                                                                    callback_data=f"{CBT.CMD_LIST}:0"))
            if reply_mode:
                bot.reply_to(message_obj, f"❌ Не удалось обнаружить команду с индексом <code>{command_index}</code>.",
                             allow_sending_without_reply=True, parse_mode="HTML", reply_markup=update_button)
            else:
                bot.edit_message_text(f"❌ Не удалось обнаружить команду с индексом <code>{command_index}</code>.",
                                      message_obj.chat.id, message_obj.id,
                                      parse_mode="HTML", reply_markup=update_button)
            return False
        return True

    def open_commands_list(c: types.CallbackQuery):
        """
        Открывает список существующих команд.
        """
        offset = int(c.data.split(":")[1])
        bot.edit_message_text(f"Выберите интересующую вас команду.", c.message.chat.id, c.message.id,
                              reply_markup=keyboards.commands_list(cardinal, offset))
        bot.answer_callback_query(c.id)

    def act_add_command(c: types.CallbackQuery):
        """
        Активирует режим добавления новой команды.
        """
        result = bot.send_message(c.message.chat.id,
                                  "Введите новую команду (или несколько команд через знак <code>|</code>).",
                                  parse_mode="HTML", reply_markup=keyboards.CLEAR_STATE_BTN)
        tg.set_user_state(c.message.chat.id, result.id, c.from_user.id, CBT.ADD_CMD)
        bot.answer_callback_query(c.id)

    def add_command(m: types.Message):
        """
        Добавляет новую команду в конфиг.
        """
        tg.clear_user_state(m.chat.id, m.from_user.id, True)
        raw_command = m.text.strip()
        commands = [i.strip() for i in raw_command.split("|") if i.strip()]
        applied_commands = []
        error_keyboard = types.InlineKeyboardMarkup()\
            .row(Button("◀️ Назад", callback_data=f"{CBT.CATEGORY}:autoResponse"),
                 Button("➕ Добавить другую", callback_data=CBT.ADD_CMD))

        for cmd in commands:
            if cmd in applied_commands:

                bot.reply_to(m, f"❌ В сете команд дублируется команда <code>{utils.escape(cmd)}</code>.",
                             allow_sending_without_reply=True, parse_mode="HTML", reply_markup=error_keyboard)
                return
            if cmd in cardinal.AR_CFG.sections():
                bot.reply_to(m, f"❌ Команда <code>{utils.escape(cmd)}</code> уже существует.",
                             allow_sending_without_reply=True, parse_mode="HTML", reply_markup=error_keyboard)
                return
            applied_commands.append(cmd)

        cardinal.RAW_AR_CFG.add_section(raw_command)
        cardinal.RAW_AR_CFG.set(raw_command, "response", "Данной команде необходимо настроить текст ответа :(")
        cardinal.RAW_AR_CFG.set(raw_command, "telegramNotification", "0")

        for cmd in applied_commands:
            cardinal.AR_CFG.add_section(cmd)
            cardinal.AR_CFG.set(cmd, "response", "Данной команде необходимо настроить текст ответа :(")
            cardinal.AR_CFG.set(cmd, "telegramNotification", "0")

        cardinal.save_config(cardinal.RAW_AR_CFG, "configs/auto_response.cfg")

        command_index = len(cardinal.RAW_AR_CFG.sections())-1
        offset = command_index - 4 if command_index - 4 > 0 else 0

        keyboard = types.InlineKeyboardMarkup()\
            .row(Button("◀️ Назад", callback_data=f"{CBT.CATEGORY}:autoResponse"),
                 Button("➕ Добавить еще", callback_data=CBT.ADD_CMD),
                 Button("⚙️ Настроить", callback_data=f"{CBT.EDIT_CMD}:{command_index}:{offset}"))
        logger.info(f"Пользователь $MAGENTA{m.from_user.username} (id: {m.from_user.id})$RESET добавил секцию "
                    f"$YELLOW[{raw_command}]$RESET в конфиг авто-ответчика.")
        bot.reply_to(m, f"✅ Добавлена новая секция "
                        f"<code>[{utils.escape(raw_command)}]</code> в конфиг авто-ответчика.",
                     allow_sending_without_reply=True, parse_mode="HTML", reply_markup=keyboard)

    def open_edit_command_cp(c: types.CallbackQuery):
        """
        Открывает панель редактирования команды.
        """
        split = c.data.split(":")
        command_index, offset = int(split[1]), int(split[2])
        if not check_command_exists(command_index, c.message, reply_mode=False):
            bot.answer_callback_query(c.id)
            return

        keyboard = keyboards.edit_command(cardinal, command_index, offset)

        command = cardinal.RAW_AR_CFG.sections()[command_index]
        command_obj = cardinal.RAW_AR_CFG[command]
        if command_obj.get("telegramNotification") == "1":
            telegram_notification_text = "Да."
        else:
            telegram_notification_text = "Нет."
        notification_text = command_obj.get("notificationText")
        notification_text = notification_text if notification_text else "Пользователь $username ввел команду $message_text."

        message = f"""<b>[{utils.escape(command)}]</b>

<b><i>Ответ:</i></b> <code>{utils.escape(command_obj["response"])}</code>

<b><i>Отправлять уведомления в Telegram:</i></b> <b><u>{telegram_notification_text}</u></b>

<b><i>Текст уведомления:</i></b> <code>{utils.escape(notification_text)}</code>

<i>Обновлено:</i>  <code>{datetime.datetime.now().strftime('%H:%M:%S')}</code>"""
        bot.edit_message_text(message, c.message.chat.id, c.message.id, reply_markup=keyboard, parse_mode="HTML")
        bot.answer_callback_query(c.id)

    def act_edit_command_response(c: types.CallbackQuery):
        """
        Активирует режим изменения текста ответа на команду.
        """
        split = c.data.split(":")
        command_index, offset = int(split[1]), int(split[2])

        result = bot.send_message(c.message.chat.id, "Введите новый текст ответа.",
                                  parse_mode="HTML", reply_markup=keyboards.CLEAR_STATE_BTN)

        tg.set_user_state(c.message.chat.id, result.id, c.from_user.id, CBT.EDIT_CMD_RESPONSE_TEXT,
                          {"command_index": command_index,
                           "offset": offset})

        bot.answer_callback_query(c.id)

    def edit_command_response(m: types.Message):
        """
        Изменяет текст ответа команды.
        """
        command_index = tg.get_user_state(m.chat.id, m.from_user.id)["data"]["command_index"]
        offset = tg.get_user_state(m.chat.id, m.from_user.id)["data"]["offset"]
        tg.clear_user_state(m.chat.id, m.from_user.id, True)
        if not check_command_exists(command_index, m):
            return

        response_text = m.text.strip()
        command = cardinal.RAW_AR_CFG.sections()[command_index]
        commands = [i.strip() for i in command.split("|") if i.strip()]
        cardinal.RAW_AR_CFG.set(command, "response", response_text)
        for cmd in commands:
            cardinal.AR_CFG.set(cmd, "response", response_text)
        cardinal.save_config(cardinal.RAW_AR_CFG, "configs/auto_response.cfg")

        logger.info(f"Пользователь $MAGENTA{m.from_user.username} (id: {m.from_user.id})$RESET изменил текст ответа "
                    f"команды / сета команд $YELLOW[{command}]$RESET на $YELLOW\"{response_text}\"$RESET.")

        keyboard = types.InlineKeyboardMarkup() \
            .row(Button("◀️ Назад", callback_data=f"{CBT.EDIT_CMD}:{command_index}:{offset}"),
                 Button("✏️ Изменить", callback_data=f"{CBT.EDIT_CMD_RESPONSE_TEXT}:{command_index}:{offset}"))

        bot.reply_to(m, f"✅ Текст ответа команды / сета команд <code>[{utils.escape(command)}]</code> "
                        f"изменен на <code>{utils.escape(response_text)}</code>",
                     allow_sending_without_reply=True,
                     parse_mode="HTML", reply_markup=keyboard)

    def act_edit_command_notification(c: types.CallbackQuery):
        """
        Активирует режим изменения текста уведомления об использовании команды.
        """
        split = c.data.split(":")
        command_index, offset = int(split[1]), int(split[2])
        result = bot.send_message(c.message.chat.id, "Введите новый текст уведомления.",
                                  parse_mode="HTML", reply_markup=keyboards.CLEAR_STATE_BTN)
        tg.set_user_state(c.message.chat.id, result.id, c.from_user.id, CBT.EDIT_CMD_NOTIFICATION_TEXT,
                          {"command_index": command_index,
                           "offset": offset})
        bot.answer_callback_query(c.id)

    def edit_command_notification(m: types.Message):
        """
        Изменяет текст уведомления об использовании команды.
        """
        command_index = tg.get_user_state(m.chat.id, m.from_user.id)["data"]["command_index"]
        offset = tg.get_user_state(m.chat.id, m.from_user.id)["data"]["offset"]
        tg.clear_user_state(m.chat.id, m.from_user.id, True)

        if not check_command_exists(command_index, m):
            return

        notification_text = m.text.strip()
        command = cardinal.RAW_AR_CFG.sections()[command_index]
        commands = [i.strip() for i in command.split("|") if i.strip()]
        cardinal.RAW_AR_CFG.set(command, "notificationText", notification_text)

        for cmd in commands:
            cardinal.AR_CFG.set(cmd, "notificationText", notification_text)
        cardinal.save_config(cardinal.RAW_AR_CFG, "configs/auto_response.cfg")

        logger.info(f"Пользователь $MAGENTA{m.from_user.username} (id: {m.from_user.id})$RESET изменил текст "
                    f"уведомления команды $YELLOW[{command}]$RESET на $YELLOW\"{notification_text}\"$RESET.")

        keyboard = types.InlineKeyboardMarkup() \
            .row(Button("◀️ Назад", callback_data=f"{CBT.EDIT_CMD}:{command_index}:{offset}"),
                 Button("✏️ Изменить", callback_data=f"{CBT.EDIT_CMD_NOTIFICATION_TEXT}:{command_index}:{offset}"))

        bot.reply_to(m, f"✅ Текст уведомления команды / сета команд <code>[{utils.escape(command)}]</code> "
                        f"изменен на <code>{utils.escape(notification_text)}</code>",
                     allow_sending_without_reply=True,
                     parse_mode="HTML", reply_markup=keyboard)

    def switch_notification(c: types.CallbackQuery):
        """
        Вкл / Выкл уведомление об использовании команды.
        """
        split = c.data.split(":")
        command_index, offset = int(split[1]), int(split[2])
        bot.answer_callback_query(c.id)
        if not check_command_exists(command_index, c.message, reply_mode=False):
            bot.answer_callback_query(c.id)
            return

        command = cardinal.RAW_AR_CFG.sections()[command_index]
        commands = [i.strip() for i in command.split("|") if i.strip()]
        command_obj = cardinal.RAW_AR_CFG[command]
        if command_obj.get("telegramNotification") in [None, "0"]:
            value = "1"
        else:
            value = "0"
        cardinal.RAW_AR_CFG.set(command, "telegramNotification", value)
        for cmd in commands:
            cardinal.AR_CFG.set(cmd, "telegramNotification", value)
        cardinal.save_config(cardinal.RAW_AR_CFG, "configs/auto_response.cfg")
        logger.info(f"Пользователь $MAGENTA{c.from_user.username} (id: {c.from_user.id})$RESET изменил значение "
                    f"параметра $CYANtelegramNotification$RESET команды / сета команд $YELLOW[{command}]$RESET "
                    f"на $YELLOW{value}$RESET.")
        open_edit_command_cp(c)

    def del_command(c: types.CallbackQuery):
        """
        Удаляет команду из конфига авто-ответчика.
        """
        split = c.data.split(":")
        command_index, offset = int(split[1]), int(split[2])
        if not check_command_exists(command_index, c.message, reply_mode=False):
            bot.answer_callback_query(c.id)
            return

        command = cardinal.RAW_AR_CFG.sections()[command_index]
        commands = [i.strip() for i in command.split("|") if i.strip()]
        cardinal.RAW_AR_CFG.remove_section(command)
        for cmd in commands:
            cardinal.AR_CFG.remove_section(cmd)
        cardinal.save_config(cardinal.RAW_AR_CFG, "configs/auto_response.cfg")
        logger.info(f"Пользователь $MAGENTA{c.from_user.username} (id: {c.from_user.id})$RESET удалил "
                    f"команду / сет команд $YELLOW[{command}]$RESET.")
        bot.edit_message_text(f"Выберите интересующую вас команду.", c.message.chat.id, c.message.id,
                              reply_markup=keyboards.commands_list(cardinal, offset))
        bot.answer_callback_query(c.id)

    # Регистрируем хэндлеры
    tg.cbq_handler(open_commands_list, lambda c: c.data.startswith(f"{CBT.CMD_LIST}:"))

    tg.cbq_handler(act_add_command, lambda c: c.data == CBT.ADD_CMD)
    tg.msg_handler(add_command, func=lambda m: tg.check_state(m.chat.id, m.from_user.id, CBT.ADD_CMD))

    tg.cbq_handler(open_edit_command_cp, lambda c: c.data.startswith(f"{CBT.EDIT_CMD}:"))

    tg.cbq_handler(act_edit_command_response, lambda c: c.data.startswith(f"{CBT.EDIT_CMD_RESPONSE_TEXT}:"))
    tg.msg_handler(edit_command_response,
                   func=lambda m: tg.check_state(m.chat.id, m.from_user.id, CBT.EDIT_CMD_RESPONSE_TEXT))

    tg.cbq_handler(act_edit_command_notification, lambda c: c.data.startswith(f"{CBT.EDIT_CMD_NOTIFICATION_TEXT}:"))
    tg.msg_handler(edit_command_notification,
                   func=lambda m: tg.check_state(m.chat.id, m.from_user.id, CBT.EDIT_CMD_NOTIFICATION_TEXT))

    tg.cbq_handler(switch_notification, lambda c: c.data.startswith(f"{CBT.SWITCH_CMD_NOTIFICATION}:"))
    tg.cbq_handler(del_command, lambda c: c.data.startswith(f"{CBT.DEL_CMD}:"))


BIND_TO_PRE_INIT = [init_auto_response_cp]
