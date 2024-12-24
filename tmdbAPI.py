import requests

# get 電影ID
def tmdb_get_movie_id(movie_name):
    url = "https://api.themoviedb.org/3/search/movie"
    params = {
        "api_key": "667621b92d162532c756a520b12952ea",
        "query": movie_name,
        "language": "en-US"
    }
    
    response = requests.get(url, params=params)
    # 確保 API 請求成功
    if response.status_code == 200:
        results = response.json().get("results", [])
        if results:
            # 獲取第一個匹配結果的 ID
            # print(f"Results: \n{results}")
            # print("-"*40)
            movie_id = results[0].get("id")
            print(f"Movie ID for '{movie_name}': {movie_id}")
            print("-"*40)
            return movie_id
        else:
            print(f"No movie found for '{movie_name}'")
            return None
    else:
        print(f"Failed to fetch data: {response.status_code}")
        return None

# get 電影影評
def tmdb_get_movie_reviews(movie_id):
    url = f"https://api.themoviedb.org/3/movie/{movie_id}/reviews"
    params = {"api_key": "667621b92d162532c756a520b12952ea"}  # 替換為你的 TMDB API 金鑰
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        reviews_data = response.json()  # API 返回的 JSON 數據
        reviews = reviews_data.get("results", [])  # 獲取 "results" 字段中的影評列表
        contents = []

        # 遍歷影評列表，提取 "content" 字段
        for review in reviews:
            content = review.get("content", "No content available")  # 如果沒有 "content"，提供默認值
            contents.append(content)

        return contents
    else:
        print(f"Failed to fetch reviews: {response.status_code}")
        return None        

# get 電影預告片
def tmdb_get_movie_trailer(movie_id):
    url = f"https://api.themoviedb.org/3/movie/{movie_id}/videos"
    params = {
        "api_key": "667621b92d162532c756a520b12952ea",  # TMDB API 金鑰
        "language": "en-US"  # 語言
    }

    response = requests.get(url, params=params)

    if response.status_code == 200:
        videos = response.json().get("results", [])
        for video in videos:
            # 篩選出類型為 "Trailer" 且來源為 "YouTube" 的視頻
            if video["type"] == "Trailer" and video["site"] == "YouTube":
                youtube_url = f"https://www.youtube.com/watch?v={video['key']}"
                print(f"Trailer: {youtube_url}")
                return youtube_url
        print("No trailer found.")
        return None
    else:
        print(f"Failed to fetch data: {response.status_code}")
        return None

# get 電影簡介, 票房等
def tmdb_get_movie_box_office(movie_id):
    url = f"https://api.themoviedb.org/3/movie/{movie_id}"
    params = {
        "api_key": "667621b92d162532c756a520b12952ea",  # 替換為您的 TMDB API 金鑰
        "language": "en-US"
    }

    response = requests.get(url, params=params)
    if response.status_code == 200:
        movie_details = response.json()
        title = movie_details.get("title", "N/A")
        revenue = movie_details.get("revenue", "N/A")  # 全球票房收入
        release_date = movie_details.get("release_date", "N/A")
        overview = movie_details.get("overview", "N/A")
        genres = movie_details.get("genres", [])
        popularity = movie_details.get("popularity", "N/A")
        poster_path = movie_details.get("poster_path", None)
        runtime = movie_details.get("runtime", "N/A")
        tagline = movie_details.get("tagline", "N/A")
        vote_average = movie_details.get("vote_average", "N/A")

        # print(f"Title: {title}")
        # print(f"Tagline: {tagline}")
        # print(f"Overview: {overview}")
        # print(f"Genres: {[genre['name'] for genre in genres]}")
        # print(f"Runtime: {runtime} minutes")
        # print(f"Release Date: {release_date}")
        # print(f"Revenue: ${revenue:,.2f}")
        # print(f"Popularity: {popularity}")
        # print(f"Vote Average: {vote_average}")
        # print(f"Poster URL: https://image.tmdb.org/t/p/w500{poster_path}")

        return movie_details
    else:
        print(f"Failed to fetch data: {response.status_code}")
        return None

# get 電影串流平台
def tmdb_get_watch_providers(movie_id):

    url = f"https://api.themoviedb.org/3/movie/{movie_id}/watch/providers"
    params = {
        "api_key": "667621b92d162532c756a520b12952ea"  # 替換為您的 TMDB API 金鑰
    }

    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        providers_data = response.json()
        tw_data = providers_data.get("results", {}).get("TW", {})
        
        if not tw_data:
            print("No watch providers available for Taiwan.")
            return None

        platforms = {
            "subscription": [provider["provider_name"] for provider in tw_data.get("flatrate", [])],
            "rent": [provider["provider_name"] for provider in tw_data.get("rent", [])],
            "buy": [provider["provider_name"] for provider in tw_data.get("buy", [])]
        }

        # 顯示結果
        for key, providers in platforms.items():
            print(f"{key.capitalize()} Services in Taiwan:")
            for provider in providers:
                print(f"  - {provider}")
        
        print(f"More details: {tw_data.get('link')}")
        return platforms
    else:
        print(f"Failed to fetch watch providers: {response.status_code}")
        return None

# get 電影推薦
def tmdb_get_recommendations(movie_id):

    url = f"https://api.themoviedb.org/3/movie/{movie_id}/recommendations"
    params = {
        "api_key": "667621b92d162532c756a520b12952ea",
        "language": "en-US",
        "page": 1
    }

    response = requests.get(url, params=params)

    if response.status_code == 200:
        data = response.json()
        recommendations = data.get("results", [])  # 獲取推薦電影列表
        for movie in recommendations:
            title = movie.get("title", "N/A")
            overview = movie.get("overview", "No overview available.")
            release_date = movie.get("release_date", "Unknown")
            vote_average = movie.get("vote_average", 0)
            poster_path = movie.get("poster_path", None)

            # print(f"Title: {title}")
            # print(f"Overview: {overview}")
            # print(f"Release Date: {release_date}")
            # print(f"Average Rating: {vote_average}")
            # if poster_path:
            #     print(f"Poster URL: https://image.tmdb.org/t/p/w500{poster_path}")
            # print("-" * 40)
        return recommendations
    else:
        print(f"Failed to fetch recommendations: {response.status_code}")
        return None

def find_all_movie_type():

    url='https://api.themoviedb.org/3/genre/movie/list?api_key=667621b92d162532c756a520b12952ea&language=en-US'
    params = {
        "api_key": "667621b92d162532c756a520b12952ea",
        "language": "en-US",
        "page": 1
    }

    response = requests.get(url, params=params)

    if response.status_code == 200:
        data = response.json()
        genres = data.get("genres", [])
        for genre in genres:
            print(f"ID: {genre['id']}, Name: {genre['name']}")
        return genres
    else:
        print(f"Failed to fetch genres: {response.status_code}")
        return None
    


# find_all_movie_type()

# movie_name = "La La Land"  # 電影名稱
# movie_id = tmdb_get_movie_id(movie_name)       # ID
# contents = tmdb_get_movie_reviews(movie_id)    # 影評
# trailer = tmdb_get_movie_trailer(movie_id)     # YouTube Trailer
# box_office = tmdb_get_movie_box_office(movie_id)  # 電影簡介, 票房等
# watch_provider = tmdb_get_watch_providers(movie_id)  # Watch Providers
# recommendations = tmdb_get_recommendations(movie_id)  # Recommendations

