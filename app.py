import sys
import configparser
import os
from flask import Flask, render_template, jsonify, url_for, request
from werkzeug.datastructures import ImmutableMultiDict
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from configparser import ConfigParser
import google.generativeai as genai
import mysql.connector
from datetime import datetime, timedelta, time
import random
import json
import tempfile
import requests
from PIL import Image
from urllib.parse import quote
import string
import re
from Ticket_Booking_System import find_nearby_cinemas, get_location_info, query_remaining_seats, generate_remaining_seats
import datetime as dt
import speech_recognition as sr
from pydub import AudioSegment
from tmdbAPI import tmdb_get_movie_box_office, tmdb_get_movie_id, tmdb_get_movie_reviews, tmdb_get_movie_trailer, tmdb_get_recommendations, tmdb_get_watch_providers
from movie_details import analyze_reviews, generate_creative_movie_response

# Azure Text Analytics
from azure.ai.translation.text import TextTranslationClient
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError
from azure.core.credentials import AzureKeyCredential
from azure.ai.textanalytics import TextAnalyticsClient

# Azure Speech
import azure.cognitiveservices.speech as speechsdk
import librosa

# Azure Translator
from azure.ai.translation.text import TextTranslationClient
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError

# Google Generative AI
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

from flask import Flask, request, abort, render_template, url_for
from linebot.v3 import (
    WebhookHandler
)
from linebot.v3.exceptions import (
    InvalidSignatureError
)
# 決定有甚麼格式輸入可以進來
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    LocationMessageContent,
    ImageMessageContent,
    AudioMessageContent
)
# 決定可以輸出甚麼格式
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    MessagingApiBlob,
    ReplyMessageRequest,
    TextMessage,
    AudioMessage,
    FlexMessage,
    FlexContainer
)
import mysql.connector
from google.cloud.sql.connector import Connector
import sqlalchemy

# 獲取當前時間
current_time = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# --------------- Config Parser --------------- #
config = configparser.ConfigParser()
config.read('config.ini')

# Azure Text Analytics Config
credential = AzureKeyCredential(config['AzureLanguage']['API_KEY'])

# Azure Translator Config
text_translator = TextTranslationClient(
    credential=AzureKeyCredential(config["AzureTranslator"]["Key"]),
    endpoint=config["AzureTranslator"]["EndPoint"],
    region=config["AzureTranslator"]["Region"],
)

# Azure Speech Config
speech_config = speechsdk.SpeechConfig(subscription=config['AzureSpeech']['SPEECH_KEY'],
                                       region=config['AzureSpeech']['SPEECH_REGION'])
audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)

# Azure Translator Config
text_translator = TextTranslationClient(
    credential=AzureKeyCredential(config["AzureTranslator"]["Key"]),
    endpoint=config["AzureTranslator"]["EndPoint"],
    region=config["AzureTranslator"]["Region"],
)

# Google Generative AI Config
genai.configure(api_key=config["Gemini"]["API_KEY"])

llm = genai.GenerativeModel(
    "gemini-1.5-flash-latest",
    safety_settings={
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    },
    generation_config={
        "temperature": 1,
        "top_p": 0.95,
        "top_k": 64,
        "max_output_tokens": 8192,
    },
)

# 設定 GOOGLE_APPLICATION_CREDENTIALS
google_credentials = config["GoogleCloud"]["APPLICATION_CREDENTIALS"]
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = google_credentials

movie_source = {}
id_to_name = {}

# 公共時間模組
time_suffix = f"現在時間是 {current_time}"

# 提取情境的實例
scenario_chat = llm.start_chat(history=[])

# 推薦電影的實例
recommendation_chat = llm.start_chat(history=[])

searchkey_chat = llm.start_chat(history=[])

bookingkey_chat = llm.start_chat(history=[])

searchRemainSeats_chat = llm.start_chat(history=[])

recommendORdetails_chat = llm.start_chat(history=[])

recommendORdetails_chat = llm.start_chat(history=[])

movie_title_chat = llm.start_chat(history=[])

# 對應不同的角色設定
role_recommend = """
目前上映的電影有《Avatar》、《Dune》、《To All the Boys I've Loved Before》、《Little Woman》、
《Fresh》、《Before Sunrise》、《Everything Everywhere All at Once》、《Enola Holmes》、
《Call Me By Your Name》和《Princess Mononoke》，
除此之外的電影均為本影廳為上架或已下架的電影，
而你是一位電影嚮導，
請與對話者聊天，依照對話者的性格和情感，逐步的了解他，
如果有給予官方回應資料，請參考提問的問題，然後根據資料內容回答，請記得換行，不要聊其他的，可以更多的追問此電影細節。
若無回應資料，則開啟聊天模式，根據情境，如果對方不知道聊什麼或想請你推薦電影，請推薦一部以上的電影來觀看，並且只能推薦我們有上映的電影。
如果是問某部電影的資訊，不管我們是否有上映均可以回答，請根據電影名稱提供該電影的資訊，包含電影名稱、上映日期、時長、劇情簡介、演員、導演、評分等等，並加以聊天。
不要回答跟電影不相關的問題，禁止出現*。
"""

role_scenario = """你是一個助手，負責從用戶輸入中提取關鍵字並返回對應的情境名稱，有五種情境：Search、Booking、Search_remain_seats、Search_movie_detail、Recommend。
1. Search：用戶查詢電影場次，用戶要提到'場次'才算這個情境。
2. Booking：用戶有提到他想預訂電影。
3. Search_remain_seats：用戶查詢電影剩餘座位。
4. Recommend：用戶想要推薦電影或聊特定電影相關資訊（例如：movie revenue, release date, overview, genres, popularity, poster, runtime, tagline, vote average, watch providers, reviews, trailer,...），
如果不符合Search、Booking、Search_remain_seats條件，一律都算此項情境。
不要回答非以上的情境名稱，也不要有額外回答。
"""
role_scenario += time_suffix

role_searchkey = """
你是抓取關鍵字的ai，能夠將使用者的輸入中所詢問的電影名稱、日期、最近場次等關鍵列點提取出來。
格式如下:
1. movie:紀錄所提及的電影名稱，只有《Avatar》、《Dune》、《To All the Boys I've Loved Before》、《Little Woman》、
《Fresh》、《Before Sunrise》、《Everything Everywhere All at Once》、《Enola Holmes》、
《Call Me By Your Name》和《Princess Mononoke》這幾個選項。
2. date:要查詢的那部電影的日期（如果有具體日期，請格式化為 YYYY-MM-DD，否則為 null)。
3. recent:是否查詢最近場次（如果提到 "最近"，返回 true，否則返回 false）。
4. 如果用戶同時查詢不同電影不同時間的場次，請用一個list包裹多個回復。
返回範例:
[
    {
        "movie": "Avatar",
        "date": "2024-12-12",
        "recent": false
    }
]
當有多個時:
[
    {
        "movie": "Avatar",
        "date": "2024-12-12",
        "recent": false
    },
    {
        "movie": "Dune",
        "date": null,
        "recent": ture
    }
]
"""
role_searchkey += time_suffix

role_bookingkey = """
你是一個智能的訂票助手，專門負責幫助用戶完成電影票的預訂。

1. 如果收到的輸入中有缺失的信息（如電影名稱:需對應到我們有上映的電影、日期、時間、座位數、票種等)。
2. movie:紀錄所提及的電影名稱，只有《Avatar》、《Dune》、《To All the Boys I've Loved Before》、《Little Woman》、
# 《Fresh》、《Before Sunrise》、《Everything Everywhere All at Once》、《Enola Holmes》、
# 《Call Me By Your Name》和《Princess Mononoke》這幾個選項。
3. 當所有必要的信息齊全後，請返回一個 JSON 格式的結構化結果。格式如下：
[
    {
        "movie": "<電影名稱>",
        "date": "<YYYY-MM-DD>",
        "time": "<HH:MM:SS>",
        "seats": <座位數量>,
        "user_name": "<用戶名稱>",
    }
]
5. 去除多餘的文字 (如頭尾的'''以及json字樣)，只回答符合 JSON 格式的結構化結果。
6. 如果有缺失的信息，請使用 '' 代替。
7. date 部分如果沒有提及年份，請使用當前年份(2024)。
"""
role_bookingkey += f"現在時間是{current_time}"

role_recommendORdetails = """你是一個助手，負責從用戶輸入中提取關鍵字並返回對應的情境名稱，有兩種情境：Movie_details_info、Recommendation。
1. Movie_details_info：若用戶有指定詢問特定電影資訊，如：YouTube Trailer, Poster, revenue, 等）屬於此情境。
2. Recommendation：不符合Movie_details_info條件，一律都算此項情境。
不要回答非以上的情境名稱，也不要有額外回答。
"""

role_movie_title = """你是一個助手，負責從用戶輸入中提取關鍵字並返回使用者希望查找的電影名稱。
不要額外回答，只回答使用者想找的特定電影。
"""

role_searchRemainSeats = """
你是一個智能的查詢剩餘座位的助手，專門負責幫助用戶查詢電影的剩餘座位。

1. movie:紀錄所提及的電影名稱，只有《Avatar》、《Dune》、《To All the Boys I've Loved Before》、《Little Woman》、
# 《Fresh》、《Before Sunrise》、《Everything Everywhere All at Once》、《Enola Holmes》、
# 《Call Me By Your Name》和《Princess Mononoke》這幾個選項。
2. 接收到的訊息有電影名稱、日期、時間、戲廳等關鍵字，請將這些關鍵字提取出來。
3. 最少要有電影名稱，其他資訊可以為空。
4. 請返回一個 JSON 格式的結構化結果。格式如下：
[
    {
        "movie": "<電影名稱>",
        "date": "<YYYY-MM-DD>",
        "time": "<HH:MM:SS>",
        "room": "<戲廳名稱>",
    }
]
5. 去除多餘的文字 (如頭尾的'''以及json字樣)，只回答符合 JSON 格式的結構化結果。
6. 如果有缺失的信息，請使用 '' 代替。
7. date 部分如果沒有提及年份，請使用當前年份(2024)。
"""
role_searchRemainSeats += time_suffix

UPLOAD_FOLDER = 'static'

# --------------- Flask & Line Bot --------------- #
app = Flask(__name__, static_folder='static')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

channel_access_token = config['Line']['CHANNEL_ACCESS_TOKEN']
channel_secret = config['Line']['CHANNEL_SECRET']
if channel_secret is None:
    print('Specify LINE_CHANNEL_SECRET as environment variable.')
    sys.exit(1)
if channel_access_token is None:
    print('Specify LINE_CHANNEL_ACCESS_TOKEN as environment variable.')
    sys.exit(1)

handler = WebhookHandler(channel_secret)

configuration = Configuration(
    access_token=channel_access_token
)

# 要連線azure資料庫(需額外下載ssl憑證 有附在資料夾中:DigiCertGlobalRootCA.crt.pem)
# def get_db_connection():
#     conn = mysql.connector.connect(
#         host="access-for-sql.mysql.database.azure.com",
#         user="guest",
#         password="MYSQLmysql/",
#         database="movie_db",
#         ssl_ca=r"C:\Users\ll092\Downloads\DigiCertGlobalRootCA.crt.pem" #需更改為自己放置的檔案路徑
#     )
#     return conn

# IGNORE_START
# 要連線自己本機的mysql資料庫 帳號密碼請自己改


# def get_db_connection():
#    conn = mysql.connector.connect(
#        host="localhost",
#        user="s1101549",
#        password="s1101549",
#        database="movie_db",
#        charset="utf8mb4"  # 確保使用 utf8mb4 編碼
#    )
#    return conn

#

connector = Connector()


def getconn():
    return connector.connect(
        "winter-arena-443413-i7:asia-east1:showtime-1",  # 替换为您的实例连接名称
        "pymysql",  # 指定连接器类型
        user="root",  # 数据库用户名
        password="showtime-1",  # 直接填写密码
        db="movie_db",  # 数据库名称
    )


pool = sqlalchemy.create_engine(
    "mysql+pymysql://",  # 使用 pymysql
    creator=getconn,  # 指定连接创建器
)


def get_db_connection():
    # 返回一个 sqlalchemy 连接对象
    return pool.connect()

# IGNORE_END


# 返回字典格式的結果
@app.route('/api/moviesource', methods=['GET'])
def get_moviesource():
    conn = get_db_connection()
    result = conn.execute(
        sqlalchemy.text("SELECT id, name, src, duration AS time FROM movies")
    )
    movies = [dict(row._mapping) for row in result.fetchall()]
    # cursor = conn.cursor(dictionary=True)
    # cursor.execute("SELECT id, name, src, duration AS time FROM movies")
    # movies = cursor.fetchall()
    conn.close()
    return jsonify(movies)

# 清理過期場次


def clean_up_showtimes():
    conn = get_db_connection()
    # cursor = conn.cursor()
    current_time = datetime.now()
    conn.execute(
        sqlalchemy.text("""
                DELETE FROM showtimes
                WHERE show_date < :cutoff_date OR (show_date = :current_date AND show_time < :current_time)
            """),
        {
            "cutoff_date": current_time.date(),
            "current_date": current_time.date(),
            "current_time": current_time.time()
        }
    )
    # cursor.execute("""
    #    DELETE FROM showtimes
    #    WHERE show_date < %s OR (show_date = %s AND show_time < %s)
    # """, (current_time.date(), current_time.date(), current_time.time()))
    conn.commit()
    conn.close()

# 随机生成每天的第一场次时间


def get_random_initial_time(show_date):
    random_hour = random.randint(9, 12)
    random_minute = random.choice([0, 15, 30, 45])
    initial_time = datetime.combine(show_date, datetime.min.time(
    )) + timedelta(hours=random_hour, minutes=random_minute)
    return initial_time

# 生成一周内的场次


def generate_showtimes():
    conn = get_db_connection()
    result = conn.execute(sqlalchemy.text(
        "SELECT id, name, duration FROM movies"))
    movies = [dict(row._mapping) for row in result.fetchall()]
    # cursor = conn.cursor(dictionary=True)

    # 获取所有电影及其时长
    # cursor.execute("SELECT id, name, duration FROM movies")
    # movies = cursor.fetchall()

    # 获取当前日期
    today = datetime.now().date()

    # 每个放映厅的名称
    all_rooms = ["A廳", "B廳", "C廳", "D廳", "E廳", "F廳", "G廳"]

    # 遍历每部电影生成场次
    for movie in movies:
        movie_id = movie['id']
        movie_name = movie['name']
        movie_duration = movie['duration']

        for day in range(7):  # 为未来7天生成场次
            show_date = today + timedelta(days=day)

            # 检查当天是否已有数据
            # cursor.execute("""
            #    SELECT COUNT(*) AS count FROM showtimes
            #    WHERE movie_id = %s AND show_date = %s
            # """, (movie_id, show_date))
            # result = cursor.fetchone()
            result = conn.execute(
                sqlalchemy.text("""
                        SELECT COUNT(*) AS count FROM showtimes
                        WHERE movie_id = :movie_id AND show_date = :show_date
                    """),
                {"movie_id": movie_id, "show_date": show_date}
            )
            # count = result.fetchone()['count']
            count = result.fetchone()._mapping['count']

            if count > 0:
                print(f"跳过生成：电影 '{movie_name}' {show_date} 已有场次数据")
                continue  # 如果已有数据，则跳过当天

            # 随机生成这部电影当天的放映厅数量（1到3个厅）
            total_rooms = random.randint(1, 3)
            # 随机从可用的放映厅中选择不重复的厅
            selected_rooms = random.sample(all_rooms, total_rooms)

            # 为每个选定的厅生成场次
            room_schedule = {room: [] for room in selected_rooms}  # 每个放映厅初始化为空

            for room in room_schedule:
                target_show_count = random.randint(1, 5)  # 每个厅最多生成3-5场

                # 如果当前厅没有任何场次，生成第一场次
                if not room_schedule[room]:
                    initial_time = get_random_initial_time(show_date)
                    room_schedule[room].append(initial_time)

                # 如果已有场次，生成下一场
                while len(room_schedule[room]) < target_show_count:
                    last_show_time = room_schedule[room][-1]  # 获取最后一场的时间
                    # 随机生成下一场间隔（30 到 60 分钟）
                    random_interval = random.randint(30, 60)
                    next_show_time = last_show_time + \
                        timedelta(minutes=movie_duration + random_interval)

                    # 如果下一场时间超过当天的最后时间，停止生成
                    if next_show_time.time() > time(23, 59):
                        break

                    # 如果下一场时间有效，添加到日程表
                    room_schedule[room].append(next_show_time)

                # 插入该厅的所有场次
                for show_time in room_schedule[room]:
                    conn.execute(
                        sqlalchemy.text("""
                        INSERT INTO showtimes (movie_id, show_date, show_time, room)
                        VALUES (:movie_id, :show_date, :show_time, :room)
                    """),
                        {"movie_id": movie_id, "show_date": show_date,
                         "show_time": show_time.time(), "room": room})
                    # cursor.execute("""
                    #    INSERT INTO showtimes (movie_id, show_date, show_time, room)
                    #    VALUES (%s, %s, %s, %s)
                    # """, (movie_id, show_date, show_time.time(), room))

    conn.commit()
    conn.close()


def parse_response_text(text):
    """
    將返回的 text 轉換為結構化的 JSON。
    """
    try:
        # 嘗試直接將文本解析為 JSON
        result = json.loads(text)
        print("Parsed JSON successfully:", result)
        return result
    except json.JSONDecodeError:
        print("Text is not valid JSON, trying regex...")
    # 提取 JSON 區域
    json_part = re.search(r'\[.*?\]', text, re.DOTALL)
    if not json_part:
        print("No JSON-like content found")
        return None

    # 匹配電影資料
    matches = re.findall(
        r'"movie":\s*"(.*?)",\s*"date":\s*(null|"[\d-]+"),\s*"recent":\s*(true|false)',
        json_part.group(0)
    )

    # 將結果轉換為結構化資料
    result = []
    for match in matches:
        result.append({
            "movie": match[0],
            "date": None if match[1] == "null" else match[1].strip('"'),
            "recent": match[2].lower() == "true"
        })

    return result


def parse_response_text_for_remaining_seat(text):
    """
    將返回的 text 轉換為結構化的 JSON。
    """
    try:
        # 嘗試直接將文本解析為 JSON
        result = json.loads(text)
        print("Parsed JSON successfully:", result)
        return result
    except json.JSONDecodeError:
        print("Text is not valid JSON, trying regex...")
    # 提取 JSON 區域
    json_part = re.search(r'\[.*?\]', text, re.DOTALL)
    if not json_part:
        print("No JSON-like content found")
        return None

    # 匹配電影資料
    matches = re.findall(
        r'"movie":\s*"(.*?)",\s*"date":\s*(null|""|"[\d-]+"),\s*"time":\s*(null|""|"[\d:]+"),\s*"room":\s*"(.*?)"',
        json_part.group(0)
    )

    # 將結果轉換為結構化資料
    result = []
    for match in matches:
        result.append({
            "movie": match[0],
            "date": None if match[1] == "null" else match[1].strip('"'),
            "time": None if match[2] == "null" else match[2].strip('"'),
            "room": match[3]
        })

    return result


def fetch_movie_source():
    global movie_source, id_to_name
    conn = get_db_connection()
    # cursor = conn.cursor(dictionary=True)
    # cursor.execute("SELECT id, name, src, duration AS time FROM movies")
    # movies = cursor.fetchall()  # 获取查询结果
    result = conn.execute(
        sqlalchemy.text("SELECT id, name, src, duration AS time FROM movies")
    )
    movies = [dict(row._mapping) for row in result.fetchall()]
    conn.close()

    # 将数据封装成字典，以电影名称为键
    movie_source = {movie['name']: movie for movie in movies}
    id_to_name = {movie['id']: movie['name'] for movie in movies}
    print("Loaded movie_source:", movie_source)


def get_movie_id(movie_name):
    global movie_source  # 声明使用全局变量
    if not movie_source:  # 如果 movie_source 为空
        fetch_movie_source()
    if movie_name in movie_source:
        return movie_source[movie_name]['id']  # 使用字典键访问 id
    else:
        return None  # 如果电影名称不存在，返回 None


def format_showtimes(showtimes):
    global id_to_name
    formatted_result = []
    for show in showtimes:
        # 转换 show_time
        if isinstance(show["show_time"], timedelta):
            # 将 timedelta 转换为 "HH:MM" 格式
            total_seconds = int(show["show_time"].total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            show_time_str = f"{hours:02}:{minutes:02}"
        else:
            # 如果是 datetime.time 类型，直接格式化
            show_time_str = show["show_time"].strftime("%H:%M:%S")
        id = show["movie_id"]
        movie_name = id_to_name[id]
        # 构建格式化后的字典
        formatted_result.append({
            "movie_name": movie_name,
            "show_date": show["show_date"].strftime("%Y-%m-%d"),
            "show_time": show_time_str,
            "room": show["room"]
        })

    # 返回格式化后的 JSON 字符串
    return formatted_result


def generate_random_username(length=8):
    # 使用字母和數字生成隨機名稱
    characters = string.ascii_letters + string.digits
    username = ''.join(random.choice(characters) for _ in range(length))
    return username


def get_showtime(movie_id, date, recent):
    conn = get_db_connection()
    # cursor = conn.cursor(dictionary=True)
    if date is None and recent:
        # 如果日期为空且 recent 为真，返回最近的场次
        # cursor.execute(
        #    "SELECT * FROM showtimes WHERE movie_id=%s AND show_date >= CURDATE() ORDER BY show_date, show_time LIMIT 3", (movie_id,))
        result = conn.execute(
            sqlalchemy.text(
                """SELECT * FROM showtimes WHERE movie_id=:movie_id AND show_date >= CURDATE() ORDER BY show_date, show_time LIMIT 3"""),
            {"movie_id": movie_id}
        )
    else:
        # cursor.execute(
        #    "SELECT * FROM showtimes WHERE movie_id=%s AND show_date=%s", (movie_id, date))
        result = conn.execute(
            sqlalchemy.text(
                """SELECT * FROM showtimes WHERE movie_id=:movie_id AND show_date=:date"""),
            {"movie_id": movie_id, "date": date}
        )
    showtimes = [dict(row._mapping) for row in result.fetchall()]
    conn.close()
    return format_showtimes(showtimes)


def ask_more_information(field_name):
    prompts = {
        "movie": "請問您想訂哪一部電影？",
        "date": "請問您想訂哪一天的票？請提供日期（格式：YYYY-MM-DD）。",
        "time": "請問您想訂哪個場次？請提供時間（格式：HH:MM:SS）。",
        "seats": "請問您需要多少個座位？",
    }
    return prompts.get(field_name, "缺少必要信息，請提供。")

# new for booking


def parse_response_text_forBooking(text):
    """
    將返回的 text 轉換為結構化的 JSON。
    """
    try:
        # 嘗試直接將文本解析為 JSON
        result = json.loads(text)
        print("Parsed JSON successfully:", result)
        return result
    except json.JSONDecodeError:
        print("Text is not valid JSON, trying regex...")
    # 提取 JSON 區域
    json_part = re.search(r'\[.*?\]', text, re.DOTALL)
    if not json_part:
        print("No JSON-like content found")
        return None

    print(json_part.group(0))

    # 匹配電影資料
    matches = re.findall(
        r'"movie":\s*(?:"(.*?)"|null),\s*"date":\s*(?:"([\d-]+)"|null),\s*"time":\s*(?:"(.*?)"|null),\s*"seats":\s*(?:(\d+)|null|""),\s*"user_name":\s*(?:"(.*?)"|null|"")',
        json_part.group(0)
    )

    if not matches:
        print("No matches found in the JSON content")
        return None

    # 將結果轉換為結構化資料
    result = []
    for match in matches:
        result.append({
            "movie": None if match[0] in (None, "null", "") else match[0],
            "date": None if match[1] in (None, "null", "") else match[1].strip('"'),
            "time": None if match[2] in (None, "null", "") else match[2],
            "seats":  None if match[3] in (None, "null", "") else int(match[3]),
            "user_name": generate_random_username() if match[4] in (None, "null", "") else match[4],
        })

    return result

# new for booking


def book_tickets(movie_id, user_name, reservation_date, reservation_time, seats):
    conn = get_db_connection()
    # cursor = conn.cursor(dictionary=True)

    try:
        # Step 1: 查詢場次資訊
        # cursor.execute(
        #    "SELECT * FROM showtimes WHERE movie_id = %s AND show_date = %s AND show_time = %s",
        #    (movie_id, reservation_date, reservation_time)
        # )
        # showtime = cursor.fetchone()
        result = conn.execute(
            sqlalchemy.text("""
        SELECT * FROM showtimes WHERE movie_id = :movie_id AND show_date = :date AND show_time = :time
        """),
            {"movie_id": movie_id, "date": reservation_date, "time": reservation_time}
        )
        showtime = result.fetchone()

        if not showtime:
            return {"error": "指定的場次不存在！"}

        # 假設每個場次初始座位數為 100，這裡可以根據實際需求修改。
        max_seats = 32
        # 計算已預訂座位數
        # cursor.execute(
        #    """
        #    SELECT COALESCE(SUM(LENGTH(seats) - LENGTH(REPLACE(seats, ',', '')) + 1), 0) AS reserved_seats
        #    FROM reservations
        #    WHERE movie_id = %s AND reservation_date = %s AND reservation_time = %s""",
        #    (movie_id, reservation_date, reservation_time)
        # )
        # result = cursor.fetchone()
        result = conn.execute(
            sqlalchemy.text("""
        SELECT COALESCE(SUM(LENGTH(seats) - LENGTH(REPLACE(seats, ',', '')) + 1), 0) AS reserved_seats 
            FROM reservations 
            WHERE movie_id =:movie_id AND reservation_date = :date AND reservation_time = :time
        """),
            {"movie_id": movie_id, "date": reservation_date, "time": reservation_time}
        )
        result_s = result.fetchone()

        reserved_seats = int(result_s["reserved_seats"])
        print(f"Reserved seats: {reserved_seats}")
        # reserved_seats = int(result["reserved_seats"]) if result["reserved_seats"] else 0
        available_seats = max_seats - reserved_seats

        seats = int(seats)  # 確保 seats 是整數
        seats_list = [str(i) for i in range(1, seats + 1)]  # 生成座位號列表
        if seats > available_seats:
            return {"error": f"場次剩餘座位不足，目前剩餘：{available_seats} 個座位。"}

        # Step 2: 插入到 reservations 表
        # cursor.execute(
        #    "INSERT INTO reservations (movie_id, user_name, reservation_date, reservation_time, seats, tickets) VALUES (%s, %s, %s, %s, %s, %s)",
        #    (movie_id, user_name, reservation_date,
        #     reservation_time,  ",".join(seats_list), seats)
        # )
        conn.execute(
            sqlalchemy.text("""
        INSERT INTO reservations (movie_id, user_name, reservation_date, reservation_time, seats, tickets)
        VALUES (:movie_id, :user_name, :reservation_date, :reservation_time, :seats, :tickets)
        """),
            {
                "movie_id": movie_id,
                "user_name": user_name,
                "reservation_date": reservation_date,
                "reservation_time": reservation_time,
                "seats": ",".join(seats_list),
                "tickets": seats
            }
        )

        # 提交事務
        conn.commit()
        conn.close()
        return {"success": "訂票成功！"}

    except Exception as e:
        conn.rollback()  # 發生錯誤時回滾
        return {"error": f"訂票失敗：{e}"}

    finally:
        conn.close()


@app.route("/api/movie/<int:movie_id>/showtimes", methods=["GET"])
def get_movie_showtimes(movie_id):
    conn = get_db_connection()
    # cursor = conn.cursor(dictionary=True)

    # 获取请求中的日期参数
    date_param = request.args.get("date", None)
    if date_param is None:
        date = datetime.now().date()
    else:
        try:
            date = datetime.strptime(date_param, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"error": "Invalid date format, expected YYYY-MM-DD"}), 400

    print(f"Received date_param: {date_param}")

    # cursor.execute("""
    # SELECT show_date, show_time, room
    # FROM showtimes
    # WHERE movie_id = %s AND show_date = %s
    # ORDER BY show_time
    # """, (movie_id, date))
    # showtimes = cursor.fetchall()
    result = conn.execute(
        sqlalchemy.text("""
        SELECT show_date, show_time, room
        FROM showtimes
        WHERE movie_id = :movie_id AND show_date = :date
        ORDER BY show_time
        """),
        {"movie_id": movie_id, "date": date}
    )
    showtimes = [dict(row._mapping) for row in result.fetchall()]
    print(f"Querying showtimes for movie_id: {movie_id}, date: {date}")

    conn.close()
    grouped_showtimes = {}
    for show in showtimes:
        room = show["room"]
        if room not in grouped_showtimes:
            grouped_showtimes[room] = []

        # 解析 show_time
        if isinstance(show["show_time"], str):
            # 如果是字符串，解析为时间对象
            show_time = datetime.strptime(show["show_time"], "%H:%M:%S").time()
        elif isinstance(show["show_time"], timedelta):
            # 如果是 timedelta，手动计算小时和分钟
            total_seconds = show["show_time"].total_seconds()
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            show_time = f"{hours:02}:{minutes:02}"
        else:
            # 如果是时间对象，直接使用
            show_time = show["show_time"].strftime("%H:%M")

        grouped_showtimes[room].append(show_time)

    return jsonify({
        "movie_id": movie_id,
        "date": str(date),
        "showtimes": grouped_showtimes
    })


@app.route('/reservation/api', methods=['POST'])
def create_reservation():
    data = request.json
    # 打印接收到的 JSON 数据
    print("Received data:", data)
    conn = get_db_connection()
    # cursor = conn.cursor()

    # 將 seat 列表轉換為逗號分隔的字符串
    seats = ",".join(data['seat']) if isinstance(
        data['seat'], list) else data['seat']

    # 插入數據到資料庫
    # cursor.execute(
    #    "INSERT INTO reservations (movie_id, user_name, reservation_date, reservation_time, seats, tickets) "
    #    "VALUES (%s, %s, %s, %s, %s, %s)",
    #    (data['movie_id'], data['user_name'],
    #     data['date'], data['time'], seats, data['ticket'])
    # )
    conn.execute(
        sqlalchemy.text("""
        INSERT INTO reservations (movie_id, user_name, reservation_date, reservation_time, seats, tickets)
        VALUES (:movie_id, :user_name, :reservation_date, :reservation_time, :seats, :tickets)
        """),
        {
            "movie_id": data['movie_id'],
            "user_name": data['user_name'],
            "reservation_date": data['date'],
            "reservation_time": data['time'],
            "seats": seats,
            "tickets": data['ticket']
        }
    )
    conn.commit()
    conn.close()
    try:
        response = requests.post(
            "https://asia-east1-winter-arena-443413-i7.cloudfunctions.net/send-email",
            json={"reservation_data": data}  # 您可以調整這裡的 payload
        )
        print("Email service response:", response.status_code, response.text)
    except requests.exceptions.RequestException as e:
        print("Failed to call email service:", e)
    return jsonify({"success": True})  # 返回成功響應


@app.route('/reservation/api', methods=['GET'])
def get_reservations():
    # 打印所有请求参数
    print("Received args:", request.args)

    # 获取参数
    user_name = request.args.get('user_name')
    movie_id = request.args.get('movie_id')
    date = request.args.get('reservation_date')
    time = request.args.get('reservation_time')

    # 参数校验
    if not (user_name or (movie_id and date and time)):
        return jsonify({"error": "Missing required parameters"}), 400

    try:
        conn = get_db_connection()
        # cursor = conn.cursor(dictionary=True)

        # 动态构造查询语句
        query = "SELECT * FROM reservations WHERE 1=1"
        params = {}

        if user_name:
            query += " AND user_name = :user_name"
            params["user_name"] = user_name
        if movie_id:
            query += " AND movie_id = :movie_id"
            params["movie_id"] = movie_id
        if date:
            query += " AND reservation_date = :reservation_date"
            params["reservation_date"] = date
        if time:
            query += " AND reservation_time = :reservation_time"
            params["reservation_time"] = time

        # 打印查询语句和参数
        print("SQL Query:", query)
        print("Parameters:", params)

        # 执行查询
        # cursor.execute(query, params)
        # reservations = cursor.fetchall()
        result = conn.execute(sqlalchemy.text(query), params)
        reservations = [dict(row._mapping) for row in result.fetchall()]

        # 对 timedelta 类型数据进行处理
        for reservation in reservations:
            if isinstance(reservation.get('reservation_time'), timedelta):
                # 将 timedelta 转换为字符串格式（如 'HH:MM:SS'）
                total_seconds = int(
                    reservation['reservation_time'].total_seconds())
                hours, remainder = divmod(total_seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                reservation['reservation_time'] = f"{hours:02}:{minutes:02}:{seconds:02}"

        conn.close()
        return jsonify(reservations)
    except Exception as e:
        print("Error:", e)  # 打印错误信息
        return jsonify({"error": str(e)}), 500


@app.route('/reservation/api', methods=['DELETE'])
def delete_reservation():
    # 获取查询参数中的 reservationId
    reservation_id = request.args.get("id")

    # 如果 reservationId 缺失，返回错误
    if not reservation_id:
        return jsonify({"error": "Missing reservation ID"}), 400

    # 解析请求体中的 JSON 数据
    data = request.get_json()
    reason = data.get("reason") if data else None  # 获取删除原因（可选）

    try:
        conn = get_db_connection()
        # cursor = conn.cursor()

        # 执行删除操作
        # cursor.execute("DELETE FROM reservations WHERE id = %s",
        #               (reservation_id,))
        result = conn.execute(
            sqlalchemy.text(
                "DELETE FROM reservations WHERE id = :reservation_id"),
            {"reservation_id": reservation_id}
        )
        conn.commit()

        # 检查是否真的删除了记录
        if result.rowcount == 0:
            return jsonify({"error": "Reservation not found"}), 404

        # 可选：记录删除原因到日志或数据库（如有需要）
        if reason:
            print(f"Reservation {reservation_id} deleted. Reason: {reason}")

        conn.close()
        return jsonify({"success": True, "deleted_id": reservation_id}), 200
    except Exception as e:
        print("Error:", e)  # 打印错误日志
        return jsonify({"error": str(e)}), 500


@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']
    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # parse webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/reservation")
def reservation():
    return render_template("reservation.html")


@app.route("/gemini")
def gemini():
    return render_template("gemini.html")


book_state = False
reservation_json_history = ""


@app.route("/call_llm", methods=["POST"])
def call_llm(input_data=None, lineBot=False):
    print("################ call_llm ################")
    if request.method == "POST":
        global book_state
        data = request.form
        if lineBot:
            data = ImmutableMultiDict([('message', input_data)])
        print("data:", data)
        to_keyword = ""
        if len(scenario_chat.history) > 0:
            to_keyword = data["message"]
        else:
            to_keyword = role_scenario + data["message"]

        try:
            result = scenario_chat.send_message(to_keyword)
        except Exception as e:
            print(e)
            return "這不是我能回答的"
        scenario = result.text.replace("\n", "")
        print("Scenario: ", scenario)
        # -----------------Search-------------------#
        if scenario == "Search" and book_state == False:
            if len(searchkey_chat.history) > 0:
                to_se = data["message"]
            else:
                to_se = role_searchkey + data["message"]
            try:
                result = searchkey_chat.send_message(to_se)
            except Exception as e:
                print(e)
                return "這不是我能回答的"
            text_json = result.text.replace("\n", "")
            real_json = parse_response_text(text_json)
            print(real_json)

            # 開始正式查詢
            all_result = []
            for i in real_json:
                movie_name = i["movie"]
                print(movie_name)
                id = get_movie_id(movie_name)
                result = get_showtime(id, i["date"], i["recent"])
                all_result.append(result)
            if len(recommendation_chat.history) > 0:
                to_re = "提出的問題:"+data["message"]+"，官方回應資料:"+str(all_result)
            else:
                to_re = role_recommend + "，提出的問題:" + \
                    data["message"]+"，官方回應資料:"+str(all_result)

            try:
                result = recommendation_chat.send_message(to_re)
            except Exception as e:
                print(e)
                return "這不是我能回答的"

            # -----------------booking-------------------#
        elif scenario == "Booking" or book_state == True:
            global reservation_json_history
            if book_state == False:
                book_state = True
            # Step 1: 確定輸入訊息
            if len(bookingkey_chat.history) > 0:
                to_se = data["message"]+str(reservation_json_history)
            else:

                to_se = role_bookingkey + \
                    data["message"]+str(reservation_json_history)

            try:
                # 解析用戶輸入，提取訂票需求
                result = bookingkey_chat.send_message(to_se)
            except Exception as e:
                print(e)
                return "這不是我能回答的"

            # 將返回的文字轉為結構化資料
            text_json = result.text.replace("\n", "")
            booking_request = parse_response_text_forBooking(text_json)
            print("解析的訂票需求：", booking_request)

            if booking_request:
                reservation_json_history = booking_request

            # Step 2: 檢測是否有缺失字段
            for i in booking_request:
                missing_fields = []
                if not i.get("movie"):
                    missing_fields.append("movie")
                if not i.get("date"):
                    missing_fields.append("date")
                if not i.get("time"):
                    missing_fields.append("time")
                if not i.get("seats"):
                    missing_fields.append("seats")

                if missing_fields:
                    # 生成提示並返回給用戶
                    prompts = {
                        "movie": "請問您想訂哪一部電影？",
                        "date": "想要看哪一天的呢？",
                        "time": "想訂幾點的呢？",
                        "seats": "請問您需要多少個座位？"
                    }
                    missing_prompt = [prompts[field]
                                      for field in missing_fields]
                    return "\n".join(missing_prompt), False

            # Step 2: 確認訂票資訊
            all_result = []
            for i in booking_request:
                movie_name = i["movie"]
                date = i["date"]
                time = i["time"]  # 場次時間
                seats = i["seats"] if "seats" in i else "1"  # 預設 1 個座位
                user_name = i["user_name"] if "user_name" in i else "None"
                if date == None or time == None or movie_name == None or seats == None:
                    all_result.append({"error": "缺少必要參數"})
                    continue

                # 查詢電影 ID
                movie_id = get_movie_id(movie_name)
                if not movie_id:
                    all_result.append({"error": f"找不到電影：{movie_name}"})
                    print(f"找不到電影：{movie_name}")
                    continue
                print(f"電影 ID: {movie_id}")

                # Step 3: 訂票邏輯
                booking_result = book_tickets(
                    movie_id=movie_id,
                    user_name=user_name,
                    reservation_date=date,
                    reservation_time=time,
                    seats=seats,
                )
                book_state = False
                reservation_json_history.clear()
                all_result.append(booking_result)

            # Step 4: 回傳結果
            if booking_result.get("success"):
                generate_remaining_seats()
                return "訂票成功！\n你的訂票查詢ID為：" + user_name, False
            else:
                print("訂票失敗：", booking_result.get("error"))
                return "很抱歉，系統出現錯誤，訂票失敗！", False

            # -----------------Recommend-------------------#
        elif scenario == "Recommend" and book_state == False:
            to_analyze = role_recommendORdetails + \
                f"User input: {data['message']}"
            try:
                recommendORdetails = recommendORdetails_chat.send_message(
                    to_analyze)
                print("recommendORdetails: ", recommendORdetails.text)
            except Exception as e:
                print(e)
                return "Error: I can't answer this question."

            check = recommendORdetails.text.replace("\n", "")
            print("check: ", check)
            if check == "Recommendation":

                to_re = role_recommend + "User input: " + data["message"]

                try:
                    result = recommendation_chat.send_message(to_re)
                    reply = result.text.replace("\n", "")
                    return reply, False
                except Exception as e:
                    print(e)
                    return "Error: I can't answer this question."
            else:
                toGetTitle = role_movie_title + \
                    f"User input: {data['message']}"
                try:
                    movie_title = movie_title_chat.send_message(toGetTitle)
                except Exception as e:
                    print(e)
                    return "Error: I can't answer this question."
                movieName = movie_title.text.replace("\n", "")
                response = message_movie_detail(movieName)

                # print(movieName)
                # print(f"Response: {response}")
                return response, True
        elif scenario == "Search_remain_seats" and book_state == False:
            if len(searchRemainSeats_chat.history) > 0:
                to_se = data["message"]
            else:
                to_se = role_searchRemainSeats + data["message"]
            try:
                result = searchRemainSeats_chat.send_message(to_se)
            except Exception as e:
                print(e)
                return "這不是我能回答的"
            text_json = result.text.replace("\n", "")
            real_json = parse_response_text_for_remaining_seat(text_json)
            print(real_json)

            result = query_remaining_seats(
                real_json[0]["movie"], real_json[0]["date"], real_json[0]["time"], real_json[0]["room"])
            return result

        return result.text.replace("\n", ""), False


# ----------------- Initailize SQL ----------------- #
clean_up_showtimes()
generate_showtimes()
generate_remaining_seats()

# ----------------- add transtale function to Chatbot ----------------- #


def process_audio_to_text(audio_content, file_path):
    """將音訊轉換為文字的邏輯"""
    # 將音訊儲存為 .m4a 檔案
    with open(file_path, 'wb') as fd:
        fd.write(audio_content)

    # 進行語音轉文字處理
    r = sr.Recognizer()
    # 輸入自己的ffmpeg.exe路徑
    AudioSegment.converter = r"C:\Users\ll092\Downloads\ffmpeg-7.1-full_build\bin\ffmpeg.exe"
    sound = AudioSegment.from_file_using_temporary_files(file_path)

    # 將音訊轉換為 .wav 格式
    wav_path = os.path.splitext(file_path)[0] + '.wav'
    sound.export(wav_path, format="wav")

    # 使用語音識別
    with sr.AudioFile(wav_path) as source:
        audio = r.record(source)
    text = r.recognize_google(audio, language='zh-Hant')  # 設定語言為中文

    return text


def azure_translate(user_input):
    try:  # 偵測使用者輸入的語言，儲存起來
        # 設定目標語言
        target_languages = [detect_language(user_input)]  # 支援簡體中文和英文的回覆
        input_text_elements = [user_input]

        # 翻譯後的結果
        response = text_translator.translate(
            body=input_text_elements, to_language=["zh-Hant"]
        )

        translation = response[0] if response else None
        result = translation.translations[0].text
        print('\n', result, '\n')
        return result

    except HttpResponseError as exception:
        if exception.error is not None:
            print(f"Error Code: {exception.error.code}")
            print(f"Message: {exception.error.message}")
        raise

    except Exception as exception:
        print(f"Error: {exception}")
        raise


def azure_translate_to(text, target_language):
    if target_language == 'zh-Hans':
        target_language = 'zh-Hant'
    try:
        response = text_translator.translate(
            body=[text], to_language=[target_language]
        )
        if response and response[0].translations:
            return response[0].translations[0].text
        else:
            return text

    except Exception as e:
        print(f"Error in azure_translate_to: {e}")
        return text


def detect_language(user_input):
    try:
        # 使用 Azure 翻譯服務偵測語言
        input_text_elements = [user_input]
        response = text_translator.translate(
            body=input_text_elements, to_language=["en"]  # 偵測語言不需要實際翻譯
        )

        if response and response[0].detected_language.language:
            return response[0].detected_language.language  # 回傳語言代碼
        else:
            return "unknown"

    except HttpResponseError as exception:
        print(f"Error Code: {exception.error.code}")
        print(f"Message: {exception.error.message}")
        return "error"

    except Exception as exception:
        print(f"Error: {exception}")
        return "error"

# --------------- Handle Text Message --------------- #


@handler.add(MessageEvent, message=TextMessageContent)
def message_text(event):
    text = event.message.text
    user_id = event.source.user_id
    global user_language  # 儲存使用者語言的全域變數
    print(f"Received text: {text}")
    # 使用 Azure 翻譯服務檢測語言並翻譯文字
    translated_text = azure_translate(text)
    language_code = detect_language(text)
    user_language = language_code  # 儲存使用者語言
    print(
        f"Translated text: {translated_text}, Detected language code: {language_code}")
    result, remaining_seat = call_llm(translated_text, True)
    if result == None:
        print("No response from LLM")
    print(f"Response: {result}")
    # 翻譯用戶的語言
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        if remaining_seat:
            message = FlexMessage(
                alt_text="hello", contents=FlexContainer.from_json(result))
            # 使用 push_message 正確提供 'to' 和 'messages'
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[message]
                )
            )
        else:  # 需要修改
            if user_language != "zh-Hant":
                result = azure_translate_to(result, user_language)
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        TextMessage(text=result)
                    ]
                )
            )


@handler.add(MessageEvent, message=ImageMessageContent)
def message_image(event):

    with ApiClient(configuration) as api_client:
        line_bot_blob_api = MessagingApiBlob(api_client)
        message_content = line_bot_blob_api.get_message_content(
            message_id=event.message.id
        )
        with tempfile.NamedTemporaryFile(
            dir=UPLOAD_FOLDER, prefix="", delete=False
        ) as tf:
            tf.write(message_content)
            tempfile_path = tf.name

    original_file_name = os.path.basename(tempfile_path)

    # 儲存圖片到目錄
    global uploaded_images
    if 'uploaded_images' not in globals():
        uploaded_images = []

    image_path = UPLOAD_FOLDER + "/" + original_file_name
    uploaded_images.append(image_path)
    os.replace(tempfile_path, image_path)

    # 改為動態處理多張圖片
    try:
        inputs = ["分析圖片中的文字，並保留分析完的結果，其他的說明文字不要呈現"]
        for image_path in uploaded_images:
            upload_image = Image.open(image_path)
            inputs.append(upload_image)

        response = llm.generate_content(inputs)
        # 移除不需要的提示文字
        # movie_name = response.text.replace("圖片上的文字是", "").strip()
        # finish_message = f"這部電影的名稱是: {response.text}"
        movie_name = response.text
        movie_name = movie_name.replace("\n", " ")
        flex_message = message_movie_detail(movie_name)

    except Exception as e:
        print(f"Error in image processing: {e}")
        finish_message = "處理圖片時發生錯誤，請稍後再試。"

    with ApiClient(configuration) as api_client:
        message = FlexMessage(
            alt_text="hello", contents=FlexContainer.from_json(flex_message))
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[message]
            )
        )


@handler.add(MessageEvent, message=LocationMessageContent)
def message_location(event):
    print("event:", event)
    address, latitude, longitude = get_location_info(event)
    cinemasList = find_nearby_cinemas(latitude, longitude)
    if not cinemasList:
        print("No nearby cinemas found.")
        cinemasList.append((0, "沒有找到附近的電影院", address))

    flex_message = """{
    "type": "carousel",
    "contents": [
        {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
            {
                "type": "text",
                "text": "鄰近影廳",
                "weight": "bold",
                "size": "xxl",
                "gravity": "bottom",
                "color": "#14746F"
            }
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
            {
                "type": "box",
                "layout": "vertical",
                "contents": [
                {
                    "type": "text",
                    "text": "THEATER1",
                    "align": "center",
                    "decoration": "none",
                    "weight": "bold",
                    "position": "relative",
                    "color": "#FEFEFA"
                }
                ],
                "backgroundColor": "#14746F",
                "cornerRadius": "xl",
                "paddingAll": "md",
                "action": {
                "type": "uri",
                "label": "THEATER1",
                "uri": "URL1"
                }
            },
            {
                "type": "box",
                "layout": "vertical",
                "contents": [
                {
                    "type": "text",
                    "text": "THEATER2",
                    "align": "center",
                    "decoration": "none",
                    "weight": "bold",
                    "position": "relative",
                    "color": "#14746F"
                }
                ],
                "backgroundColor": "#C0D6DF",
                "cornerRadius": "xl",
                "paddingAll": "md",
                "action": {
                "type": "uri",
                "label": "THEATER2",
                "uri": "URL2"
                }
            },
            {
                "type": "box",
                "layout": "vertical",
                "contents": [
                {
                    "type": "text",
                    "text": "THEATER3",
                    "align": "center",
                    "decoration": "none",
                    "weight": "bold",
                    "position": "relative",
                    "color": "#FEFEFA"
                }
                ],
                "backgroundColor": "#14746F",
                "cornerRadius": "xl",
                "paddingAll": "md",
                "action": {
                "type": "uri",
                "label": "THEATER3",
                "uri": "URL3"
                }
            }
            ],
            "spacing": "xxl"
        }
        }
    ]
    }"""

    for i, cinema in enumerate(cinemasList[:3]):
        cinema_info = cinema[0]  # 取得影城的詳細資訊（字典部分）
        name = cinema_info.get('name', '名稱未知')  # 取得影城名稱
        address = cinema_info.get('address', '地址未知')  # 取得影城地址
        encoded_address = quote(address)  # 將地址編碼以用於 URL

        # name = cinema[0][1]
        # address = cinema[0][2]
        # encoded_address = quote(address)
        flex_message = flex_message.replace(f"THEATER{i+1}", name)
        flex_message = flex_message.replace(
            f"URL{i+1}", f"https://maps.google.com/?q={encoded_address}")

    # Save flex_message to a txt file
    with open('flex_message.txt', 'w', encoding='utf-8') as file:
        file.write(flex_message)

    print("cinemasList:", cinemasList)
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        message = FlexMessage(
            alt_text="hello", contents=FlexContainer.from_json(flex_message))
        # 使用 push_message 正確提供 'to' 和 'messages'
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[message]
            )
        )


@handler.add(MessageEvent, message=AudioMessageContent)
def message_audio(event):
    """處理使用者發送的語音訊息並回傳轉換後的文字"""
    message = []

    with ApiClient(configuration) as api_client:  # 初始化 API 客戶端
        line_bot_blob_api = MessagingApiBlob(api_client)  # 使用 MessagingApiBlob
        audio_content = line_bot_blob_api.get_message_content(
            event.message.id)  # 下載音訊檔案

    # 設定音訊檔案儲存路徑
    file_path = './static/audio/sound.m4a'
    global user_language  # 儲存使用者語言的全域變數
    # 儲存音訊檔案並轉換為文字
    text = process_audio_to_text(audio_content, file_path)
    result, remaining_seat = call_llm(text, True)
    if result == None:
        print("No response from LLM")
    print(f"Response: {result}")

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        if remaining_seat:
            message = FlexMessage(
                alt_text="hello", contents=FlexContainer.from_json(result))
            # 使用 push_message 正確提供 'to' 和 'messages'
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[message]
                )
            )
        else:  # 需要修改
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        TextMessage(text=result)
                    ]
                )
            )


def message_movie_detail(movie_name):
    movieID = tmdb_get_movie_id(movie_name)
    movie_data = tmdb_get_movie_box_office(movieID)

    title = movie_data.get("title", "N/A")
    revenue = movie_data.get("revenue", "N/A")  # 全球票房收入
    release_date = movie_data.get("release_date", "N/A")
    genres = movie_data.get("genres", [])
    popularity = movie_data.get("popularity", "N/A")
    poster_path = movie_data.get("poster_path", None)
    runtime = movie_data.get("runtime", "N/A")
    tagline = movie_data.get("tagline", "N/A")
    vote_average = movie_data.get("vote_average", "N/A")

    summary = analyze_reviews(title)
    recommendations = tmdb_get_recommendations(movieID)
    trailer_url = tmdb_get_movie_trailer(movieID)

    genres_text = ", ".join([g['name'] for g in genres])

    flex_message = f"""{{
    "type": "carousel",
    "contents": [
      {{
        "type": "bubble",
        "hero": {{
          "type": "image",
          "url": "https://image.tmdb.org/t/p/w500{poster_path}",
          "size": "full",
          "aspectRatio": "13:20",
          "aspectMode": "cover"
        }},
        "body": {{
          "type": "box",
          "layout": "vertical",
          "contents": [
            {{
              "type": "text",
              "text": "{title}",
              "size": "xl",
              "weight": "bold"
            }},
            {{
              "type": "text",
              "text": "{genres_text}",
              "color": "#666666",
              "wrap": true
            }}
          ]
        }},
        "footer": {{
          "type": "box",
          "layout": "vertical",
          "contents": [
            {{
              "type": "button",
              "action": {{
                "type": "uri",
                "label": "Click to watch the movie trailer",
                "uri": "{trailer_url}"
              }},
              "height": "sm",
              "margin": "none",
              "color": "#635147"
            }}
          ]
        }}
      }},
      {{
        "type": "bubble",
        "body": {{
          "type": "box",
          "layout": "vertical",
          "contents": [
            {{
              "type": "text",
              "text": "電影資訊",
              "size": "xl",
              "weight": "bold"
            }},
            {{
              "type": "box",
              "layout": "baseline",
              "contents": [
                {{
                  "type": "text",
                  "text": "🗓  Release Date",
                  "offsetTop": "sm",
                  "flex": 0,
                  "margin": "sm",
                  "weight": "bold"
                }},
                {{
                  "type": "text",
                  "text": "{release_date}",
                  "size": "md",
                  "color": "#696969",
                  "align": "end",
                  "gravity": "bottom",
                  "margin": "sm",
                  "offsetTop": "sm"
                }}
              ]
            }},
            {{
              "type": "box",
              "layout": "baseline",
              "contents": [
                {{
                  "type": "text",
                  "text": "⏳ Runtime",
                  "offsetTop": "sm",
                  "flex": 0,
                  "margin": "sm",
                  "weight": "bold"
                }},
                {{
                  "type": "text",
                  "text": "{runtime} 分鐘",
                  "size": "md",
                  "color": "#696969",
                  "align": "end",
                  "gravity": "bottom",
                  "margin": "sm",
                  "offsetTop": "sm"
                }}
              ]
            }},
            {{
              "type": "box",
              "layout": "baseline",
              "contents": [
                {{
                  "type": "text",
                  "text": "💰 Box Office",
                  "offsetTop": "sm",
                  "flex": 0,
                  "margin": "sm",
                  "weight": "bold"
                }},
                {{
                  "type": "text",
                  "text": "US$ {revenue}",
                  "size": "md",
                  "color": "#696969",
                  "align": "end",
                  "gravity": "bottom",
                  "margin": "sm",
                  "offsetTop": "sm"
                }}
              ]
            }},
            {{
              "type": "box",
              "layout": "baseline",
              "contents": [
                {{
                  "type": "text",
                  "text": "⭐️ Rating",
                  "offsetTop": "sm",
                  "flex": 0,
                  "margin": "sm",
                  "weight": "bold"
                }},
                {{
                  "type": "text",
                  "text": "{vote_average} / 10",
                  "size": "md",
                  "color": "#696969",
                  "align": "end",
                  "gravity": "bottom",
                  "margin": "sm",
                  "offsetTop": "sm"
                }}
              ]
            }},
            {{
              "type": "box",
              "layout": "baseline",
              "contents": [
                {{
                  "type": "text",
                  "text": "📊 Popularity",
                  "offsetTop": "sm",
                  "flex": 0,
                  "margin": "sm",
                  "weight": "bold"
                }},
                {{
                  "type": "text",
                  "text": "{popularity}",
                  "size": "md",
                  "color": "#696969",
                  "align": "end",
                  "gravity": "bottom",
                  "margin": "sm",
                  "offsetTop": "sm"
                }}
              ]
            }},
            {{
              "type": "separator",
              "margin": "xxl"
            }},
            {{
              "type": "text",
              "text": "📝 {tagline}",
              "weight": "bold",
              "offsetTop": "lg",
              "wrap": true,
              "size": "lg"
            }},
            {{
              "type": "box",
              "layout": "baseline",
              "contents": [
                {{
                  "type": "text",
                  "text": "{summary}",
                  "weight": "regular",
                  "wrap": true,
                  "scaling": false
                }}
              ],
              "offsetTop": "xxl",
              "paddingBottom": "lg"
            }},
            {{
              "type": "separator",
              "margin": "xxl"
            }},
            {{
              "type": "text",
              "text": "🌟 Recommended Movies",
              "weight": "bold",
              "offsetTop": "lg",
              "size": "lg"
            }}, 
            {{
              "type": "box",
              "layout": "baseline",
              "contents": [
                {{
                  "type": "text",
                  "text": "1. REC1",
                  "weight": "regular",
                  "wrap": true
                }},
                {{
                  "type": "text",
                  "text": "VOTE1 / 10",
                  "size": "md",
                  "color": "#696969",
                  "align": "end",
                  "margin": "sm"
                }}
              ],
              "offsetTop": "xxl"
            }},
            {{
              "type": "box",
              "layout": "baseline",
              "contents": [
                {{
                  "type": "text",
                  "text": "2. REC2",
                  "weight": "regular",
                  "wrap": true
                }},
                {{
                  "type": "text",
                  "text": "VOTE2 / 10",
                  "size": "md",
                  "color": "#696969",
                  "align": "end",
                  "margin": "sm"
                }}
              ],
              "offsetTop": "xxl"
            }},
            {{
              "type": "box",
              "layout": "baseline",
              "contents": [
                {{
                  "type": "text",
                  "text": "3. REC3",
                  "weight": "regular",
                  "wrap": true
                }},
                {{
                  "type": "text",
                  "text": "VOTE3 / 10",
                  "size": "md",
                  "color": "#696969",
                  "align": "end",
                  "margin": "sm",
                  "offsetBottom": "none"
                }}
              ],
              "offsetTop": "xxl",
              "paddingBottom": "lg"
            }}
          ],
          "backgroundColor": "#FEFEFA",
          "justifyContent": "center"
        }}
      }}
    ]
  }}
    """

    for idx, rec in enumerate(recommendations[:3], start=1):
        mm = f"REC{idx}"
        m = rec['title']
        vv = f"VOTE{idx}"
        v = f"{rec['vote_average']}"
        print("v: ", v)
        flex_message = flex_message.replace(mm, m)
        flex_message = flex_message.replace(vv, v)

    return flex_message


if __name__ == "__main__":
    clean_up_showtimes()
    generate_showtimes()
    app.run(host='0.0.0.0', port=8080)
