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
from urllib import parse

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
				chatstr = re.sub(r' said', '', re.sub(r'^.*Character ', '', line))
				yield chatstr
			elif "Join request:" in line:
				url = 'http://example.com/?ccc=123&'+'&'.join('/'.join(line.split('/')[1:]).split('?'))
				query_Name = parse.parse_qs(parse.urlparse(url).query)['Name'][0]
				query_dw_user_id = parse.parse_qs(parse.urlparse(url).query)['dw_user_id'][0]
				#print("Name= %s, dw_user_id= %s" % (query_Name,query_dw_user_id))

				cmd = 'sqlite3 -csv /conanexiles/ConanSandbox/Saved/game.db "select * from characters where playerId=%s;"' % query_dw_user_id
				stdoutdata = subprocess.getoutput(cmd)
				try:
					username = stdoutdata.split(',')[2]
					yield "Join succeeded: Player %s joined the game." % username
				except IndexError:
					print("Join request Error: %s - %s" % (line, query_dw_user_id))
					yield "Join succeeded: Player %s joined the game." % query_Name
				except:
					print("Join request Error: %s - %s" % (line, query_dw_user_id))
					yield "Join succeeded: Player %s joined the game." % query_Name
			elif "BattlEyeLogging:" in line and "disconnected" in line:
				name = line.split(']')[2].split(' ')[6]
				yield "Player disconnected: %s" % name
			elif "Allocator Stats for binned2:" in line:
				subprocess.call(['/usr/bin/discord_broadcast', '"Server crash, restarting now..."'])
				subprocess.call(['supervisorctl', 'restart', 'conanexilesServer'])
				await asyncio.sleep(5)
				subprocess.call(['supervisorctl', 'restart', 'conanexilesChat'])
				sys.exit(0)

	await client.wait_until_ready()

	logfile = open("/conanexiles/ConanSandbox/Saved/Logs/ConanSandbox.log","r", encoding="utf-8")
	loglines = follow(logfile)
	channel = discord.Object(id=channel_id)
	async for line in loglines:
		print("From game: " + line)
		if line.split(':')[1].startswith(' !'):
			continue
		try:
			await client.send_message(channel, line)
		except:
			print("Fail to send message to discord: %s" % line)
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
			embed = discord.Embed(title=title, url=url, description=desc[0:2000], color=0x00ff00)
			await client.send_message(message.channel, embed=embed)
	elif message.content.startswith('!status'):
		stdoutdata = subprocess.getoutput("tac /conanexiles/ConanSandbox/Saved/Logs/ConanSandbox.log | grep -m 1 'LogServerStats:'")
		stdoutdata = urllib.parse.unquote(stdoutdata)

		if not stdoutdata:
			return

		pattern = re.compile(r"players=(\d+)&\S+&uptime=(\d+)&memory=\d+:\d+:\d+:(\d+)&cpu_time=(\d+\.\d*)")
		try:
			data = pattern.match(stdoutdata.split('report')[1].split('?')[1])
			status_str = "Server report:\n   Players: %s\n   Uptime: %s\n   Memory Usage: %sGB\n   CPU Loading: %s" % (data[1], datetime.timedelta(seconds=int(data[2])), '{:.2f}'.format(int(data[3])/(1024*1024*1024)), '{:.2f}'.format(float(data[4])))

			# show players
			online_player = ""
			cmd = 'sqlite3 -csv /conanexiles/ConanSandbox/Saved/game.db "select * from characters,account where account.online = 1 and account.user = characters.playerId;"'
			stdoutdata = subprocess.getoutput(cmd)
			# Status Error: 76561198070232842,35839,"喬巧",50,3,39590,1,"",1533895072,"",76561198070232842,1
			if stdoutdata:
				online_player = "\nOnline Players:\n"
				for line in stdoutdata.split('\n'):
					username = line.split(',')[2]
					online_player += "   %s\n" % username

			await client.send_message(message.channel, "```%s%s```" % (status_str, online_player))
		except IndexError:
			print("Status Error: %s" % stdoutdata)
		except:
			print("Status Error: %s" % stdoutdata)
	elif message.content.startswith('!player'):
		cmd = 'sqlite3 -csv /conanexiles/ConanSandbox/Saved/game.db "select * from characters,account where account.online = 1 and account.user = characters.playerId;"'
		stdoutdata = subprocess.getoutput(cmd)
		if stdoutdata:
			outstr = "```Online Players\n"
			for line in stdoutdata.split('\n'):
				username = line.split(',')[2]
				outstr += "   %s\n" % username
			outstr += "```"
			await client.send_message(message.channel, outstr)
		else:
			await client.send_message(message.channel, "Currently no player online.")
	elif message.content.startswith('!restart'):
		stdoutdata = subprocess.getoutput("tac /conanexiles/ConanSandbox/Saved/Logs/ConanSandbox.log | grep -m 1 'LogServerStats:'")
		stdoutdata = urllib.parse.unquote(stdoutdata)
		if not stdoutdata:
			subprocess.call(['/usr/bin/discord_broadcast', 'I can\'t get the server uptime, and can\'t do it now.'])
			return

		pattern = re.compile(r"players=(\d+)&\S+&uptime=(\d+)&memory=\d+:\d+:\d+:(\d+)&cpu_time=(\d+\.\d*)")
		data = pattern.match(stdoutdata.split('report')[1].split('?')[1])
		seconds=int(data[2])
		datetime.timedelta(seconds)
		if seconds < 24*60*60:
			subprocess.call(['/usr/bin/discord_broadcast', 'Server uptime is not more than 1 day, so can\'t do it.'])
			return

		cmd = 'sqlite3 -csv /conanexiles/ConanSandbox/Saved/game.db "select count(*) from characters,account where account.online = 1 and account.user = characters.playerId;"'
		stdoutdata = subprocess.getoutput(cmd)
		if stdoutdata != '0':
			subprocess.call(['/usr/bin/discord_broadcast', 'I can\'t do that, there are still %s players in the game.' % stdoutdata])
			return
		subprocess.call(['/usr/bin/discord_broadcast', 'Roger that, server is restarting...'])
		subprocess.call(['supervisorctl', 'restart', 'conanexilesServer'])
		await asyncio.sleep(5)
		subprocess.call(['supervisorctl', 'restart', 'conanexilesChat'])
		sys.exit(0)
	elif message.content.startswith('!search'):
		token = message.content[8:]
		cmd = 'sqlite3 -csv -header /conanexiles/ConanSandbox/Saved/game.db "select quote(g.name) as GUILD, quote(c.char_name) as NAME, case c.rank WHEN \'3\' then \'Owner\' WHEN \'2\' then \'Leader\' WHEN \'1\' then \'Officer\' WHEN \'0\' then \'Peon\' ELSE c.rank END RANK, c.level as LEVEL, datetime(c.lastTimeOnline, \'unixepoch\') as LASTONLINE from characters as c left outer join guilds as g on g.guildid = c.guild left outer join actor_position as ap on ap.id = c.id order by g.name, c.rank desc, c.level desc, c.char_name;" | grep %s' % token
		stdoutdata = subprocess.getoutput(cmd)
		if not stdoutdata:
			return
		dbstr = stdoutdata.split("\n")
		outstr = "```GUILD,NAME,RANK,LEVEL,LASTONLINE\n"
		for line in dbstr:
			outstr += line + "\n"
		outstr += "```"
		await client.send_message(message.channel, outstr)

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
