"""AI 面试辅导 Agent — Streamlit 前端（含对话持久化）"""
import os
import tempfile
import time
import streamlit as st
from agent.harness_agent import HarnessAgent
from data.conversation_store import (
    init_db, create_conversation, save_message,
    get_conversation, list_conversations, delete_conversation,
    trim_conversations,
)
from utils.logger import get_recent_logs

st.set_page_config(page_title="AI 面试辅导", page_icon="🤖")

# 启动时初始化数据库（幂等）
init_db()

# ==================== 侧边栏 ====================
with st.sidebar:
    # ── 新对话按钮 ──
    if st.button("🆕 新对话", use_container_width=True):
        st.session_state["conv_id"] = None
        st.session_state["messages"] = []
        st.session_state["conv_title"] = None
        st.rerun()

    st.divider()

    # ── 简历上传 ──
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

    st.divider()

    # ── 历史会话列表 ──
    st.header("📜 历史会话")
    conversations = list_conversations()
    if not conversations:
        st.caption("暂无历史会话")
    else:
        for conv in conversations:
            cid = conv["id"]
            title = conv["title"]
            ts = time.strftime("%m/%d %H:%M", time.localtime(conv["created_at"]))

            col1, col2 = st.columns([4, 1])
            with col1:
                if st.button(f"💬 {title}\n_{ts}_", key=f"load_{cid}",
                             use_container_width=True,
                             help=f"加载会话: {title}"):
                    conv_data = get_conversation(cid)
                    if conv_data:
                        st.session_state["conv_id"] = cid
                        st.session_state["messages"] = conv_data["messages"]
                        st.session_state["conv_title"] = conv_data["title"]
                        st.rerun()
            with col2:
                if st.button("🗑️", key=f"del_{cid}", help="删除此会话"):
                    delete_conversation(cid)
                    # 如果删的是当前会话，重置
                    if st.session_state.get("conv_id") == cid:
                        st.session_state["conv_id"] = None
                        st.session_state["messages"] = []
                        st.session_state["conv_title"] = None
                    st.rerun()

    st.divider()

    # ── 调试日志面板 ──
    st.header("🔧 调试日志")
    show_debug = st.checkbox("☑ 显示调试日志", value=False,
                             help="开启后查看 Agent 内部运行日志")
    if show_debug:
        log_level = st.radio("级别", ["ALL", "DEBUG", "INFO", "WARNING", "ERROR"],
                             horizontal=True, key="log_level")
        logs = get_recent_logs(n=50, level=log_level)
        if logs:
            st.code("\n".join(reversed(logs)), language="text")
            st.caption(f"最近 {len(logs)} 条 · 日志文件: logs/app.log")
        else:
            st.caption("暂无日志")

# ==================== 主页面 ====================
st.title("🤖 AI 面试辅导 Agent")
st.caption("自研 Harness 引擎 | DeepSeek + RAG + ChromaDB | 对话自动保存")

# 显示当前会话标题
current_title = st.session_state.get("conv_title")
if current_title:
    st.caption(f"📝 当前会话: {current_title}")

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

    # ── 持久化：首次发言时创建会话 ──
    conv_id = st.session_state.get("conv_id")
    if conv_id is None:
        title = query[:50] + ("..." if len(query) > 50 else "")
        conv_id = create_conversation(title)
        st.session_state["conv_id"] = conv_id
        st.session_state["conv_title"] = title

    # 保存用户消息
    save_message(conv_id, "user", query)

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

    # 保存助手消息
    save_message(conv_id, "assistant", full_response)
    st.session_state["messages"].append({"role": "assistant", "content": full_response})

    # 清理超出上限的旧会话
    trim_conversations()
