# 訂票系統
import sys
import configparser
from collections import defaultdict
import requests
import configparser
import urllib.request
import mysql.connector as pymysql
import os
import tempfile
import socket
import math
from flask import Flask, request, abort, render_template, url_for
from tmdbAPI import tmdb_get_movie_id, tmdb_get_movie_box_office
import json
import time
from datetime import datetime
import random
import mysql.connector
from google.cloud.sql.connector import Connector
import sqlalchemy
from urllib.parse import quote


from linebot.v3 import (
    WebhookHandler
)
from linebot.v3.exceptions import (
    InvalidSignatureError
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    LocationMessageContent
)
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    FlexMessage,
    FlexContainer

)

# Config Parser
config = configparser.ConfigParser()
config.read('config.ini')

app = Flask(__name__)

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

# 設定 GOOGLE_APPLICATION_CREDENTIALS
google_credentials = config["GoogleCloud"]["APPLICATION_CREDENTIALS"]
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = google_credentials

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


conn = get_db_connection()


movie_source = {}
id_to_name = {}


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


@handler.add(MessageEvent, message=TextMessageContent)
def message_text(event):

    lines = event.message.text.splitlines()
    input_parser = [word for line in lines for word in line.split()]
    for i in range(0, 3):
        if len(input_parser) < 4:
            input_parser.append("")
    output = query_remaining_seats(
        input_parser[0], input_parser[1], input_parser[2], input_parser[3])

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=output)]
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
                "uri": "ULR2"
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
        name = cinema[i][1]
        address = cinema[i][2]
        encoded_address = quote(address)
        flex_message = flex_message.replace(f"THEATER{i+1}", name)
        flex_message = flex_message.replace(
            f"URL{i+1}", f"https://maps.google.com/?q={encoded_address}")

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
    # with ApiClient(configuration) as api_client:
    #     line_bot_api = MessagingApi(api_client)
    #     line_bot_api.reply_message_with_http_info(
    #         ReplyMessageRequest(
    #             reply_token=event.reply_token,
    #             messages=[TextMessage(text="附近的電影院有:\n"\
    #                                    + "\n".join([f"{cinema[1]}({cinema[2]})" for cinema in cinemasList]))]
    #         )
    #     )


def fetch_movie_source():
    global movie_source, id_to_name
    global conn
    result = conn.execute(
        sqlalchemy.text("SELECT id, name, src, duration AS time FROM movies")
    )
    movies = [dict(row._mapping) for row in result.fetchall()]
    # cursor = conn.cursor(dictionary=True)
    # cursor.execute("SELECT id, name, src, duration AS time FROM movies")
    # movies = cursor.fetchall()  # 获取查询结果
    # cursor.close()
    for movie in movies:
        movie_source[movie['name']] = movie
        id_to_name[movie['id']] = movie['name']
    # print("Movie source fetched:", movie_source)
    # print("id_to_name:", id_to_name)
    return

# get location info


def get_location_info(event):
    address = event.message.address
    latitude = event.message.latitude
    longitude = event.message.longitude

    print(f"Address: {address}")
    print(f"Latitude: {latitude}")
    print(f"Longitude: {longitude}")
    return address, latitude, longitude

# 使用 ip 取得使用者位置


def get_user_location():
    print("get_user_location")
    url = "http://ip-api.com/batch"
    # post data
    # ip = user_ip
    # data = [{"query": ip, "fields": "city,country,regionName,lat,lon", "lang": "zh-CN"}]
    # Convert the list of IPs to JSON format
    data = json.dumps(data)
    print("Sending:", data)
    contry = ''
    city = ''
    regionName = ''
    lat = ''
    lon = ''
    try:
        # Make the POST request
        response = requests.post(url, data=data)

        # Check if the request was successful
        if response.status_code == 200:
            # Parse the response JSON
            results = response.json()
            # print(results)
            contry = results[0].get('country', 'Unknown Country')
            city = results[0].get('city', 'Unknown City')
            regionName = results[0].get('regionName', 'Unknown Region')
            lat = results[0].get('lat', 'Unknown Latitude')
            lon = results[0].get('lon', 'Unknown Longitude')
        else:
            print(f"Request failed with status code: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"An error occurred: {e}")
    return contry, city, regionName, lat, lon

# 計算兩點間的距離


def get_distance(lat1, lon1, lat2, lon2):
    # 地球半徑
    R = 6371
    # 計算緯度差
    dLat = (lat2 - lat1) * (3.141592653589793 / 180)
    # 計算經度差
    dLon = (lon2 - lon1) * (3.141592653589793 / 180)
    # 計算兩點間的距離
    a = (math.sin(dLat / 2) * math.sin(dLat / 2) +
         math.cos(lat1 * (3.141592653589793 / 180)) * math.cos(lat2 * (3.141592653589793 / 180)) *
         math.sin(dLon / 2) * math.sin(dLon / 2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c
    return distance

# 用經緯度找尋附近的電影院


def find_nearby_cinemas(lat, lon):
    # 使用 DB 的資料
    lat = float(lat)
    lon = float(lon)
    global conn
    result = conn.execute(
        sqlalchemy.text("SELECT * FROM cinemas")
    )
    selected_data = [dict(row._mapping) for row in result.fetchall()]

    # result = []
    # cursor = conn.cursor()
    # query = "SELECT * from cinemas"
    # cursor.execute(query)
    # selected_data = cursor.fetchall()
    nearby_cinemas = []
    for data in selected_data:
        distance = get_distance(lat, lon, data[3], data[4])
        if distance < 10:
            nearby_cinemas.append((data, distance))  # 同時儲存 data 和 distance

    # cursor.close()
    # 根據距離進行排序
    sorted_cinemas = sorted(nearby_cinemas, key=lambda x: x[1])
    return sorted_cinemas

# 生成電影剩餘座位


def generate_remaining_seats():
    global conn
    # cursor = conn.cursor()
    # query = "SELECT * from showtimes"
    # cursor.execute(query)
    # selected_data = cursor.fetchall()
    selected_data = conn.execute(
        sqlalchemy.text("SELECT * FROM showtimes")
    ).fetchall()

    # cursor.execute("DELETE FROM remaining_seats")
    # cursor.execute("ALTER TABLE remaining_seats AUTO_INCREMENT = 1")
    conn.execute(sqlalchemy.text("DELETE FROM remaining_seats"))
    conn.execute(sqlalchemy.text(
        "ALTER TABLE remaining_seats AUTO_INCREMENT = 1"))

    # conn.commit()
    for data in selected_data:
        remaining_seats = random.randint(0, 50)
        showtime_id = data[0]
        movie_id = int(data[1])
        raw_date = data[2]  # 原始日期
        raw_time = data[3]  # 原始時間
        cinema_id = data[4]

        formatted_date = datetime.strptime(
            str(raw_date), "%Y-%m-%d").strftime("%Y-%m-%d")
        formatted_time = datetime.strptime(
            str(raw_time), "%H:%M:%S").strftime("%H:%M")

        max_seats = 32

        # cursor.execute(
        #    """
        #    SELECT COALESCE(SUM(LENGTH(seats) - LENGTH(REPLACE(seats, ',', '')) + 1), 0) AS reserved_seats
        #    FROM reservations
        #    WHERE movie_id = %s AND reservation_date = %s AND reservation_time = %s
        #    """,
        #    (movie_id, formatted_date, formatted_time)
        # )
        # result = cursor.fetchone()
        result = conn.execute(
            sqlalchemy.text("""
            SELECT COALESCE(SUM(LENGTH(seats) - LENGTH(REPLACE(seats, ',', '')) + 1), 0) AS reserved_seats
            FROM reservations
            WHERE movie_id = :movie_id AND reservation_date = :reservation_date AND reservation_time = :reservation_time
            """),
            {
                "movie_id": movie_id,
                "reservation_date": formatted_date,
                "reservation_time": formatted_time
            }
        ).fetchone()

        reserved_seats = result[0] if result else 0  # 已預訂座位數

        print(
            f"Reserved seats for movie {movie_id} at {formatted_date} {formatted_time}: {reserved_seats}")
        # 5. 計算剩餘座位數
        remaining_seats = max(max_seats - reserved_seats, 0)  # 避免負數

        # 6. 插入剩餘座位數到 remaining_seats 表
        # cursor.execute(
        #    """
        #    INSERT INTO remaining_seats (showtime_id, movie_id, cinema_id, remaining_seats)
        #    VALUES (%s, %s, %s, %s)
        #    """,
        #    (showtime_id, movie_id, cinema_id, remaining_seats)
        # )
        conn.execute(
            sqlalchemy.text("""
            INSERT INTO remaining_seats (showtime_id, movie_id, cinema_id, remaining_seats)
            VALUES (:showtime_id, :movie_id, :cinema_id, :remaining_seats)
            """),
            {
                "showtime_id": showtime_id,
                "movie_id": movie_id,
                "cinema_id": cinema_id,
                "remaining_seats": remaining_seats
            }
        )
    # cursor.close()
    conn.commit()
    return


print("Starting Ticket Booking System")
generate_remaining_seats()
fetch_movie_source()


def query_remaining_seats(movie_name, date=None, time=None, room=None):
    print("query_remaining_seats")
    global conn
    # cursor = conn.cursor()
    movie_id = movie_source[movie_name]['id']
    print(
        f"movie_id: {movie_id}, cinema_id: {room}, date: {date}, time: {time}")

    # 查詢 showtimes 並加入篩選條件
    # query = "SELECT * FROM showtimes WHERE movie_id = %s"
    # params = [movie_id]
    # if date:
    #    query += " AND show_date = %s"
    #    params.append(date)
    # if time:
    #    query += " AND show_time = %s"
    #    params.append(time)
    # if room:
    #    query += " AND room = %s"
    #    params.append(room)

    showtimes_query = """
    SELECT * FROM showtimes WHERE movie_id = :movie_id
    """
    params = {"movie_id": movie_id}
    if date:
        showtimes_query += " AND show_date = :show_date"
        params["show_date"] = date
    if time:
        showtimes_query += " AND show_time = :show_time"
        params["show_time"] = time
    if room:
        showtimes_query += " AND room = :room"
        params["room"] = room

    # cursor.execute(query, params)
    # showtime_list = cursor.fetchall()
    showtime_list = conn.execute(sqlalchemy.text(
        showtimes_query), params).fetchall()

    # 一次性查詢所有剩餘座位資訊
    showtime_ids = [showtime[0] for showtime in showtime_list]
    format_strings = ','.join(['%s'] * len(showtime_ids))
    # query = f"SELECT * FROM remaining_seats WHERE showtime_id IN ({format_strings})"
    # cursor.execute(query, tuple(showtime_ids))
    # remaining_seats_list = cursor.fetchall()
    remaining_seats_query = f"""
    SELECT * FROM remaining_seats WHERE showtime_id IN :showtime_ids
    """
    remaining_seats_list = conn.execute(
        sqlalchemy.text(remaining_seats_query), {
            "showtime_ids": tuple(showtime_ids)}
    ).fetchall()

    # cursor.close()
    # conn.commit()

    # 組合剩餘座位數據
    remaining_seats_dict = {data[0]: data[3] for data in remaining_seats_list}

    # 合併相同日期和影廳的時間與剩餘座位
    combined_data = defaultdict(list)
    for showtime in showtime_list:
        key = (showtime[2], showtime[4])  # 日期, 影廳
        formatted_time = datetime.strptime(
            str(showtime[3]), '%H:%M:%S').strftime('%H:%M')
        remaining_seats = remaining_seats_dict.get(showtime[0], "無資料")
        combined_data[key].append((formatted_time, remaining_seats))
    # 建立 Flex Message
    flex_contents = []
    for (show_date, room), times_seats in combined_data.items():
        formatted_date = datetime.strptime(
            str(show_date), "%Y-%m-%d").strftime("%Y-%m-%d")

        # 每個場次卡片 (Bubble)
        bubble = {
            "type": "bubble",
            "size": "kilo",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": "MOVIE", "size": "sm",
                        "color": "#1DB446", "weight": "bold"},
                    {"type": "text", "text": movie_name, "margin": "md",
                        "size": "xxl", "weight": "bold"},
                    {"type": "separator", "margin": "md"},
                    {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "日期", "flex": 0,
                                        "size": "sm", "color": "#555555"},
                                    {"type": "text", "text": formatted_date,
                                        "size": "sm", "color": "#111111", "align": "end"}
                                ],
                                "margin": "xxl"
                            },
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "影廳", "flex": 0,
                                        "size": "sm", "color": "#555555"},
                                    {"type": "text", "text": room, "size": "sm",
                                        "color": "#111111", "align": "end"}
                                ]
                            },
                            {"type": "separator", "margin": "xxl"},
                            {"type": "text", "text": "剩餘座位", "size": "sm",
                                "color": "#555555", "margin": "xxl"}
                        ]
                    }
                ] + [
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [
                            {"type": "text", "text": time,
                                "size": "sm", "color": "#555555"},
                            {"type": "text", "text": f"{seats}個",
                                "size": "sm", "color": "#111111", "align": "end"}
                        ],
                        "margin": "md" if i == 0 else "none"
                    }
                    for i, (time, seats) in enumerate(times_seats)
                ]
            },
            "styles": {
                "body": {"backgroundColor": "#FEFEFA"}
            }
        }
        flex_contents.append(bubble)

    # 包裝成 Carousel
    flex_message = {
        "type": "carousel",
        "contents": flex_contents
    }
    bubble_str = json.dumps(flex_message, ensure_ascii=False)

    return bubble_str, True


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
