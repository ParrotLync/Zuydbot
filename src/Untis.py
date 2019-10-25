from PIL import Image, ImageDraw, ImageFont
import os
import datetime
import sqlite3
import requests
from icalendar import Calendar
from discord.ext import commands
import asyncio
import discord
import shutil


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


class Rooster:
    def __init__(self, database):
        self.cwhite = 'rgb(255, 255, 255)'
        self.cgray = 'rgb(127, 131, 132)'
        self.font1 = ImageFont.truetype(os.getcwd() + '/files/cards/bahnschrift.ttf', size=200)
        self.font2 = ImageFont.truetype(os.getcwd() + '/files/cards/bahnschrift.ttf', size=100)
        self.font3 = ImageFont.truetype(os.getcwd() + '/files/cards/SegoeUI.ttf', size=120)
        self.font4 = ImageFont.truetype(os.getcwd() + '/files/cards/SegoeUI.ttf', size=90)
        self.font5 = ImageFont.truetype(os.getcwd() + '/files/cards/bahnschrift.ttf', size=40)
        self.database = database
        self.date = None
        self.time = None

    def get_time(self):
        now = datetime.datetime.now()
        self.date = str(now.day) + '-' + str(now.month) + '-' + str(now.year)
        self.time = str(now.hour) + ':' + format(str(now.minute), '0>2.2')

    def create_image(self, start, end, course, location, teacher, next_start='', next_course='', next_location=''):
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

    def download(self, user):
        query = "SELECT url FROM USERS WHERE username = ?"
        url = self.database.execute_query(query, user)
        r = requests.get(url[0][0])
        self.get_time()
        file = os.getcwd() + '/files/users/' + str(user) + '/icalexport.ics'
        os.makedirs(os.path.dirname(file), exist_ok=True)
        with open(file, 'wb') as cal:
            cal.write(r.content)
        query = "UPDATE USERS SET last_update = ? WHERE username = ?"
        self.database.modify_value(query, self.date, user)

    def get(self, user):
        query = "DELETE FROM TIMETABLE WHERE username = ?"
        self.database.modify_value(query, user)
        try:
            with open(os.getcwd() + '/files/users/' + user + '/icalexport.ics', 'rb') as g:
                gcal = Calendar.from_ical(g.read())
                for component in gcal.walk():
                    if component.name == 'VEVENT':
                        whole_date = component.get('DTSTART')
                        whole_date = str(whole_date.dt)
                        date = whole_date[:10]
                        now = datetime.datetime.now()
                        checkdate = now.date()
                        if str(checkdate) == date:
                            course = str(component.get('SUMMARY').to_ical().decode("utf-8"))
                            location = str(component.get('LOCATION').to_ical().decode("utf-8"))
                            teacher = str(component.get('DESCRIPTION').to_ical().decode("utf-8"))
                            teacher = teacher[-6:]
                            hour = str(int(whole_date[11:13]) + 2)
                            if len(hour) == 2:
                                pass
                            elif '0' not in hour:
                                hour = '0' + hour
                            start_time = hour + ':' + whole_date[14:16]
                            end_time = component.get('DTEND')
                            end_time = str(end_time.dt)
                            hour = str(int(end_time[11:13]) + 2)
                            if len(hour) == 2:
                                pass
                            elif '0' not in hour:
                                hour = '0' + hour
                            end_time = hour + ':' + end_time[14:16]
                            query = "INSERT INTO TIMETABLE (username, start, end, course, location, teacher)" + \
                                    " VALUES(?, ?, ?, ?, ?, ?)"
                            self.database.modify_value(query, user, start_time, end_time, course, location, teacher)
        except FileNotFoundError:
            pass


class Untis(commands.Cog):
    """Untis Integration"""
    def __init__(self, bot, rooster, database):
        self.bot = bot
        self.rooster = rooster
        self.database = database
        self.bot.loop.create_task(self.check())

    def check_setup(self, ctx):
        query = "SELECT username FROM USERS WHERE username = ?"
        result = self.database.execute_query(query, str(ctx.author))
        try:
            if str(result[0][0]) == str(ctx.author):
                return True
        except IndexError:
            return False

    def get_path(self, event, next_event):
        start = event[0]
        end = event[1]
        course = event[2]
        location = event[3]
        teacher = event[4]
        if next_event is not None:
            next_start = next_event[0]
            next_course = next_event[2]
            next_location = next_event[3]
        else:
            next_start = ''
            next_course = ''
            next_location = ''
        path = self.rooster.create_image(start, end, course, location, teacher, next_start, next_course, next_location)
        return path

    @commands.command(hidden=True)
    async def untis(self, ctx, url):
        """Setup the Untis synchronisation"""
        if self.check_setup(ctx) is False:
            query = "INSERT INTO USERS (username, url) VALUES(?, ?)"
            self.database.modify_value(query, str(ctx.author), str(url))
            await ctx.send(':white_check_mark: **Setup completed!**')
            self.rooster.download(str(ctx.author))
            self.rooster.get(str(ctx.author))
        elif self.check_setup(ctx) is True:
            await ctx.send(':negative_squared_cross_mark: **Your setup has already been completed!**')

    @commands.has_role('Bot Controller')
    @commands.command(hidden=True)
    async def untis_update(self, ctx):
        """Force an Untis synchronisation"""
        if self.check_setup(ctx) is True:
            await ctx.message.delete()
            async with ctx.typing():
                self.rooster.download(str(ctx.author))
                self.rooster.get(str(ctx.author))
            await ctx.send(':white_check_mark: **Je rooster is geüpdate!**')
        elif self.check_setup(ctx) is False:
            await ctx.send(":negative_squared_cross_mark:  **Your setup is not completed. Please check the wiki.**")

    @commands.has_role('Bot Controller')
    @commands.command(hidden=True)
    async def untisreset(self, ctx):
        """Reset the deadline synchronisation"""
        if self.check_setup(ctx) is True:
            path = os.getcwd() + '/files/users/' + str(ctx.author)
            if os.path.exists(path):
                shutil.rmtree(path)
            query = "DELETE FROM USERS WHERE username = ?"
            self.database.modify_value(query, str(ctx.author))
            query = "DELETE FROM TIMETABLE WHERE username = ?"
            self.database.modify_value(query, str(ctx.author))
            await ctx.send(':ballot_box_with_check: **All of your traces have been carefully removed...**')
        elif self.check_setup(ctx) is False:
            await ctx.send(
                ":warning: **You really should complete the setup first before attempting to perform a reset...**")

    @commands.command()
    async def lessons(self, ctx):
        """Check your schedule"""
        if self.check_setup(ctx) is False:
            await ctx.send(':negative_squared_cross_mark: **Your setup is not completed for Untis Integration.**')
            await ctx.send('Please use *untis <url> to complete setup.')
        elif self.check_setup(ctx) is True:
            query = "SELECT start, end, course, location, teacher FROM TIMETABLE WHERE username = ?"
            timetable = self.database.execute_query(query, str(ctx.author))
            now = datetime.datetime.now()
            i = 0
            first_found = False
            hours = []
            time = []
            try:
                event = timetable[0]
                for x in timetable:
                    hours.append((x[0], x[1]))
                sorted(hours)
                for x in hours:
                    dt_start = str(now.date()) + ' ' + x[0]
                    dts = datetime.datetime.strptime(dt_start, '%Y-%m-%d %H:%M')
                    dt_end = str(now.date()) + ' ' + x[1]
                    dte = datetime.datetime.strptime(dt_end, '%Y-%m-%d %H:%M')
                    time.append((dts, dte))
                while not first_found:
                    event = timetable[i]
                    if time[i][0] < now:
                        if time[i][1] > now:
                            first_found = True
                            try:
                                next_event = timetable[i + 1]
                            except IndexError:
                                next_event = None
                            path = self.get_path(event, next_event)
                            async with ctx.typing():
                                with open(path, 'rb') as image:
                                    await ctx.send(file=discord.File(image, filename='card.png'))
                                os.remove(path)
                    elif time[i][0] > now:
                        first_found = True
                        try:
                            next_event = timetable[i + 1]
                        except IndexError:
                            next_event = None
                        path = self.get_path(event, next_event)
                        async with ctx.typing():
                            with open(path, 'rb') as image:
                                await ctx.send(file=discord.File(image, filename='card.png'))
                            os.remove(path)
                    i += 1
            except IndexError:
                with open(os.getcwd() + '/files/cards/card_done.png', 'rb') as image:
                    await ctx.send(file=discord.File(image, filename='card.png'))
            except ValueError:
                with open(os.getcwd() + '/files/cards/card_done.png', 'rb') as image:
                    await ctx.send(file=discord.File(image, filename='card.png'))

    async def check(self):
        while True:
            now = datetime.datetime.now()
            if int(now.hour) == 0 and int(now.minute) == 0:
                query = "SELECT username FROM USERS"
                users = self.database.execute_query(query)
                for user in users:
                    user = str(user[0])
                    self.rooster.download(user)
                    self.rooster.get(user)
            await asyncio.sleep(60)


def setup(bot):
    db = SqliteDBConnection()
    rooster = Rooster(db)
    bot.add_cog(Untis(bot, rooster, db))
