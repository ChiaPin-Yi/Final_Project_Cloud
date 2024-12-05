from flask import Flask, render_template, jsonify, url_for
from flask import request
import mysql.connector
from datetime import datetime, timedelta, time
import random
from google.cloud.sql.connector import Connector
import sqlalchemy

app = Flask(__name__, static_folder='static')

# 初始化 Connector 对象
connector = Connector()


def getconn():
    return connector.connect(
        "winter-arena-443413-i7:asia-east1:showtime-1",  # 替换为您的实例连接名称
        "pymysql",  # 指定连接器类型
        user="root",  # 数据库用户名
        password="showtime-1",  # 直接填写密码
        db="movie_db",  # 数据库名称
    )


# 创建连接池
pool = sqlalchemy.create_engine(
    "mysql+pymysql://",  # 使用 pymysql
    creator=getconn,  # 指定连接创建器
)

# 替换 Flask 应用中的 `get_db_connection` 方法


def get_db_connection():
    # 返回一个 sqlalchemy 连接对象
    return pool.connect()

# 返回字典格式的結果


@app.route('/api/moviesource', methods=['GET'])
def get_moviesource():
    conn = get_db_connection()
    result = conn.execute(
        sqlalchemy.text("SELECT id, name, src, duration AS time FROM movies")
    )
    movies = result.fetchall()
    conn.close()
    return jsonify(movies)

# 清理過期場次


def clean_up_showtimes():
    conn = get_db_connection()
    current_time = datetime.now()

    try:
        # 使用文本绑定方式
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

        # 提交事务
        conn.commit()
    except Exception as e:
        print(f"Error in clean_up_showtimes: {e}")
        # 如果出错，回滚事务
        conn.rollback()
    finally:
        # 确保连接被关闭
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

    try:
        # 获取所有电影及其时长
        result = conn.execute(sqlalchemy.text(
            "SELECT id, name, duration FROM movies"))
        movies = result.fetchall()

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
                result = conn.execute(
                    sqlalchemy.text("""
                        SELECT COUNT(*) AS count FROM showtimes
                        WHERE movie_id = :movie_id AND show_date = :show_date
                    """),
                    {"movie_id": movie_id, "show_date": show_date}
                )
                count = result.fetchone()['count']
                if count > 0:
                    print(f"跳过生成：电影 '{movie_name}' {show_date} 已有场次数据")
                    continue  # 如果已有数据，则跳过当天

                # ... (其余代码保持不变，只需要将 execute 方法改为使用 text())
                # 随机生成这部电影当天的放映厅数量（1到3个厅）
                total_rooms = random.randint(1, 3)
                # 随机从可用的放映厅中选择不重复的厅
                selected_rooms = random.sample(all_rooms, total_rooms)

                # 为每个选定的厅生成场次
                room_schedule = {room: []
                                 for room in selected_rooms}  # 每个放映厅初始化为空

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

                    for show_time in room_schedule[room]:
                        conn.execute(
                            sqlalchemy.text("""
                        INSERT INTO showtimes (movie_id, show_date, show_time, room)
                        VALUES (:movie_id, :show_date, :show_time, :room)
                    """),
                            {"movie_id": movie_id, "show_date": show_date,
                             "show_time": show_time.time(), "room": room})
        conn.commit()
    except Exception as e:
        print(f"Error in generate_showtimes: {e}")
        conn.rollback()
    finally:
        conn.close()


@app.route("/api/movie/<int:movie_id>/showtimes", methods=["GET"])
def get_movie_showtimes(movie_id):
    conn = get_db_connection()

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

    result = conn.execute(
        sqlalchemy.text("""
        SELECT show_date, show_time, room
        FROM showtimes
        WHERE movie_id = :movie_id AND show_date = :date
        ORDER BY show_time
        """),
        {"movie_id": movie_id, "date": date}
    )
    showtimes = result.fetchall()
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

    # 將 seat 列表轉換為逗號分隔的字符串
    seats = ",".join(data['seat']) if isinstance(
        data['seat'], list) else data['seat']

    # 插入數據到資料庫
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
        result = conn.execute(sqlalchemy.text(query), params)
        reservations = result.fetchall()

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
        return jsonify([dict(row) for row in reservations])
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

        # 执行删除操作
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


clean_up_showtimes()
generate_showtimes()


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/reservation")
def reservation():
    return render_template("reservation.html")


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
