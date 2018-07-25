#!/usr/bin/python3
import discord
import asyncio
import sys
import os

client = discord.Client()
token = os.environ["CONANEXILES_Game_DiscordPlugin_Token"]
channel_id = os.environ["CONANEXILES_Game_DiscordPlugin_Channel"]
msg = str.join(' ', sys.argv[1:])

@client.event
async def on_ready():
	await client.send_message(client.get_channel(channel_id), msg)
	await client.logout()

client.run(token)
