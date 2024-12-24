from tmdbAPI import tmdb_get_movie_box_office, tmdb_get_movie_id, tmdb_get_movie_reviews, tmdb_get_movie_trailer, tmdb_get_recommendations, tmdb_get_watch_providers
from movie_details import analyze_reviews

def message_movie_detail(movie_name):
    movieID = tmdb_get_movie_id(movie_name)
    movie_data = tmdb_get_movie_box_office(movieID)
    
    title = movie_data.get("title", "N/A")
    revenue = movie_data.get("revenue", "N/A")  # 全球票房收入
    release_date = movie_data.get("release_date", "N/A")
    overview = movie_data.get("overview", "N/A")
    genres = movie_data.get("genres", [])
    popularity = movie_data.get("popularity", "N/A")
    poster_path = movie_data.get("poster_path", None)
    runtime = movie_data.get("runtime", "N/A")
    tagline = movie_data.get("tagline", "N/A")
    vote_average = movie_data.get("vote_average", "N/A")

    summary = analyze_reviews(title)
    recommendations = tmdb_get_recommendations(movieID)
    watch_providers = tmdb_get_watch_providers(movieID)
    trailer_url = tmdb_get_movie_trailer(movieID)
