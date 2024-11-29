CREATE DATABASE movie_db;

USE movie_db;

CREATE TABLE movies (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    src VARCHAR(255),
    duration INT
);

CREATE TABLE reservations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    movie_id INT,
    user_name VARCHAR(255),
    reservation_date DATE,
    reservation_time TIME,
    seats TEXT,
    tickets INT,
    FOREIGN KEY (movie_id) REFERENCES movies(id)
);

CREATE TABLE showtimes (
    id INT AUTO_INCREMENT PRIMARY KEY, -- 場次 ID
    movie_id INT NOT NULL,             -- 對應的電影 ID
    show_date DATE NOT NULL,           -- 放映日期
    show_time TIME NOT NULL,           -- 放映時間
    room VARCHAR(50),                  -- 放映廳（如 Room A, Room B）
    FOREIGN KEY (movie_id) REFERENCES movies(id)    -- 關聯電影表
);

INSERT INTO movies (name, src, duration) VALUES
('Avatar', 'image/IMG_5841.JPG', 162),
('Dune', 'image/IMG_5842.JPG', 155),
('To All the Boy I''ve Loved Before', 'image/IMG_5840.JPG', 99),
('Little Woman', 'image/IMG_5839.JPG', 135),
('Fresh', 'image/IMG_5838.JPG', 117),
('Before Sunrise', 'image/IMG_5836.JPG', 105),
('Everything Everywhere All at Once', 'image/IMG_5837.JPG', 140),
('Enola Holmes', 'image/IMG_5833.JPG', 123),
('Call Me By Your Name', 'image/IMG_5835.JPG', 130),
('Princess Mononoke', 'image/IMG_5834.JPG', 124);
