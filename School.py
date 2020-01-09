from discord.ext import commands
import discord
from SchoolFunctions import LessonImage, APIConnection
import datetime
import asyncio
import json
import requests
import os
import logging
from logdna import LogDNAHandler

with open('config.json') as config_file:
    config = json.load(config_file)

log = logging.getLogger('logdna')
log.setLevel(logging.INFO)
options = {'hostname': 'Zuydbot',
           'index_meta': True,
           'meta': {
               'app': 'API'
           }}
handler = LogDNAHandler(config['logging']['key'], options)
log.addHandler(handler)


class School(commands.Cog):
    """Integrate Untis and Moodle with Discord"""
    def __init__(self, bot):
        self.bot = bot
        self.api = APIConnection()
        self.date = None
        self.time = None
        self.bot.loop.create_task(self.update())
        self.bot.loop.create_task(self.check())

    def get_time(self):
        now = datetime.datetime.now()
        self.date = str(now.day) + '-' + str(now.month) + '-' + str(now.year)
        self.time = str(now.hour) + ':' + format(str(now.minute), '0>2.2')

    def check_embed(self, state, description, footer, guild):
        self.get_time()
        if state == 'passed':
            title = 'Deadline passed!'
            color = 1879160
        else:
            title = 'New deadline!'
            color = 15605837
        payload = {'embeds': [{
            'title': title,
            'description': description,
            'color': color,
            'footer': {
                'text': footer}}]}
        requests.post(guild.webhook, data=json.dumps(payload), headers={'Content-Type': 'application/json'})

    @commands.is_owner()
    @commands.command(hidden=True)
    async def announce(self, ctx, title, *, description):
        guilds = self.api.get_guilds()
        self.get_time()
        for guild in guilds:
            payload = {'embeds': [{
                'title': title,
                'description': description,
                'color': 1786041,
                'footer': {
                    'text': str(ctx.author) + " • Generated: " + self.date + ' ' + self.time
                }}]}
            requests.post(guild.webhook, data=json.dumps(payload), headers={'Content-Type': 'multipart/form-data'})
        await ctx.send(":white_check_mark: **Announcement has been sent to all servers using the Moodle webhook.**")
        log.info(str(ctx.author) + " used command ANNOUNCE", {'meta': {'title': title, 'description': description}})

    @commands.command()
    async def sync(self, ctx, channel: discord.TextChannel):
        """Get deadline warnings in a channel on your guild"""
        if self.api.check_user_moodle(ctx.author.id):
            webhooks = await channel.webhooks()
            names = []
            for hook in webhooks:
                names.append(str(hook.name))
            if 'Moodle' not in names:
                with open(os.getcwd() + "/files/moodle-icon.jpg", "rb") as image:
                    icon = bytearray(image.read())
                webhook = await channel.create_webhook(name="Moodle", avatar=icon)
                self.api.new_guild(ctx.guild.id, ctx.guild.name, webhook.url, ctx.author.id)
                await ctx.send(':white_check_mark: **Your deadlines are synced with this guild in channel** `#' +
                               channel.name + '`')
                log.info(str(ctx.author) + " used command SYNC", {'meta': {'guild': str(ctx.guild.name)}})
            else:
                await ctx.send(':question: **Another webhook named Moodle is already here... Are you cheating on me?**')
                log.info(str(ctx.author) + " used command SYNC", {'level': 'FAIL',
                                                                  'meta': {'description': 'Moodle webhook already present'}})
        else:
            await ctx.send(':negative_squared_cross_mark: **Moodle is not connected to your account**')
            log.info(str(ctx.author) + " used command ANNOUNCE", {'level': 'FAIL',
                                                                  'meta': {'description': 'Moodle is not connected'}})

    @commands.command()
    async def unsync(self, ctx):
        """Stop the deadline warnings in your guild"""
        if self.api.check_guild(ctx.guild.id):
            for channel in ctx.guild.text_channels:
                webhooks = await channel.webhooks()
                for webhook in webhooks:
                    if webhook.name == 'Moodle':
                        await webhook.delete()
            self.api.remove_guild(ctx.guild.id)
            await ctx.send(':mag: **All of your traces have been carefully removed...**')
            log.info(str(ctx.author) + " used UNSYNC")
        else:
            await ctx.send(':question: **It seems like this guild is not synced. Are you trying to trick me?**')
            log.info(str(ctx.author) + " used command ANNOUNCE", {'level': 'FAIL',
                                                                  'meta': {'description': 'Guild is not synced'}})

    @commands.command()
    async def deadlines(self, ctx, user: discord.User = None):
        """Display your deadlines"""
        if user is None:
            user_id = ctx.author.id
        else:
            user_id = user.id
        if self.api.check_user_moodle(user_id):
            self.get_time()
            deadlines, meta = self.api.get_deadlines(user_id)
            footer = 'Last update: ' + meta['last-update'] + ' • Generated: ' + str(self.date) + ' ' + str(self.time) \
                     + ' • Deadlines are updated every day'
            embed = discord.Embed(title='Deadlines', color=0xcc6600)
            deadlines = sorted(deadlines, key=lambda x: x.date)
            opp1 = ''
            opp2 = ''
            for deadline in deadlines:
                if deadline.opportunity == '1':
                    opp1 += '**' + deadline.date + ' // ' + deadline.course + '** ' + deadline.content + '\n'
                elif deadline.opportunity == '2':
                    opp2 += '**' + deadline.date + ' // ' + deadline.course + '** ' + deadline.content + '\n'
            embed.add_field(name='Gelegenheid 1', value=opp1, inline=False)
            embed.add_field(name='Gelegenheid 2', value=opp2, inline=False)
            embed.set_footer(text=footer)
            await ctx.send(embed=embed)
            log.info(str(ctx.author) + " used command DEADLINES")
        else:
            await ctx.send(':negative_squared_cross_mark: **Moodle is not connected to your account**')
            log.info(str(ctx.author) + " used command DEADLINES", {'level': 'FAIL',
                                                                   'meta': {'description': 'Moodle is not connected'}})

    # BETA FUNCTION
    @commands.command()
    async def lessons(self, ctx):
        """Display your lessons"""
        if self.api.check_user_untis(ctx.author.id):
            lessons, meta = self.api.get_lessons(ctx.author.id)
            lessons = sorted(lessons, key=lambda l: l.start)
            found = False
            creator = LessonImage()
            now = datetime.datetime.now()
            for lesson in lessons:
                dt_start = str(now.date()) + ' ' + lesson.start
                dts = datetime.datetime.strptime(dt_start, '%Y-%m-%d %H:%M')
                dt_end = str(now.date()) + ' ' + lesson.end
                dte = datetime.datetime.strptime(dt_end, '%Y-%m-%d %H:%M')
                if dts <= now:
                    if dte >= now:
                        found = True
                elif dts >= now:
                    found = True
                if found is True:
                    try:
                        next_lesson = lessons[lessons.index(lesson) + 1]
                    except IndexError:
                        next_lesson = None
                    path = creator.create_from_lessons(lesson, next_lesson)
                    async with ctx.typing():
                        with open(path, 'rb') as image:
                            await ctx.send(file=discord.File(image, filename='card.png'))
                        return os.remove(path)
            if found is False:
                with open(os.getcwd() + '/files/cards/card_done.png', 'rb') as image:
                    return await ctx.send(file=discord.File(image, filename='card.png'))
            log.info(str(ctx.author) + " used command LESSONS")
        else:
            await ctx.send(':negative_squared_cross_mark: **Untis is not connected to your account**')
            log.info(str(ctx.author) + " used command LESSONS", {'level': 'FAIL',
                                                                 'meta': {'description': 'Untis is not connected'}})

    @commands.is_owner()
    @commands.command(hidden=True)
    async def force_update(self, ctx):
        self.api.update_all()
        await ctx.message.delete()
        log.info(str(ctx.author) + " used command FORCE UPDATE")

    async def update(self):
        while True:
            now = datetime.datetime.now()
            if int(now.hour) == 0:
                self.api.update_all()
                log.info('Updating all deadlines and lessons')
            await asyncio.sleep(3600)

    # BETA FUNCTION
    async def check(self):
        while True:
            now = datetime.datetime.now()
            if int(now.hour) == 12 and int(now.minute) == 0:
                guilds = self.api.get_guilds()
                for guild in guilds:
                    deadlines, meta = self.api.get_deadlines(guild.user)
                    self.get_time()
                    footer = 'Last update: ' + meta['last-update'] + ' • Generated: ' + str(self.date) + ' ' + \
                             str(self.time) + ' • Deadlines are updated every day'
                    for deadline in deadlines:
                        date = datetime.datetime.strptime(deadline.date, '%Y-%m-%d').date()
                        if date == (datetime.datetime.today() - datetime.timedelta(days=3)).date():
                            description = '**' + deadline.date + ' // ' + deadline.course + '** ' + deadline.content \
                                          + ', gelegenheid ' + deadline.opportunity
                            self.check_embed('new', description, footer, guild)
                            log.info("Sending DEADLINE WARNING for " + guild.name, {'meta': {'date': deadline.date,
                                                                                             'course': deadline.course,
                                                                                             'content': deadline.content
                                                                                             }})
                        if date == datetime.datetime.today().date():
                            description = '**' + deadline.course + '** ' + deadline.content + ', gelegenheid ' \
                                          + deadline.opportunity
                            self.check_embed('passed', description, footer, guild)
                            log.info("Sending DEADLINE PASSED for " + guild.name, {'meta': {'date': deadline.date,
                                                                                            'course': deadline.course,
                                                                                            'content': deadline.content
                                                                                            }})
            await asyncio.sleep(60)


def setup(bot):
    bot.add_cog(School(bot))
