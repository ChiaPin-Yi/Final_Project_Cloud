from tmdbAPI import tmdb_get_movie_id, tmdb_get_movie_reviews, tmdb_get_movie_trailer, tmdb_get_movie_box_office, tmdb_get_watch_providers, tmdb_get_recommendations

import sys
import configparser

from azure.core.credentials import AzureKeyCredential
from azure.ai.textanalytics import TextAnalyticsClient


#Config Parser
config = configparser.ConfigParser()
config.read('config.ini')

#Config Azure Analytics
credential =AzureKeyCredential(config['AzureLanguage']['API_KEY'])

# Config Gemini
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
genai.configure(api_key=config["Gemini"]["API_KEY"])

llm = genai.GenerativeModel(
    model_name="gemini-1.5-flash-latest",
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
    system_instruction="請用繁體中文回答。",
)

searchMoive_chat = llm.start_chat(history=[])


# 使用 azure 情感分析 & gemini & TMDB API 取得影評摘要
def analyze_reviews(movie_name):

    text_analytics_client=TextAnalyticsClient(
    endpoint=config['AzureLanguage']['END_POINT'],
    credential=credential)

    reviews = tmdb_get_movie_reviews(tmdb_get_movie_id(movie_name))
    documents = reviews
    response =text_analytics_client.analyze_sentiment(
        documents,
        show_opinion_mining=True,
        language='en')  # TMDB 提供的影評多數為英文
    
    docs =[doc for doc in response if not doc.is_error]
    sentiments = []
    for idx, doc in enumerate(docs):
        sentiments.append({            
            "text": doc.sentences[0].text,
            "sentiment": doc.sentiment,
            "confidence_scores": doc.confidence_scores,
        })

    # Google Gemini - 生成功能
    review_texts = "\n".join([f"- {s['text']} (情感: {s['sentiment']}  {s['confidence_scores']}) " for s in sentiments])

    print(f"影評摘要：\n{review_texts}")

    gemini_prompt = f"""
    以下是一些影評，請生成一段總結：
    {review_texts}
    要求：使用輕鬆幽默的語氣，總結整體情緒趨勢，並給出吸引人的結論，同時不要講太多廢話。
    """

    result = searchMoive_chat.send_message(gemini_prompt)

    return result.text.replace("\n", "")

def generate_creative_movie_response(movie_name):

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

    # 創意回應
    response = f"""🎬 **電影名稱**：{title}
🍿 **類型**：{", ".join([genre['name'] for genre in genres])}
🗓 **上映日期**：{release_date}
⏳ **片長**：{runtime} 分鐘
💰 **票房**：${revenue:,}
⭐️ **評分**：{vote_average}/10
🎥 **預告片**：[點擊觀看]({trailer_url})
📊 **熱度**：{popularity}
📝 **標語**：{tagline}
🖼 **海報**：[點擊查看](https://image.tmdb.org/t/p/w500{poster_path})

📖 **故事簡介**：{overview}
✨ **影評摘要**：{summary}
🌟 **推薦電影**：
    """

    # 推薦電影
    for idx, rec in enumerate(recommendations[:3], start=1):
        response += f"{idx}. {rec['title']} - {rec['vote_average']}/10\n"

    # 可觀看平台
    if watch_providers:
        response += "\n📺 **可觀看平台**：\n"
        for category, platforms in watch_providers.items():
            response += f"- {category.capitalize()}：{', '.join(platforms)}\n"

    return response

