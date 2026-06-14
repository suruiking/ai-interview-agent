"""AI 面试辅导 Agent — Streamlit 前端"""
import os
import tempfile
import streamlit as st
from agent.harness_agent import HarnessAgent

st.set_page_config(page_title="AI 面试辅导", page_icon="🤖")

# ==================== 侧边栏：简历 + JD 上传 ====================
with st.sidebar:
    st.header("📎 简历分析")
    uploaded_file = st.file_uploader("上传简历", type=["pdf", "txt"])
    if uploaded_file:
        from langchain_community.document_loaders import PyPDFLoader, TextLoader

        suffix = ".pdf" if uploaded_file.name.endswith(".pdf") else ".txt"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded_file.read())
            tmp_path = tmp.name

        if suffix == ".pdf":
            loader = PyPDFLoader(tmp_path)
        else:
            loader = TextLoader(tmp_path, encoding="utf-8")
        resume_text = "\n".join([doc.page_content for doc in loader.load()])
        os.unlink(tmp_path)

        st.session_state["resume_text"] = resume_text
        st.success(f"简历已加载（{len(resume_text)} 字）")

    jd_text = st.text_area("岗位 JD（可选）", height=100, placeholder="粘贴职位描述...")
    if jd_text:
        st.session_state["jd_text"] = jd_text

# ==================== 主页面 ====================
st.title("🤖 AI 面试辅导 Agent")
st.caption("自研 Harness 引擎 | DeepSeek + RAG + ChromaDB | 源码级理解")

# 初始化 Agent
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
    # 拼接简历和 JD
    extra = ""
    if st.session_state.get("resume_text"):
        extra += f"\n\n[简历全文]\n{st.session_state['resume_text'][:4000]}"
    if st.session_state.get("jd_text"):
        extra += f"\n\n[岗位JD]\n{st.session_state['jd_text'][:2000]}"
    full_query = query + extra

    # 用户消息
    st.session_state["messages"].append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    # Agent 回复
    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_response = ""

        agent = st.session_state["agent"]
        for chunk in agent.execute_stream(full_query):
            if chunk:
                full_response += chunk
                placeholder.markdown(full_response)

    st.session_state["messages"].append({"role": "assistant", "content": full_response})
