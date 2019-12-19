import requests
import datetime
import os
import json
from PIL import Image, ImageDraw, ImageFont

with open('config.json') as config_file:
    config = json.load(config_file)


class Deadline:
    def __init__(self, date, course, content, opportunity):
        self.date = date
        self.course = course
        self.content = content
        self.opportunity = opportunity


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
        draw.text((2200, 545), message, fill=self.cwhite, font=self.font3)

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
        self.base_url = "https://app.zuydbot.cc/api/v2/"
        self.master_header = {'id': config['master_api']['id'],
                              'secret': config['master_api']['secret']}

    def get_key(self, user_id):
        payload = {'user': str(user_id)}
        r = requests.get(self.base_url + 'master/fetch/key', json=payload, headers=self.master_header)
        key = r.content.decode('utf-8')
        key = json.loads(key)
        return key['key']

    def get_guilds(self):
        guild_list = []
        r = requests.get(self.base_url + 'master/fetch/guilds', headers=self.master_header)
        r = json.loads(r.content.decode('utf-8'))
        guild_json = r['guilds']
        for i in guild_json:
            guild_list.append(Guild(guild_json[i]['name'],
                                    guild_json[i]['webhook_url'],
                                    guild_json[i]['user']))
        return guild_list

    def get_deadlines(self, user_id):
        deadline_list = []
        key = self.get_key(user_id)
        headers = {'key': key}
        r = requests.get(self.base_url + 'deadlines', headers=headers)
        r = json.loads(r.content.decode('utf-8'))
        deadlines = r['deadlines']
        meta = r['meta']
        for deadline in deadlines:
            deadline_list.append(Deadline(deadline['date'],
                                          deadline['course'],
                                          deadline['description'],
                                          deadline['opportunity']))
        return deadline_list, meta

    def get_lessons(self, user_id):
        lesson_list = []
        key = self.get_key(user_id)
        headers = {'key': key}
        r = requests.get(self.base_url + 'lessons', headers=headers)
        r = json.loads(r.content.decode('utf-8'))
        lessons = r['lessons']
        meta = r['meta']
        for lesson in lessons:
            lesson_list.append(Lesson(lesson['start-time'],
                                      lesson['end-time'],
                                      lesson['course'],
                                      lesson['location'],
                                      lesson['teacher']))
        return lesson_list, meta

    def new_guild(self, guild_id, guild_name, webhook_url, user):
        payload = {'id': str(guild_id),
                   'name': str(guild_name),
                   'webhook_url': str(webhook_url),
                   'user': str(user)}
        requests.post(self.base_url + 'master/guild/new', headers=self.master_header, json=payload)

    def remove_guild(self, guild_id):
        payload = {'guild': guild_id}
        requests.post(self.base_url + 'master/guild/remove', headers=self.master_header, json=payload)

    def check_guild(self, guild_id):
        payload = {'guild': guild_id}
        r = requests.get(self.base_url + 'master/guild/check', headers=self.master_header, json=payload)
        r = json.loads(r.content.decode('utf-8'))
        if r['exists'] == 'True':
            return True
        if r['exists'] == 'False':
            return False

    def check_user_moodle(self, user_id):
        payload = {'user': user_id}
        r = requests.get(self.base_url + 'master/user/check', headers=self.master_header, json=payload)
        r = json.loads(r.content.decode('utf-8'))
        if r['user_exists'] == 'True' and r['moodle_exists'] == 'True':
            return True
        if r['user_exists'] == 'False':
            return False

    def check_user_untis(self, user_id):
        payload = {'user': user_id}
        r = requests.get(self.base_url + 'master/user/check', headers=self.master_header, json=payload)
        r = json.loads(r.content.decode('utf-8'))
        if r['user_exists'] == 'True' and r['untis_exists'] == 'True':
            return True
        if r['user_exists'] == 'False':
            return False

    def update_all(self):
        requests.get(self.base_url + 'master/update', headers=self.master_header)
