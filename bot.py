from flask import Flask, Request, jsonify
from datetime import datetime
from telebot import types
import logging.config
import telebot, sys
import os, re
import time

from keyboard import *
from actions import *
from configs import *
from text import *
from db import *

import actions

logging.config.fileConfig(log_ini_file, disable_existing_loggers=False)
logger = logging.getLogger(__name__)

server = Flask(__name__)			# инициализация Flask сервера
bot = telebot.TeleBot(bot_token)	# тож самое только с модулем для телеграмм бота

bot.remove_webhook()				# удаляем на всякий случай вебхук
logger.info("delete webhook")
time.sleep(2)
									# устанавливаем вебхук на наш ИП адрес с сертификатом
bot.set_webhook(url="https://{host}:{port}".format(host=bot_ip, port=bot_port), certificate=open(cert, 'r'), allowed_updates=["message", "callback_query"])
logger.info("set webhook %s" % bot_ip)

kbrs = {
	"eat":catalog_eat(),
	"dress":catalog_dress()
}

# собственно единственная функция сервера по сути
# в которую приходят все запросы от телеграмма
# нам нужно только распарсить запрос и обработать
# все запросы приходят через POST
@server.route("/", methods=['POST'])
def getMessage():
	r = request.get_json()										# запрос сразу пытаемся распарсить json
	logger.info(r)
	print(r)
	if r == None:
		return "ok", 200

	if "callback_query" in r.keys():							# если в запросе есть callback_query
		chat_id = r["callback_query"]["from"]["id"]				# то нужно вытащить chat_id
		data = r["callback_query"]["data"]						# тело сообщения
		message_id = r["callback_query"]["id"]					# на всякий случай ID сообщения
		username = '0'
		if "username" in r["callback_query"]["from"]:			# username пользователя
			username = r["callback_query"]["from"]["username"]

		if data == "back_to_main":
			bot.send_message(chat_id=chat_id, text=text_MAIN_MENU.format(username=username), parse_mode='HTML', reply_markup=main_keyboard())
			return "ok", 200
		if data == "back_to_catalog":
			bot.send_message(chat_id=chat_id, text=text_CATALOG.format(username=username), parse_mode='HTML', reply_markup=catalog())
			return "ok", 200
		if "catalog_" in data:
			add = data.split("_")
			item_tag = add[-1]
			img_shop = open("/root/src/python/shop_bot/images/{tag}.jpg".format(tag=item_tag), "rb")
			bot.send_photo(chat_id=chat_id, photo=img_shop, reply_markup=kbrs[item_tag])
			return "ok", 200
		if data == "go_to_cart":
			bot.send_message(chat_id=chat_id, text=user_cart(chat_id), parse_mode='HTML', reply_markup=cart())
			return "ok", 200

		if "get_" in data:
			# return "ok", 200
			add = data.split("_")
			item_tag = add[1]
			item_price = add[-1]
			img_shop = open("/root/src/python/shop_bot/images/{tag}.jpg".format(tag=item_tag), "rb")
			bot.send_photo(chat_id=chat_id, photo=img_shop, reply_markup=item_add(item_tag, item_price))
			return "ok", 200
		if "add_" in data:
			# return "ok", 200
			add = data.split("_")
			item_tag = add[1]
			item_price = add[-1]
			add_item = addItem(user=str(chat_id), item=item_tag, price=item_price)
			if add_item is False:
				bot.answer_callback_query(callback_query_id=message_id, text='Что то пошло не так, попробуйте попозже или обратитесь в службу поддержки')
				return "ok", 200
			bot.answer_callback_query(callback_query_id=message_id, text='Добавлено в корзину')
			return "ok", 200
		if "del_" in data:
			# return "ok", 200
			add = data.split("_")
			item_tag = add[1]
			item_price = add[-1]
			del_item = delItem(user=str(chat_id), item=item_tag, price=item_price)
			if del_item is False:
				bot.answer_callback_query(callback_query_id=message_id, text='Что то пошло не так, попробуйте попозже или обратитесь в службу поддержки')
				return "ok", 200
			bot.answer_callback_query(callback_query_id=message_id, text='Удалено из корзины')
			return "ok", 200

	if "message" in r.keys():
		chat_id = r["message"]["chat"]["id"]									# если в запросе на сервер прилетел Json с message
		username = 'shop user'
		if "first_name" in r["message"]["chat"]:								# так же достаем из запроса все нужные данные по пользователю
			first_name = replace_symbols(r["message"]["chat"]["first_name"])
		if "username" in r["message"]["chat"]:
			username = replace_symbols(r["message"]["chat"]["username"])
		if "last_name" in r["message"]["chat"]:
			last_name = replace_symbols(r["message"]["chat"]["last_name"])
		if "text" in r["message"]:
			text_mess = r["message"]["text"]
		else:
			bot.send_message(chat_id=chat_id, text="Какая то не понятная проблема", parse_mode='HTML', reply_markup=main_keyboard())
			return "ok", 200

		# если боту прилетел запрос /start 
		if text_mess == '/start':
			bot.send_message(chat_id=chat_id, text=text_START.format(username=username), parse_mode='HTML', reply_markup=main_keyboard())
			return "ok", 200

		if text_mess == '💰 Каталог':
			bot.send_message(chat_id=chat_id, text=text_CATALOG.format(username=username), parse_mode='HTML', reply_markup=catalog())
			return "ok", 200

		if text_mess == '🎓 Корзина':
			bot.send_message(chat_id=chat_id, text=user_cart(chat_id), parse_mode='HTML', reply_markup=cart())
			return "ok", 200

		if text_mess == '🤖 Контакты':
			bot.send_message(chat_id=chat_id, text=text_CONTACT, parse_mode='HTML', reply_markup=main_keyboard())
			return "ok", 200

	return "ok", 200

def user_cart(user):
	user_items = getItem(str(user))
	if user_items == False:
		text = "Ваша корзина пуста"
	else:
		text = "В Вашей корзине на данный момент:\n\n"
		text += "<b>Итоговая сумма: {price}</b>\n\n".format(price=user_items["all_price"])
		del user_items["all_price"]
		for item in user_items:
			text += "{item} {count}шт".format(item=item, count=user_items[item]["count"])
	return text

# убираем лишние символы из POST запроса к боту
def replace_symbols(text):
	update_text = re.sub(r'\W*', '', text)
	return update_text

if __name__ == "__main__":
	server.run(host=bot_ip, port=int(os.environ.get('PORT', bot_port)), ssl_context=(cert, cert_key))
