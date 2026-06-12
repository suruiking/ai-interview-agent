"""AI 面试辅导 Agent — Streamlit 前端"""
import streamlit as st
from agent.harness_agent import HarnessAgent

st.set_page_config(page_title="AI 面试辅导", page_icon="🤖")
st.title("🤖 AI 面试辅导 Agent")
st.caption("自研 Harness 引擎 | DeepSeek + RAG + ChromaDB | 源码级理解")

# 初始化 Agent（只创建一次）
if "agent" not in st.session_state:
    with st.spinner("Agent 启动中..."):
        st.session_state["agent"] = HarnessAgent()

# 初始化对话历史
if "messages" not in st.session_state:
    st.session_state["messages"] = []

# 显示历史消息
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 用户输入
if query := st.chat_input("练一道面试题，或者问我 AI 开发知识..."):
    # 用户消息
    st.session_state["messages"].append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    # Agent 回复
    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_response = ""

        agent = st.session_state["agent"]
        for chunk in agent.execute_stream(query):
            if chunk:
                full_response += chunk
                placeholder.markdown(full_response)

    st.session_state["messages"].append({"role": "assistant", "content": full_response})
