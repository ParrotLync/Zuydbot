import discord
from discord.ext import commands
import requests
import datetime
import os
import asyncio
import json
from PIL import Image, ImageDraw, ImageFont

with open('config.json') as config_file:
    config = json.load(config_file)


class Deadline:
    def __init__(self, date, course, content):
        self.date = date
        self.course = course
        self.content = content


class Lesson:
    def __init__(self, start, end, course, location, teacher):
        self.start = start
        self.end = end
        self.course = course
        self.location = location
        self.teacher = teacher


class Guild:
    def __init__(self, name, webhook, user):
        self.name = name
        self.webhook = webhook
        self.user = user


class LessonImage:
    def __init__(self):
        self.cwhite = 'rgb(255, 255, 255)'
        self.cgray = 'rgb(127, 131, 132)'
        self.font1 = ImageFont.truetype(os.getcwd() + '/files/cards/bahnschrift.ttf', size=200)
        self.font2 = ImageFont.truetype(os.getcwd() + '/files/cards/bahnschrift.ttf', size=100)
        self.font3 = ImageFont.truetype(os.getcwd() + '/files/cards/SegoeUI.ttf', size=120)
        self.font4 = ImageFont.truetype(os.getcwd() + '/files/cards/SegoeUI.ttf', size=90)
        self.font5 = ImageFont.truetype(os.getcwd() + '/files/cards/bahnschrift.ttf', size=40)
        self.date = None
        self.time = None

    def get_time(self):
        now = datetime.datetime.now()
        self.date = str(now.day) + '-' + str(now.month) + '-' + str(now.year)
        self.time = str(now.hour) + ':' + format(str(now.minute), '0>2.2')

    def create_from_lessons(self, lesson, next_lesson):
        if next_lesson is not None:
            next_start = next_lesson.start
            next_course = next_lesson.course
            next_location = next_lesson.location
        else:
            next_start = ''
            next_course = ''
            next_location = ''
        path = self.create(lesson.start, lesson.end, lesson.course, lesson.location, lesson.teacher,
                           next_start, next_course, next_location)
        return path

    def create(self, start, end, course, location, teacher, next_start, next_course, next_location):
        image = Image.open(os.getcwd() + '/files/cards/cardtemplate.png')
        draw = ImageDraw.Draw(image)
        # StartTime
        message = str(start)
        draw.text((990, 520), message, fill=self.cwhite, font=self.font1)

        # EndTime
        message = "- " + str(end)
        draw.text((1460, 590), message, fill=self.cgray, font=self.font2)

        # Course
        message = str(course)
        draw.text((2250, 545), message, fill=self.cwhite, font=self.font3)

        # Location
        message = str(location)
        draw.text((2650, 545), message, fill=self.cgray, font=self.font3)

        # Teacher
        message = str(teacher)
        draw.text((3100, 545), message, fill=self.cgray, font=self.font3)

        # Next StartTime
        if next_start == '':
            message = '---'
        else:
            message = str(next_start)
        draw.text((1460, 770), message, fill=self.cgray, font=self.font2)

        # Next Course / Location
        if next_course == '':
            message = ''
        else:
            message = str(next_course) + " / " + str(next_location)
        draw.text((1730, 748), message, fill=self.cgray, font=self.font4)

        # Last update
        self.get_time()
        message = "Last Update: " + str(self.date)
        draw.text((130, 970), message, fill=self.cgray, font=self.font5)

        # Create file and return path
        now = datetime.datetime.now()
        path = os.getcwd() + '/files/cards/card' + str(now.hour) + str(now.minute) + '.png'
        image.save(path)
        return path


class APIConnection:
    def __init__(self):
        self.base_url = "http://app.zuydbot.cc/api/v2/"
        self.master_header = {'id': config['master_api']['id'],
                              'secret': config['master_api']['secret']}

    def get_key(self, user_id):
        payload = {'user_id': str(user_id)}
        r = requests.get(self.base_url + 'master/fetch/key', json=payload, headers=self.master_header)
        key = r.content.decode('utf-8')
        key = json.loads(key)
        return key['api_key']

    def get_guilds(self):
        guild_list = []
        r = requests.get(self.base_url + 'master/fetch/guilds', headers=self.master_header)
        r = json.loads(r.content.decode('utf-8'))
        guild_json = r['guilds']
        for i in guild_json:
            guild_list.append(Guild(guild_json[i]['guild_name'],
                                    guild_json[i]['webhook_url'],
                                    guild_json[i]['user']))
        return guild_list

    def get_deadlines(self, user_id):
        deadline_list = []
        key = self.get_key(user_id)
        headers = {'api_key': key}
        r = requests.get(self.base_url + 'deadlines', headers=headers)
        r = json.loads(r.content.decode('utf-8'))
        deadline_json = r['deadlines']
        meta = r['meta']
        for i in deadline_json:
            deadline_list.append(Deadline(deadline_json[i]['date'],
                                          deadline_json[i]['course'],
                                          deadline_json[i]['description']))
        return deadline_list, meta

    def get_lessons(self, user_id):
        lesson_list = []
        key = self.get_key(user_id)
        headers = {'api_key': key}
        r = requests.get(self.base_url + 'lessons', headers=headers)
        r = json.loads(r.content.decode('utf-8'))
        lesson_json = r['lessons']
        meta = r['meta']
        for i in lesson_json:
            lesson_list.append(Lesson(lesson_json[i]['start-time'],
                                      lesson_json[i]['end-time'],
                                      lesson_json[i]['course'],
                                      lesson_json[i]['location'],
                                      lesson_json[i]['teacher']))
        return lesson_list, meta

    def new_guild(self, guild_id, guild_name, webhook_url, user):
        payload = {'guild_id': str(guild_id),
                   'guild_name': str(guild_name),
                   'webhook_url': str(webhook_url),
                   'user': str(user)}
        requests.post(self.base_url + 'master/guild/new', headers=self.master_header, json=payload)

    def remove_guild(self, guild_id):
        payload = {'guild_id': guild_id}
        requests.post(self.base_url + 'master/guild/remove', headers=self.master_header, json=payload)

    def check_guild(self, guild_id):
        payload = {'guild_id': guild_id}
        r = requests.get(self.base_url + 'master/guild/check', headers=self.master_header, json=payload)
        r = json.loads(r.content.decode('utf-8'))
        if r['exists'] == 'True':
            return True
        if r['exists'] == 'False':
            return False

    def check_user_moodle(self, user_id):
        payload = {'user_id': user_id}
        r = requests.get(self.base_url + 'master/user/check', headers=self.master_header, json=payload)
        r = json.loads(r.content.decode('utf-8'))
        if r['user_exists'] == 'True' and r['moodle_exists'] == 'True':
            return True
        if r['user_exists'] == 'False':
            return False

    def check_user_untis(self, user_id):
        payload = {'user_id': user_id}
        r = requests.get(self.base_url + 'master/user/check', headers=self.master_header, json=payload)
        r = json.loads(r.content.decode('utf-8'))
        if r['user_exists'] == 'True' and r['untis_exists'] == 'True':
            return True
        if r['user_exists'] == 'False':
            return False

    def update_all(self):
        requests.get(self.base_url + 'master/update', headers=self.master_header)


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

    @classmethod
    def check_embed(cls, state, description, footer, guild):
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
        requests.post(guild.webhook, data=json.dumps(payload), headers={'Content-Type': 'multipart/form-data'})

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
            else:
                await ctx.send(':question: **Another webhook named Moodle is already here... Are you cheating on me?**')
        else:
            await ctx.send(':negative_squared_cross_mark: **Moodle is not connected to your account**')

    @commands.command()
    async def unsync(self, ctx):
        """Stop the deadline warnings in your guild"""
        if self.api.check_guild(ctx.guild.id):
            self.api.remove_guild(ctx.guild.id)
            await ctx.send(':mag: **All of your traces have been carefully removed...**')
        else:
            await ctx.send(':question: **It seems like this guild is not synced. Are you trying to trick me?**')

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
            content = ''
            for deadline in deadlines:
                header = '**' + deadline.date + ' // ' + deadline.course + '** '
                content += header + deadline.content + '\n'
            embed = discord.Embed(title='Deadlines', description=content, color=0xcc6600)
            embed.set_footer(text=footer)
            await ctx.send(embed=embed)
        else:
            await ctx.send(':negative_squared_cross_mark: **Moodle is not connected to your account**')

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
        else:
            await ctx.send(':negative_squared_cross_mark: **Untis is not connected to your account**')

    async def update(self):
        while True:
            now = datetime.datetime.now()
            if int(now.hour) == 0:
                self.api.update_all()
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
                        date = datetime.datetime.strptime(deadline.date, '%Y-%m-%d')
                        if date == (datetime.datetime.today() - datetime.timedelta(days=3)).date():
                            description = '**' + deadline.date + ' // ' + deadline.course + '** ' + deadline.content
                            self.check_embed('new', description, footer, guild)
                        if date == datetime.datetime.today().date():
                            description = '**' + deadline.course + '** ' + deadline.content
                            self.check_embed('passed', description, footer, guild)
            requests.get(config['heartbeat_url'])
            await asyncio.sleep(60)


def setup(bot):
    bot.add_cog(School(bot))
