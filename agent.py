import streamlit as st
from langchain_openai import ChatOpenAI
from langchain_community.utilities import ArxivAPIWrapper, WikipediaAPIWrapper
from langchain_community.tools import ArxivQueryRun, WikipediaQueryRun, DuckDuckGoSearchRun
from langchain.agents import initialize_agent, AgentType
from langchain.callbacks import StreamlitCallbackHandler
from langchain.tools import Tool
import requests
from requests.exceptions import RequestException, Timeout
from langchain.memory import ConversationBufferMemory

openai_api_key = st.secrets["OPENAI_API_KEY"]


if "memory" not in st.session_state:
    st.session_state.memory = ConversationBufferMemory(
        memory_key="chat_history", 
        return_messages=True
    )

arxiv_wrapper = ArxivAPIWrapper(top_k_results=1, doc_content_chars_max=200)
arxiv = ArxivQueryRun(api_wrapper=arxiv_wrapper)

# Wikipedia
wiki_wrapper = WikipediaAPIWrapper(top_k_results=1, doc_content_chars_max=200)
wiki = WikipediaQueryRun(api_wrapper=wiki_wrapper)

# DuckDuckGo Web Search
duckduckgo = DuckDuckGoSearchRun()


# News Search
def news_search_func(query: str) -> str:
    try:
        results = duckduckgo.run(f"{query} site:news.google.com")
        return f"📰 Top news for '{query}':\n\n{results[:1000]}"
    except Exception as e:
        return f"⚠️ News search failed: {str(e)}"

news_search = Tool(
    name="News Search",
    func=news_search_func,
    description="Get summarized latest news"
)

# YouTube Search
def youtube_search_func(query: str) -> str:
    try:
        results = duckduckgo.run(f"{query} site:youtube.com")
        return f"🎥 YouTube results for '{query}':\n\n{results[:800]}"
    except Exception as e:
        return f"⚠️ YouTube search failed: {str(e)}"

youtube_search = Tool(
    name="YouTube Search",
    func=youtube_search_func,
    description="Search YouTube videos"
)

# Weather Tool 
def get_weather(location: str) -> str:
    try:
        # Example: New Delhi coords
        url = "https://api.open-meteo.com/v1/forecast?latitude=28.6&longitude=77.2&current_weather=true"
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # This will raise an exception for bad status codes
        res = response.json()
        
        current = res.get("current_weather", {})
        if current:
            return f"🌤️ Current weather in {location}: {current.get('temperature', 'N/A')}°C, Wind: {current.get('windspeed', 'N/A')} km/h"
        else:
            return "⚠️ Weather data not available"
    except Exception as e:
        return f"⚠️ Weather fetch failed: {str(e)}"

weather_tool = Tool(
    name="Weather",
    func=get_weather,
    description="Get the current weather for a given location"
)

st.title("🤖 AgentCore – Ask, Search, and Discover Instantly")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state["messages"] = [
        {"role": "assistant", "content": "Hi, I'm your smart Agent. Ask me anything!"}
    ]

# ✅ FIX: Initialize agent in session state to persist memory
if "agent" not in st.session_state:
    llm = ChatOpenAI(
        openai_api_key=openai_api_key,
        model="gpt-4o-mini",
        streaming=True,
        temperature=0.5,
    )
    
    tools = [duckduckgo, news_search, youtube_search, arxiv, wiki, weather_tool]
    
    st.session_state.agent = initialize_agent(
        tools,
        llm,
        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,  # ✅ FIX: Changed to CONVERSATIONAL for memory support
        handle_parsing_errors=True,
    )

# Display old messages
st.sidebar.title("Important Note:")
st.sidebar.info("Ask about Latest news, weather at a Particular location, General knowledge, Research topics, YouTube videos, and more!")
st.sidebar.warning("This is a demo app. The tools may not always return accurate or up-to-date information.")
for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

# Take user input
if prompt := st.chat_input(placeholder="Ask me something..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)

    # ✅ FIX: Use the persistent agent from session state
    search_agent = st.session_state.agent

    # Assistant response
    with st.chat_message("assistant"):
        try:
            st_cb = StreamlitCallbackHandler(st.container(), expand_new_thoughts=False)
            response = search_agent.run(prompt, callbacks=[st_cb])
            
            # Clean up the response if needed
            if not response or response.strip() == "":
                response = "⚠️ Unable to provide details at the moment."
                
        except Exception as e:
            error_msg = str(e)
            st.error(f"Error occurred: {error_msg}")

        st.session_state.messages.append({"role": "assistant", "content": response})
        st.write(response)