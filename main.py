import os

import discord
import re
import sqlite3
from discord.ext import commands
from discord_slash import SlashCommand, SlashContext
from discord_slash.utils.manage_commands import create_option, create_choice
from discord_slash.model import SlashCommandOptionType
from dotenv import load_dotenv
import random
from datetime import datetime, date
import requests
import json
import io
import aiohttp
import operator

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
# CHANNEL = int(os.getenv('DISCORD_CHANNEL'))

RIOT_KEY = os.getenv('RIOT_KEY')
GUILDS = os.getenv('GUILDS')

bot = commands.Bot(command_prefix='?')
slash = SlashCommand(bot, sync_commands=True)

conn = sqlite3.connect('users.db')
conn.execute('PRAGMA foreign_keys = ON')

c = conn.cursor()

c.execute("CREATE TABLE IF NOT EXISTS summoner"
          "(summoner_id  TEXT PRIMARY KEY NOT NULL UNIQUE,"
          "summoner_name TEXT NOT NULL,"
          "server TEXT,"
          "owner TEXT)")

# c.execute("CREATE TABLE IF NOT EXISTS rank"
#           "(queue_type TEXT NOT NULL,"
#           "division TEXT NOT NULL,"
#           "tier TEXT NOT NULL,"
#           "summoner_id TEXT NOT NULL,"
#           "FOREIGN KEY(summoner_id) REFERENCES summoner(summoner_id) ON DELETE CASCADE)")

ALL_CHAMPIONS_URL = 'http://ddragon.leagueoflegends.com/cdn/11.11.1/data/en_US/champion.json'
GET_SUMMONER_URL = 'https://{}.api.riotgames.com/lol/summoner/v4/summoners/by-name/{}?api_key=' + RIOT_KEY
GET_RANK_URL = 'https://{}.api.riotgames.com/lol/league/v4/entries/by-summoner/{}?api_key=' + RIOT_KEY

guild_ids = [int(guild) for guild in GUILDS.split(',')]

servers = [create_choice(name='EUW', value='EUW1'),
           create_choice(name='EUNE', value='EUN1'),
           create_choice(name='BR', value='BR1'),
           create_choice(name='JP', value='JP1'),
           create_choice(name='KR', value='KR'),
           create_choice(name='LA1', value='LA1'),
           create_choice(name='LA2', value='LA2'),
           create_choice(name='NA', value='NA1'),
           create_choice(name='OC', value='OC1'),
           create_choice(name='RU', value='RU'),
           create_choice(name='TR', value='TR1')]

roles = [create_choice(name='Fighter', value='Fighter'),
         create_choice(name='Tank', value='Tank'),
         create_choice(name='Mage', value='Mage'),
         create_choice(name='Assassin', value='Assassin'),
         create_choice(name='Support', value='Support'),
         create_choice(name='Marksman', value='Marksman')]


@bot.event
async def on_command_error(ctx, error):
    print(error)
    await ctx.send(error)


@bot.event
async def on_ready():
    print(f"{bot.user.name} has successfully connected")


@slash.slash(name='test',
             description='test command')
async def slash_test(ctx: SlashContext):
    print(ctx.author.id)


@bot.command(name="test")
async def test(ctx, *args):
    print(ctx.message.guild.id)
    print(ctx.message.author)
    print(ctx.message.author.id)
    print(ctx.message.author.display_name)
    print(ctx.message.author.name)
    print(args)


@slash.slash(name='random',
             description='Send a random champion name',
             options=[
                 create_option(
                     name='role',
                     description='the type of the desired champion',
                     option_type=SlashCommandOptionType.STRING,
                     required=False,
                     choices=roles
                 ),
                 create_option(
                     name='secondary_role',
                     description='secondary role of the desired champion',
                     option_type=SlashCommandOptionType.STRING,
                     required=False,
                     choices=roles
                 )
             ])
async def random_champ(ctx: SlashContext, role=None, secondary_role=None):
    req = json.loads(requests.get(ALL_CHAMPIONS_URL).text)
    champions = list(req['data'].keys())
    if role:
        print(role)
        filtered_champions = set()
        for champion in champions:
            if role in req['data'][champion]['tags']:
                if secondary_role and secondary_role in req['data'][champion]['tags']:
                    filtered_champions.add(req['data'][champion]['name'])
                else:
                    filtered_champions.add(req['data'][champion]['name'])
        if len(filtered_champions) > 0:
            filtered_champions = list(filtered_champions)
            i = random.choice(filtered_champions)
            await ctx.send(content=i)
        else:
            await ctx.send("No champion with that role available")
    else:
        i = random.choice(champions)
        await ctx.send(content=i)


@slash.slash(name='register',
             description='register summoner to your discord-user',
             options=[
                 create_option(
                     name='summoner_name',
                     description='the summoner name you want to link to your user',
                     option_type=SlashCommandOptionType.STRING,
                     required=True
                 ),
                 create_option(
                     name='server',
                     description='the server the summoner is on',
                     option_type=SlashCommandOptionType.STRING,
                     required=True,
                     choices=servers
                 )
             ])
async def register(ctx, summoner_name, server):
    if summoner_name and server:
        summoner_resp = requests.get(GET_SUMMONER_URL.format(server, summoner_name))
        summoner_id = ''
        if summoner_resp.status_code == 200:
            print("summoner resp: ", summoner_resp.status_code)
            summoner_data = json.loads(summoner_resp.text)
            summoner_id = summoner_data['id']
            try:
                c.execute("INSERT INTO summoner(summoner_id, summoner_name, server, owner) VALUES(?,?,?,?)",
                         (summoner_id, summoner_name, server, str(ctx.author.id)))
            except sqlite3.IntegrityError:
                await ctx.send("Summoner is already registered")
                return
            print("summoner added")
            conn.commit()
        else:
            await ctx.send(f"Could not find a summoner with name {summoner_name} on {server}.")
            return
        message = ''
        if summoner_id is not None:
            rank_resp = requests.get(GET_RANK_URL.format(server, summoner_id))
            if rank_resp and rank_resp.status_code == 200:
                print("rank resp: ", rank_resp.status_code)
                rank_data = json.loads(rank_resp.text)
                for data in rank_data:
                    tier = data['tier']
                    rank = data['rank']
                    queue_type = data['queueType']
                    lp = data['leaguePoints']
                    message += f'{summoner_name} at {tier} {rank} - {lp} LP in {queue_type} found \n'
                if message != '':
                    await ctx.send(message)
                else:
                    await ctx.send(f"{summoner_name} found and registered")
            else:
                await ctx.send(f"{summoner_name} found and registered")


@slash.slash(name='rank',
             description='retrieves the rank of summoners linked to your user')
async def get_rank(ctx):
    c.execute("SELECT summoner_name, server, summoner_id FROM summoner WHERE owner = ?",
              (ctx.author.id,))
    data = c.fetchall()
    print(data)
    message = ''
    for i in data:
        summoner_name = i[0]
        server = i[1]
        summoner_id = i[2]
        rank_resp = requests.get(GET_RANK_URL.format(server, summoner_id))
        print("rank resp: ", rank_resp.status_code)
        rank_data = json.loads(rank_resp.text)
        if rank_data:
            for data in rank_data:
                if data['summonerName'] != summoner_name:
                    c.execute('UPDATE summoner SET summoner_name=? WHERE summoner_id=?',
                              (data['summonerName'], summoner_id))
                    message += f'*Updating summoner name from {summoner_name} to {data["summonerName"]}*\n'
                message += f"{data['summonerName']} on {server} is {data['tier']} {data['rank']}" \
                           f" - {data['leaguePoints']} LP in {data['queueType']}\n"
            print(i)
        else:
            message += f'{summoner_name} is unranked'
    if len(message):
        await ctx.send(message)
    else:
        await ctx.send("there are no summoners linked to your user")


@slash.slash(name='delete',
             description='delete all summoners or a specific summoner linked to user',
             options=[
                create_option(
                    name='summoner_name',
                    description='the summoner name you want to delete'
                                '(leave empty to delete all summoners)',
                    option_type=SlashCommandOptionType.STRING,
                    required=False
                ),
                create_option(
                     name='server',
                     description='the server your summoner is on',
                     option_type=SlashCommandOptionType.STRING,
                     required=False,
                     choices=servers
                )
             ])
async def delete_summoners(ctx, summoner_name=None, server=None):
    if summoner_name:
        c.execute('DELETE FROM summoner WHERE summoner_name=? AND server=? AND owner=?',
                  (summoner_name, server, ctx.author.id))
        if c.rowcount > 0:
            conn.commit()
            await ctx.send(f'{summoner_name} deleted')
        else:
            await ctx.send(f"the summoner {summoner_name} could not be found or is not linked to your user")

    else:
        c.execute('DELETE FROM summoner WHERE owner=?', (ctx.author.id,))
        if c.rowcount > 0:
            conn.commit()
            await ctx.send("all summoners deleted")
        else:
            await ctx.send("no summoners linked to your user")


if __name__ == '__main__':
    bot.run(TOKEN)
    conn.close()
