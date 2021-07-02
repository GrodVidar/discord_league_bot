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

c.execute("CREATE TABLE IF NOT EXISTS rank"
          "(queue_type TEXT NOT NULL,"
          "division TEXT NOT NULL,"
          "tier TEXT NOT NULL,"
          "summoner_id TEXT NOT NULL,"
          "FOREIGN KEY(summoner_id) REFERENCES summoner(summoner_id) ON DELETE CASCADE)")

ALL_CHAMPIONS_URL = 'http://ddragon.leagueoflegends.com/cdn/11.11.1/data/en_US/champion.json'
GET_SUMMONER_URL = 'https://{}.api.riotgames.com/lol/summoner/v4/summoners/by-name/{}?api_key=' + RIOT_KEY
GET_RANK_URL = 'https://{}.api.riotgames.com/lol/league/v4/entries/by-summoner/{}?api_key=' + RIOT_KEY

guild_ids = [int(guild) for guild in GUILDS.split(',')]

@bot.event
async def on_command_error(ctx, error):
    print(error)
    await ctx.send(error)


@bot.event
async def on_ready():
    print(f"{bot.user.name} has successfully connected")


@slash.slash(name='test',
             guild_ids=guild_ids,
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
             guild_ids=guild_ids,
             description='Send a random champion name',
             options=[
                 create_option(
                     name='role',
                     description='the type of the desired champion',
                     option_type=SlashCommandOptionType.STRING,
                     required=False,
                     choices=[
                         create_choice(
                             name='Fighter',
                             value='Fighter'
                         ),
                         create_choice(
                             name='Tank',
                             value='Tank'
                         ),
                         create_choice(
                             name='Mage',
                             value='Mage'
                         ),
                         create_choice(
                             name='Assassin',
                             value='Assassin'
                         ),
                         create_choice(
                             name='Support',
                             value='Support'
                         ),
                         create_choice(
                             name='Marksman',
                             value='Marksman'
                         )
                     ]
                 )
             ])
async def slash_random_champ(ctx: SlashContext, role):
    req = json.loads(requests.get(ALL_CHAMPIONS_URL).text)
    champions = list(req['data'].keys())
    if len(role) > 0:
        print(role)
        filtered_champions = set()
        for champion in champions:
            if role in req['data'][champion]['tags']:
                filtered_champions.add(req['data'][champion]['id'])
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
             guild_ids=guild_ids,
             description='register summoner to your discord-user',
             options=[
                 create_option(
                     name='summoner_name',
                     description='the summoner name of the account you want to link',
                     option_type=SlashCommandOptionType.STRING,
                     required=True
                 ),
                 create_option(
                     name='server',
                     description='the server the account is on kek',
                     option_type=SlashCommandOptionType.STRING,
                     required=True,
                     choices=[
                         create_choice(
                             name='EUW',
                             value='EUW1'
                         ),
                         create_choice(
                             name='EUNE',
                             value='EUN1'
                         ),
                         create_choice(
                             name='BR',
                             value='BR1'
                         ),
                         create_choice(
                             name='JP',
                             value='JP1'
                         ),
                         create_choice(
                             name='KR',
                             value='KR'
                         ),
                         create_choice(
                             name='LA1',
                             value='LA1'
                         ),
                         create_choice(
                             name='LA2',
                             value='LA2'
                         ),
                         create_choice(
                             name='NA',
                             value='NA1'
                         ),
                         create_choice(
                             name='OC',
                             value='OC1'
                         ),
                         create_choice(
                             name='RU',
                             value='RU'
                         ),
                         create_choice(
                             name='TR',
                             value='TR1'
                         ),
                     ]
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
            c.execute("INSERT INTO summoner(summoner_id, summoner_name, server, owner) VALUES(?,?,?,?)",
                      (summoner_id, summoner_name, server, str(ctx.author.id)))
            print("summoner added")
            conn.commit()
        else:
            await ctx.send(f"Could not find a summoner with name {summoner_name} on {server}.")
            return
        tier = ''
        rank = ''
        if summoner_id is not None:
            rank_resp = requests.get(GET_RANK_URL.format(server, summoner_id))
            if rank_resp.status_code == 200:
                print("rank resp: ", summoner_resp.status_code)
                rank_data = json.loads(rank_resp.text)
                for data in rank_data:
                    tier = data['tier']
                    rank = data['rank']
                    queue_type = data['queueType']
                    if tier and rank and queue_type:
                        c.execute("INSERT INTO rank(queue_type, division, tier, summoner_id) VALUES(?,?,?,?)",
                                  (queue_type, rank, tier, summoner_id))
                        conn.commit()
                if rank and tier:
                    await ctx.send(f"{summoner_name} at {tier} {rank} found and registered")
                else:
                    await ctx.send(f"{summoner_name} found and registered")
            else:
                await ctx.send(f"could not find a rank for {summoner_name}")


@slash.slash(name='rank',
             guild_ids=guild_ids,
             description='retrieves the rank of summoners linked to your discord account')
async def get_rank(ctx):
    c.execute("SELECT s.summoner_name, s.server, r.tier, r.division, r.queue_type FROM summoner s "
              "LEFT JOIN rank r on s.summoner_id=r.summoner_id "
              "WHERE s.owner = ?",
              (ctx.author.id,))
    data = c.fetchall()
    print(data)
    message = ''
    for i in data:
        print(i)
        if i[0] and i[1] and i[2] and i[3] and [4]:
            message += f"{i[0]} on {i[1]} is {i[2]} {i[3]} in {i[4]}\n"
        elif not i[2] and not i[3] and not i[4]:
            message += f"{i[0]} on {i[1]} has no rank\n"
    if len(message):
        await ctx.send(message)
    else:
        await ctx.send("there are no summoners linked to your account")


if __name__ == '__main__':
    bot.run(TOKEN)
    conn.close()
