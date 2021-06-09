import os

import discord
import re
import sqlite3
from discord.ext import commands
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

bot = commands.Bot(command_prefix='!')

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
          "FOREIGN KEY(summoner_id) REFERENCES summoner(summoner_id))")


ALL_CHAMPIONS_URL = 'http://ddragon.leagueoflegends.com/cdn/11.11.1/data/en_US/champion.json'
GET_SUMMONER_URL = 'https://{}.api.riotgames.com/lol/summoner/v4/summoners/by-name/{}?api_key=' + RIOT_KEY
GET_RANK_URL = 'https://{}.api.riotgames.com/lol/league/v4/entries/by-summoner/{}?api_key=' + RIOT_KEY


@bot.event
async def on_command_error(ctx, error):
    print(error)
    await ctx.send(error)


@bot.event
async def on_ready():
    print(f"{bot.user.name} has successfully connected")


@bot.command(name="test")
async def test(ctx, *args):
    print(ctx.message.author)
    print(ctx.message.author.id)
    print(ctx.message.author.display_name)
    print(ctx.message.author.name)
    print(args)


@bot.command(name='random',
             help='returns a random champion')
async def random_champ(ctx, *args):
    req = json.loads(requests.get(ALL_CHAMPIONS_URL).text)
    champions = list(req['data'].keys())
    if len(args) > 0:
        filtered_champions = set()
        for champion in champions:
            for arg in args:
                if arg in req['data'][champion]['tags']:
                    filtered_champions.add(req['data'][champion]['id'])
        if len(filtered_champions) > 0:
            filtered_champions = list(filtered_champions)
            i = random.choice(filtered_champions)
            await ctx.send(i)
        else:
            await ctx.send("No champion with that role available")
    else:
        i = random.choice(champions)
        await ctx.send(i)


@bot.command(name='register', aliases=['reg'], help='link your discord to a summoner name on a server\n'
                                                    'format: !register <summoner_name> <server>\n'
                                                    'example: !register grodvidar euw',
             brief='link your discord to a summoner name on a server')
async def register(ctx, *args):
    if len(args) > 1:
        server = args[-1]
        if server.lower() != 'kr' and server.lower() != 'ru':
            server += '1'
        summoner_name = ' '.join(args[:-1])
        summoner_resp = requests.get(GET_SUMMONER_URL.format(server, summoner_name))
        summoner_id = ''
        if summoner_resp.status_code == 200:
            print("summoner resp: ", summoner_resp.status_code)
            summoner_data = json.loads(summoner_resp.text)
            summoner_id = summoner_data['id']
            c.execute("INSERT INTO summoner(summoner_id, summoner_name, server, owner) VALUES(?,?,?,?)",
                      (summoner_id, summoner_name, server, str(ctx.message.author.id)))
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
                    c.execute("INSERT INTO rank(queue_type, division, tier, summoner_id) VALUES(?,?,?,?)",
                              (queue_type, rank, tier, summoner_id))
                    conn.commit()
                await ctx.send(f"{summoner_name} at {tier} {rank} found and registered")
            else:
                await ctx.send(f"could not find a rank for {summoner_name}")


@bot.command(name='rank', help='')
async def get_rank(ctx, *args):
    if len(args) < 1:
        c.execute("SELECT s.summoner_name, s.server, r.tier, r.division, r.queue_type FROM summoner s "
                  "LEFT JOIN rank r on s.summoner_id=r.summoner_id "
                  "WHERE s.owner = ?",
                  (ctx.message.author.id,))
        data = c.fetchall()
        message = ''
        for i in data:
            if len(i) == 5:
                message += f"{i[0]} on {i[1]} is {i[2]} {i[3]} in {i[4]}\n"
            else:
                message += f"{i[0]} on {i[1]} has no rank\n"
        await ctx.send(message)

if __name__ == '__main__':
    bot.run(TOKEN)
    conn.close()
