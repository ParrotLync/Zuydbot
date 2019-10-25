import discord
from discord.ext import commands
import requests
import datetime
from icalendar import Calendar
import os
import sqlite3
import asyncio
import shutil
from Logger import AsyncLogger, Logger
import json

with open('config.json') as config_file:
    config = json.load(config_file)


class SqliteDBConnection:
    def __init__(self):
        self.database_path = os.path.join(os.getcwd() + '/files/zuydbot.db')
        self.connection = sqlite3.connect(self.database_path)
        self.cursor = self.connection.cursor()

    def execute_query(self, input_query, *arg):
        self.cursor.execute(input_query, arg)
        return self.cursor.fetchall()

    def modify_value(self, modify_value_query, *arg):
        self.cursor.execute(modify_value_query, arg)
        self.connection.commit()


class Deadlines:
    def __init__(self, bot, database, log):
        self.bot = bot
        self.database = database
        self.date = None
        self.time = None
        self.log = log

    def get_time(self):
        now = datetime.datetime.now()
        self.date = str(now.day) + '-' + str(now.month) + '-' + str(now.year)
        self.time = str(now.hour) + ':' + format(str(now.minute), '0>2.2')

    def footer(self, guild):
        self.get_time()
        query = "SELECT last_deadline_update FROM GUILDS WHERE guild_name = ?"
        update = self.database.execute_query(query, guild)
        update = str(update[0][0])
        footer = 'Last update: ' + update + ' • Generated: ' + str(self.date) + ' ' + str(self.time) \
                 + ' • Deadlines are updated every day'
        return footer

    def download(self, guild):
        query = "SELECT url FROM GUILDS WHERE guild_name = ?"
        url = self.database.execute_query(query, guild)
        r = requests.get(url[0][0])
        self.get_time()
        file = os.getcwd() + '/files/guilds/' + str(guild) + '/icalexport.ics'
        os.makedirs(os.path.dirname(file), exist_ok=True)
        with open(file, 'wb') as cal:
            cal.write(r.content)
        query = "UPDATE GUILDS SET last_deadline_update = ? WHERE guild_name = ?"
        self.database.modify_value(query, self.date, guild)
        handler.info('Updated calendar file for ' + str(guild))

    def get(self, guild):
        query = "DELETE FROM DEADLINES WHERE guild = ?"
        self.database.modify_value(query, guild)
        try:
            with open(os.getcwd() + '/files/guilds/' + str(guild) + '/icalexport.ics', 'rb') as g:
                gcal = Calendar.from_ical(g.read())
                for component in gcal.walk():
                    if component.name == 'VEVENT':
                        date = component.get('DTSTART')
                        date = str(date.dt)
                        date = date[:10]
                        course = component.get('CATEGORIES').to_ical()
                        course = str(course)
                        if 'H-ICT' in course:
                            course = course[8:12]
                        if '340' in course:
                            course = course[6:11]
                        content = component.get('SUMMARY')
                        content = content.strip(' moet worden ingeleverd')
                        content = content.replace('&amp;', '&')
                        query = "INSERT INTO DEADLINES (guild, date, course, content) VALUES(?, ?, ?, ?)"
                        self.database.modify_value(query, guild, date, course, content)
        except FileNotFoundError:
            handler.error('No calendar file found for ' + str(guild))

    def embed(self, guild):
        footer = self.footer(guild)
        self.get(guild)
        content = ''
        query_dates = "SELECT date FROM DEADLINES WHERE guild = ?"
        dates = self.database.execute_query(query_dates, guild)
        query_courses = "SELECT course FROM DEADLINES WHERE guild = ?"
        courses = self.database.execute_query(query_courses, guild)
        query_contents = "SELECT content FROM DEADLINES WHERE guild = ?"
        contents = self.database.execute_query(query_contents, guild)
        for i in range(len(dates)):
            header = '**' + str(dates[i][0]) + ' // ' + str(courses[i][0]) + '** '
            content += header + str(contents[i][0]) + '\n'
        embed = discord.Embed(title='Deadlines', description=content, color=0xcc6600)
        embed.set_footer(text=footer)
        return embed


class Moodle(commands.Cog):
    """Moodle Integration"""
    def __init__(self, bot, deadlines, database, log):
        self.bot = bot
        self.deadlines = deadlines
        self.database = database
        self.bot.loop.create_task(self.check())
        self.log = log

    def check_setup(self, ctx):
        query = "SELECT guild_name FROM GUILDS WHERE guild_name = ?"
        result = self.database.execute_query(query, ctx.guild.id)
        try:
            if str(result[0][0]) == str(ctx.guild.id):
                return True
        except IndexError:
            return False

    @commands.is_owner()
    @commands.command(hidden=True)
    async def announce(self, ctx, title, *, description):
        """Send a message to all servers using Moodle webhook"""
        await ctx.message.delete()
        self.deadlines.get_time()
        query = "SELECT webhook FROM GUILDS"
        webhook_list = self.database.execute_query(query)
        for webhook in webhook_list:
            payload = {'embeds': [{
                'title': title,
                'description': description,
                'color': 1786041,
                'footer': {
                    'text': str(ctx.author) + " • Generated: " + self.deadlines.date + ' ' + self.deadlines.time
                }}]}
            requests.post(webhook[0], data=json.dumps(payload), headers={'Content-Type': 'multipart/form-data'})
        await ctx.send(":white_check_mark: **Announcement has been sent to all servers using the Moodle webhook.**")
        opts = {
            'meta': {
                'user': ctx.author,
                'title': title,
                'description': description
            }
        }
        await self.log.info('An announcements was sent to all servers using Moodle webhook', opts)

    @commands.command(hidden=True)
    async def setup(self, ctx, url):
        """Setup the deadline synchronisation"""
        if self.check_setup(ctx) is False:
            with open(os.getcwd() + "/files/moodle-icon.jpg", "rb") as image:
                icon = bytearray(image.read())
            channel = await ctx.guild.create_text_channel(name='Deadlines')
            webhook = await channel.create_webhook(name='Moodle', avatar=icon)
            await ctx.guild.create_role(name='Bot Controller')
            webhook_url = webhook.url
            query = "INSERT INTO GUILDS (guild_name, webhook, url) VALUES(?, ?, ?)"
            self.database.modify_value(query, ctx.guild.id, str(webhook_url), str(url))
            await ctx.send(':white_check_mark: **Setup completed!**')
            opts = {
                'meta': {
                    'guild': str(ctx.guild),
                    'url': url
                }
            }
            await self.log.info(str(ctx.author) + ' used command SETUP', opts)
        elif self.check_setup(ctx) is True:
            await ctx.send(':negative_squared_cross_mark: **The setup has already been completed!**')

    @commands.has_role('Bot Controller')
    @commands.command(hidden=True)
    async def reset(self, ctx):
        """Reset the deadline synchronisation"""
        if self.check_setup(ctx) is True:
            channels = ctx.guild.channels
            for channel in channels:
                if str(channel) == 'deadlines':
                    await channel.delete()
            path = os.getcwd() + '/files/guilds/' + str(ctx.guild.id)
            if os.path.exists(path):
                shutil.rmtree(path)
            query = "DELETE FROM GUILDS WHERE guild_name = ?"
            self.database.modify_value(query, ctx.guild.id)
            query = "DELETE FROM DEADLINES WHERE guild = ?"
            self.database.modify_value(query, ctx.guild.id)
            await ctx.send(':ballot_box_with_check: **All of your traces have been carefully removed...**')
            opts = {
                'meta': {
                    'guild': str(ctx.guild)
                }
            }
            await self.log.info(str(ctx.author) + ' used command RESET', opts)
        elif self.check_setup(ctx) is False:
            await ctx.send(
                ":warning: **You really should complete the setup first before attempting to perform a reset...**")

    @commands.has_role('Bot Controller')
    @commands.command(hidden=True)
    async def force_update(self, ctx):
        """Force a deadline synchronisation"""
        if self.check_setup(ctx) is True:
            await ctx.message.delete()
            async with ctx.typing():
                self.deadlines.download(ctx.guild.id)
                self.deadlines.get(ctx.guild.id)
            await ctx.send(':white_check_mark: **De deadlines zijn geüpdate!**')
            await self.log.info(str(ctx.author) + ' used command FORCE_UPDATE')
        elif self.check_setup(ctx) is False:
            await ctx.send(":negative_squared_cross_mark:  **The setup is not completed. Please check the wiki.**")

    @commands.command()
    async def deadlines(self, ctx):
        """Display the deadlines imported from Moodle"""
        if self.check_setup(ctx) is True:
            await ctx.message.delete()
            embed = self.deadlines.embed(ctx.guild.id)
            await ctx.send(embed=embed)
            await self.log.info(str(ctx.author) + ' used command DEADLINES')
        elif self.check_setup(ctx) is False:
            await ctx.send(":negative_squared_cross_mark:  **The setup is not completed. Please check the wiki.**")

    def send_embed(self, state, description, footer, guild):
        if state == 'passed':
            title = 'Deadline passed!'
            color = 1879160
        else:
            title = 'New Deadline!'
            color = 15605837
        payload = {'embeds': [{
            'title': title,
            'description': description,
            'color': color,
            'footer': {
                'text': footer
            }}]}
        query = "SELECT webhook FROM GUILDS WHERE guild_name = ?"
        webhook = self.database.execute_query(query, guild)
        webhook = webhook[0][0]
        requests.post(webhook, data=json.dumps(payload), headers={'Content-Type': 'multipart/form-data'})

    async def check_warning(self, date, course, content, footer, guild):
        description = '**' + date + ' // ' + course + '** ' + content
        self.send_embed('new', description, footer, guild)
        await self.log.info('New deadline warning: ' + course)

    async def check(self):
        longmonths = [1, 3, 5, 7, 8, 10, 12]
        shortmonths = [4, 6, 9, 11]
        while True:
            now = datetime.datetime.now()
            if int(now.hour) == 12 and int(now.minute) == 0:
                query = "SELECT guild_name FROM GUILDS"
                guilds = self.database.execute_query(query)
                for guild in guilds:
                    guild = str(guild[0])
                    self.deadlines.download(guild)
                    self.deadlines.get(guild)
                    footer = self.deadlines.footer(guild)
                    query_dates = "SELECT date FROM DEADLINES WHERE guild = ?"
                    dates = self.database.execute_query(query_dates, guild)
                    query_courses = "SELECT course FROM DEADLINES WHERE guild = ?"
                    courses = self.database.execute_query(query_courses, guild)
                    query_contents = "SELECT content FROM DEADLINES WHERE guild = ?"
                    contents = self.database.execute_query(query_contents, guild)
                    for i in range(len(dates)):
                        date = dates[i][0]
                        if int(now.day) == 31 and int(date[8:10]) == 2 and int(now.month) in longmonths and int(
                                now.month) + 1 == int(date[5:7]):
                            await self.check_warning(date, courses[i][0], contents[i][0], footer, guild)
                        elif int(now.day) == 30 and int(date[8:10]) == 2 and int(now.month) in shortmonths and int(
                                now.month) + 1 == int(date[5:7]):
                            await self.check_warning(date, courses[i][0], contents[i][0], footer, guild)
                        elif int(now.day) == 30 and int(date[8:10]) == 1 and int(now.month) in longmonths and int(
                                now.month) + 1 == int(date[5:7]):
                            await self.check_warning(date, courses[i][0], contents[i][0], footer, guild)
                        elif int(now.day) == 29 and int(date[8:10]) == 1 and int(now.month) in shortmonths and int(
                                now.month) + 1 == int(date[5:7]):
                            await self.check_warning(date, courses[i][0], contents[i][0], footer, guild)
                        elif int(now.day) == 28 and int(date[8:10]) == 2 and int(now.month) == 3 and int(now.month) \
                                + 1 == int(date[5:7]):
                            await self.check_warning(date, courses[i][0], contents[i][0], footer, guild)
                        elif int(now.day) == 27 and int(date[8:10]) == 1 and int(now.month) == 3 and int(now.month) \
                                + 1 == int(date[5:7]):
                            await self.check_warning(date, courses[i][0], contents[i][0], footer, guild)
                        elif int(now.day) == (int(date[8:10]) - 2) and int(now.month) == int(date[5:7]):
                            await self.check_warning(date, courses[i][0], contents[i][0], footer, guild)
                        elif int(now.day) == int(date[8:10]) and int(now.month) == int(date[5:7]):
                            description = '**' + courses[i][0] + '** ' + contents[i][0]
                            self.send_embed('passed', description, footer, guild)
                            await self.log.info('Deadlines passed: ' + courses[i][0])
            requests.get(config['heartbeat_url'])
            await asyncio.sleep(60)


def setup(bot):
    global handler
    log = AsyncLogger(str(bot.user.name), 'Moodle', bot)
    handler = Logger(str(bot.user.name), 'Moodle', bot)
    db = SqliteDBConnection()
    deadlines = Deadlines(bot, db, log)
    bot.add_cog(Moodle(bot, deadlines, db, log))
