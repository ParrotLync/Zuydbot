import discord.ext
from discord.ext import commands
import os
import asyncio
from Logger import AsyncLogger, Logger
import logging
import json
import requests

bot = commands.AutoShardedBot(command_prefix='*')
client = discord.Client()
startup_extensions = ["Extensions", "School"]
with open('config.json') as config_file:
    config = json.load(config_file)

os.system('clear')
print("Starting bot...")
print("")

log = AsyncLogger('Zuydbot', 'Bot', bot)
logger = logging.getLogger('discord')
logger.setLevel(logging.NOTSET)
handler = Logger('Zuydbot', 'Discord', bot)
handler.setFormatter(logging.Formatter('%(levelname)s-%(name)s: %(message)s'))
logger.addHandler(handler)


class Bot(commands.Cog):
    """General bot commands"""
    __slots__ = 'bot'

    def __init__(self):
        self.bot = bot

    @commands.command()
    async def broadcast(self, ctx, *, message):
        """Broadcast a message in your current channel"""
        await ctx.message.delete()
        await ctx.send(message)
        await log.info(str(ctx.author) + ' used command BROADCAST')

    @commands.command()
    async def embed(self, ctx, title, *, description):
        """Send an embed in your current channel"""
        await ctx.message.delete()
        embed = discord.Embed(title=title, description=description, color=0x00ff00)
        await ctx.send(embed=embed)
        await log.info(str(ctx.author) + ' used command EMBED')

    @commands.command()
    async def clear(self, ctx, *, number=100):
        """Delete messages from a text channel."""
        await ctx.message.delete()
        if number <= 100:
            deleted = await ctx.channel.purge(limit=number)
            message = await ctx.send(':ballot_box_with_check:  Deleted {} message(s)'.format(len(deleted)))
            await asyncio.sleep(5)
            await message.delete()
        else:
            await ctx.send(':negative_squared_cross_mark: Je kunt maximaal 100 berichten tegelijkertijd verwijderen!')
        await log.info(str(ctx.author) + ' used command CLEAR')

    @commands.command()
    async def ping(self, ctx):
        """Ping the bot"""
        await ctx.message.delete()
        await ctx.send("Pong! {0}ms".format(round(self.bot.latency, 1)))
        await log.info(str(ctx.author) + ' used command PING')

    @commands.command()
    async def about(self, ctx):
        embed = discord.Embed(title="Zuydbot",
                              description="**Website:** https://zuydbot.cc \n**Discord:** https://discord.gg/eGQg9mA",
                              color=534931)
        embed.set_footer(text="© Zuydbot 2019 • Developer: ParrotLync#2458")
        await ctx.send(embed=embed)
        await log.info(str(ctx.author) + ' used command ABOUT')

    @commands.is_owner()
    @commands.command(hidden=True)
    async def stats(self, ctx):
        await ctx.message.delete()
        guilds = ''
        for guild in bot.guilds:
            guilds += str(guild) + '\n'
        embed = discord.Embed(title="Zuydbot is active on " + str(len(bot.guilds)) + " servers", description=guilds,
                              color=534931)
        await ctx.send(embed=embed)
        await log.info(str(ctx.author) + ' used command STATS')

"""
async def update_status():
    while True:
        requests.get(config['heartbeat_url'])
        asyncio.sleep(600)
"""


@bot.event
async def on_ready():
    print("## Logged in as", bot.user.name)
    print("## ID:", bot.user.id)
    print('')
    await log.info(str(bot.user.name) + " is now online!")
    await bot.change_presence(activity=discord.Game(name='zuydbot.cc | *help'))
    # bot.loop.create_task(update_status())
    if __name__ == "__main__":
        for extension in startup_extensions:
            try:
                bot.load_extension(extension)
            except Exception as e:
                exc = '{}: {}'.format(type(e).__name__, e)
                await log.exception('Failed to load extension {}\n{}'.format(extension, exc))


@bot.event
async def on_command_error(ctx, error):
    opts = {
        'meta': {
            'user': str(ctx.author),
            'guild': str(ctx.guild)
        }
    }
    await log.error(str(error), opts)

bot.add_cog(Bot())
try:
    bot.run(config['tokens']['Zuydbot'])
except RuntimeError:
    handler.warning('Closed before completing cleanup')
