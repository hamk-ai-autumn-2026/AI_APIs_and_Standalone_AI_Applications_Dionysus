
import os
import streamlit as st
from openai import OpenAI, OpenAIError
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# ---------------- PAGE SETTINGS ----------------

st.set_page_config(
    page_title="AI_Chatbot",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------- CUSTOM DESIGN ----------------

st.markdown("""
<style>
    .stApp {
        background: linear-gradient(
            135deg, #090d1a 0%, #11182a 55%, #17122b 100%
        );
        color: #f1f5f9;
    }

    [data-testid="stSidebar"] {
        background: #101525;
        border-right: 1px solid #30364b;
    }

    [data-testid="stSidebar"] * {
        color: #e2e8f0;
    }

    .main-title {
        font-size: 3.3rem;
        font-weight: 800;
        text-align: center;
        background: linear-gradient(90deg, #38bdf8, #a78bfa, #f472b6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0;
    }

    .subtitle {
        text-align: center;
        color: #a5b4cc;
        font-size: 1.05rem;
        margin-bottom: 2rem;
    }

    .welcome-box {
        padding: 25px;
        border: 1px solid #343b56;
        border-radius: 18px;
        background: rgba(35, 42, 70, 0.45);
        text-align: center;
        margin-bottom: 25px;
    }

    [data-testid="stChatMessage"] {
        background: rgba(31, 41, 65, 0.65);
        border: 1px solid #303b56;
        border-radius: 16px;
        padding: 12px;
        margin-bottom: 12px;
    }

    .stButton > button {
        border-radius: 12px;
        border: 1px solid #6366f1;
        transition: all 0.2s ease;
    }

    .stButton > button:hover {
        border-color: #a78bfa;
        background: #312e81;
        color: white;
    }

    [data-testid="stChatInput"] {
        border-radius: 15px;
    }

    .footer {
        text-align: center;
        color: #7e8ba5;
        font-size: 0.8rem;
        margin-top: 35px;
    }
</style>
""", unsafe_allow_html=True)

# ---------------- AVAILABLE MODELS ----------------

MODELS = {
    "GPT-4o Mini ⚡": "gpt-4o-mini",
    "GPT-4o 🧠": "gpt-4o"
}

# ---------------- SESSION STATE ----------------

if "messages" not in st.session_state:
    st.session_state.messages = []

if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None

# ---------------- SIDEBAR ----------------

with st.sidebar:
    st.markdown("## 🤖 AI_Chatbot")
    st.caption("Your intelligent AI companion")

    st.divider()

    st.markdown("### ⚙️ Model Settings")

    selected_model = st.selectbox(
        "Choose your AI model",
        list(MODELS.keys())
    )

    st.info(f"Active model: {selected_model}")

    st.divider()

    st.markdown("### 💬 Conversation")

    st.metric(
        "Total Messages",
        len(st.session_state.messages)
    )

    if st.button(
        "🗑️ New Conversation",
        use_container_width=True
    ):
        st.session_state.messages = []
        st.session_state.pending_prompt = None
        st.rerun()

    if st.session_state.messages:
        chat_export = "\n\n".join(
            f"{m['role'].upper()}"
            f" ({m.get('model', 'User')}):\n"
            f"{m['content']}"
            for m in st.session_state.messages
        )

        st.download_button(
            "📥 Download Chat",
            data=chat_export,
            file_name="AI_Chatbot_history.txt",
            mime="text/plain",
            use_container_width=True
        )

    st.divider()
    st.caption("Powered by OpenAI")
    st.caption("Built using Python & Streamlit")

# ---------------- HEADER ----------------

st.markdown(
    '<h1 class="main-title">✦ AI_Chatbot</h1>',
    unsafe_allow_html=True
)

st.markdown(
    '<p class="subtitle">'
    'Explore ideas, ask questions, and create with AI.'
    '</p>',
    unsafe_allow_html=True
)

# ---------------- WELCOME SCREEN ----------------

if not st.session_state.messages:

    st.markdown("""
    <div class="welcome-box">
        <h2>👋 Welcome to AI_Chatbot</h2>
        <p>
            Your personal AI assistant is ready to help.
            Choose a model and start exploring!
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("#### ✨ Try asking something")

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "💡 Explain Artificial Intelligence",
            use_container_width=True
        ):
            st.session_state.pending_prompt = (
                "Explain Artificial Intelligence in simple words."
            )
            st.rerun()

        if st.button(
            "💻 Help me learn Python",
            use_container_width=True
        ):
            st.session_state.pending_prompt = (
                "Teach me Python programming as a beginner."
            )
            st.rerun()

    with col2:
        if st.button(
            "🌍 Tell me an interesting fact",
            use_container_width=True
        ):
            st.session_state.pending_prompt = (
                "Tell me an interesting science fact."
            )
            st.rerun()

        if st.button(
            "✍️ Write a creative story",
            use_container_width=True
        ):
            st.session_state.pending_prompt = (
                "Write a short creative science fiction story."
            )
            st.rerun()

# ---------------- DISPLAY CHAT HISTORY ----------------

for message in st.session_state.messages:

    with st.chat_message(message["role"]):
        st.markdown(message["content"])

        if message["role"] == "assistant":
            st.caption(
                f"🤖 {message.get('model', 'AI')}"
            )

# ---------------- CHAT INPUT ----------------

typed_prompt = st.chat_input(
    "Ask AI_Chatbot anything..."
)

prompt = st.session_state.pending_prompt or typed_prompt
st.session_state.pending_prompt = None

# ---------------- GENERATE RESPONSE ----------------

if prompt:

    st.session_state.messages.append({
        "role": "user",
        "content": prompt
    })

    with st.chat_message("user"):
        st.markdown(prompt)

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key or api_key == "your_actual_openai_api_key_here":
        st.error(
            "⚠️ OpenAI API key is missing. "
            "Please configure your .env file."
        )

    else:
        try:
            client = OpenAI(
                api_key=api_key,
                timeout=30.0,
                max_retries=1
            )

            with st.chat_message("assistant"):

                with st.spinner("✨ AI is thinking..."):

                    api_messages = [
                        {
                            "role": message["role"],
                            "content": message["content"]
                        }
                        for message in st.session_state.messages
                    ]

                    response = client.chat.completions.create(
                        model=MODELS[selected_model],
                        messages=api_messages
                    )

                    answer = (
                        response.choices[0].message.content
                        or "No response was generated."
                    )

                st.markdown(answer)
                st.caption(f"🤖 {selected_model}")

            st.session_state.messages.append({
                "role": "assistant",
                "content": answer,
                "model": selected_model,
                "time": datetime.now().isoformat()
            })

        except OpenAIError as error:
            st.error(f"⚠️ OpenAI API error: {error}")

        except Exception:
            st.error(
                "Something unexpected happened. "
                "Please try again."
            )

# ---------------- FOOTER ----------------

st.markdown(
    '<div class="footer">'
    'AI_Chatbot • Multi-Model AI Experience'
    '</div>',
    unsafe_allow_html=True
)
