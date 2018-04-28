import sys
import time
import datetime
import pprint
import asyncio
import motor.motor_asyncio
import re
import matplotlib.pyplot as plt
import numpy as np

from pprint import pprint
from os import path
from wordcloud import WordCloud
from wordcloud import WordCloud, STOPWORDS
from PIL import Image

from config import config

dbapi_string = config['db']
client = motor.motor_asyncio.AsyncIOMotorClient(dbapi_string)
db = client.analytics
stopwords = set(STOPWORDS)
stopwords.update(['fake', 'much', 'good', 'great', 'will', 'should', 'amp', 'now', 'say', 'says', 'said',
                  'new', 'day', 'one', 'well', 'want', 'us', 'today', 'via', 'year', 'need', 'read',
                  'thank', 'news', 'latest'])

def body_cleanup(text):
    URLless_string = re.sub(r'\w+:\/{2}[\d\w-]+(\.[\d\w-]+)*(?:(?:\/[^\s/]*))*', '', text)
    YEARless_string = re.sub(r'\s[1-9][0-9][0-9][0-9]\s', '', URLless_string)
    DIGITless_string = re.sub(r'[0-9]+', '', YEARless_string)
    DIGITless_string = re.sub(r'DIGIT', '', DIGITless_string)
    DIGITless_string = re.sub(r'YEAR', '', DIGITless_string)
    DIGITless_string = re.sub(r'URL', '', DIGITless_string)
    DIGITless_string = re.sub(r'news', '', DIGITless_string)
    DIGITless_string = re.sub(r'News', '', DIGITless_string)
    RTless_string = re.sub('RT @[\w|\s]+:', '', DIGITless_string)
    USERless_string = re.sub('@[\w|\s]+:', '', RTless_string)
    return USERless_string.replace('\n', '')

async def do_find(val1, val2):
    docs = []
    cursor = db.all_tweets.find({'created_at': {'$gt': val1, '$lt': val2}})
    for document in await cursor.to_list(length=50000):
        docs.append(document['text'])
    return docs

if __name__ == '__main__':
    current_time = int(time.time())
    dt = datetime.datetime.fromtimestamp(current_time) - datetime.timedelta(days=1)
    previous_time = int(time.mktime(dt.timetuple()))

    if len(sys.argv) == 3:
        try:
            val1 = int(sys.argv[1])
            val2 = int(sys.argv[2])
        except TypeError:
            val1 = previous_time
            val2 = current_time
    else:
        val1 = previous_time
        val2 = current_time

    loop = asyncio.get_event_loop()
    data = loop.run_until_complete(do_find(val1, val2))
    filtered = [body_cleanup(item).lower() for item in data]
    filtered_unique = list(set(filtered))
    filtered = filtered_unique
    full_text = ' '.join(filtered)
    text = full_text

    # Generate a word cloud image
    d = path.dirname(__file__)
    cloud_mask = np.array(Image.open(path.join(d, "cloud_mask.png")))
    wordcloud = WordCloud(background_color="white", max_words=2000,
                          mask=cloud_mask, stopwords=stopwords)
    try:
        wordcloud.generate(text)

        t = '{0}.{1}'.format(time.strftime("%H:%M:%S_%d.%m.%Y"), 'png')
        wordcloud.to_file(path.join(d, config['img_path'], t))

        items = list(wordcloud.words_.items())

        items = sorted(items, key=lambda item: item[1], reverse=True)
        items = [{'name': x, 'value': y} for x, y in items if y >= config['threshold']]

        for_db = {'time': current_time, 'datapoints': items, 'img': t}
        db.points.insert_one(for_db)
    except ValueError:
        print('It seems the list of words is empty!')
