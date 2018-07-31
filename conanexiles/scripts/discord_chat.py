#!/usr/bin/python3
# -*- coding: utf-8 -*-

import discord
import asyncio
import sys
import random
import feedparser
import ssl
import re
import valve.rcon
import os
import time
import subprocess
import urllib.parse
import datetime

valve.rcon.RCONMessage.ENCODING = "utf-8"

token = os.getenv("CONANEXILES_Game_DiscordPlugin_Token")
channel_id = os.getenv("CONANEXILES_Game_DiscordPlugin_Channel")
address = ("localhost", int(os.getenv("CONANEXILES_Game_RconPlugin_RconPort",25575)))
password = os.getenv("CONANEXILES_Game_RconPlugin_RconPassword")

client = discord.Client()

feedparser.PREFERRED_XML_PARSERS.remove('drv_libxml2')
zh_pattern = re.compile(u'[\u4e00-\u9fa5]+')

def rcon_send_msg(msg):
	with valve.rcon.RCON(address, password) as rcon:
		cmd = u"server %s" % msg
		response = rcon.execute(cmd)
		print('To game: server %s' % msg)

async def read_game_chat():
	async def follow(thefile):
		thefile.seek(0,2)
		while True:
			line = thefile.readline()
			if not line:
				await asyncio.sleep(1)
				continue
			if "ChatWindow" in line:
				str = re.sub(r' said', '', re.sub(r'^.*Character ', '', line))
				yield str
			elif "Join request:" in line:
				pattern = re.compile(r"dw_user_id=(\d+)")
				str = pattern.match(line.split('?')[5])[1]
				cmd = 'sqlite3 -csv /conanexiles/ConanSandbox/Saved/game.db "select * from characters where playerId=%s;"' % str
				stdoutdata = subprocess.getoutput(cmd)
				username = stdoutdata.split(',')[2]
				yield "Join succeeded: Player %s joined the game." % username

	await client.wait_until_ready()

	logfile = open("/conanexiles/ConanSandbox/Saved/Logs/ConanSandbox.log","r", encoding="utf-8")
	loglines = follow(logfile)
	channel = discord.Object(id=channel_id)
	async for line in loglines:
		print("From game: " + line)
		if line.split(':')[1].startswith(' !'):
			continue
		await client.send_message(channel, line)
		await asyncio.sleep(1)

@client.event
async def on_ready():
	print('Logged in as')
	print(client.user.name)
	print(client.user.id)
	print('------')

@client.event
async def on_message(message):
	if message.author == client.user:
		return
	elif message.content.startswith('!news'):
		if hasattr(ssl, '_create_unverified_context'):
			ssl._create_default_https_context = ssl._create_unverified_context
			rss = 'https://steamcommunity.com/games/440900/rss/'
			feed = feedparser.parse(rss)
			item = feed["items"][0]
			title = item['title']
			url = item['link']
			desc = item['description']
			desc = re.sub('<br />','\n', desc)
			desc = re.sub('<[^<]+?>', '', desc)
			embed = discord.Embed(title=title, url=url, description=desc, color=0x00ff00)
			await client.send_message(message.channel, embed=embed)
	elif message.content.startswith('!status'):
		stdoutdata = subprocess.getoutput("tac /conanexiles/ConanSandbox/Saved/Logs/ConanSandbox.log | grep -m 1 'LogServerStats:'")
		stdoutdata = urllib.parse.unquote(stdoutdata)

		if not stdoutdata:
			return

		pattern = re.compile(r"players=(\d+)&\S+&uptime=(\d+)&memory=\d+:\d+:\d+:(\d+)&cpu_time=(\d+\.\d*)")
		data = pattern.match(stdoutdata.split(' ')[3].split('?')[1])
		await client.send_message(message.channel, "```Server report:\n   Players: %s\n   Uptime: %s\n   Memory Usage: %sGB\n   CPU Loading: %s```" % (data[1], datetime.timedelta(seconds=int(data[2])), '{:.2f}'.format(int(data[3])/(1024*1024*1024)), '{:.2f}'.format(float(data[4]))))

	else: # send into game
		def contain_zh(word):
			global zh_pattern
			match = zh_pattern.search(word)
			return match

		# chinese chars become question marks after rcon, so skip them.
		if contain_zh(message.content):
			return;
		rcon_send_msg(message.author.name + ": " + message.content)

if os.getenv("CONANEXILES_Game_DiscordPlugin_Chat_Enabled") != "1":
	sys.exit(0)

client.loop.create_task(read_game_chat())
client.run(token)
