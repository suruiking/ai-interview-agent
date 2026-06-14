# AI 面试辅导 Agent

**自研 Harness 引擎的完整 Agent 框架，不依赖 LangChain Agent 模块。**

## 技术栈

| 层 | 技术 | 说明 |
|------|------|------|
| **循环引擎** | 自研 `agent_loop` | 不依赖 LangChain create_agent，while 循环+工具分发自己实现 |
| **聊天模型** | DeepSeek (ChatOpenAI) | OpenAI 兼容接口 |
| **向量模型** | 千问 DashScopeEmbeddings | 阿里云百炼 |
| **向量库** | ChromaDB | 本地持久化，L2 距离检索 |
| **前端** | OTrackit | 对话界面 |

## 核心架构

```
Harness = 循环骨架 + 工具层 + 环境服务

  ┌─ agent_loop: while True → 调LLM → 解析tool_call → TOOL_HANDLERS分发 → 喂结果
  ├─ 工具层: 7个工具（rag_search/ask_question/evaluate_answer/...）
  ├─ 权限管道: 黑名单+破坏性工具+敏感数据过滤（s03）
  ├─ 上下文压缩: L1裁剪+L2占位符+L3落盘+L4 LLM摘要（s08）
  ├─ 长期记忆: 对话后LLM自动提取弱项→.memory/→下次注入prompt（s09）
  └─ MCP支持: 真实stdio子进程+JSON-RPC通信（s19）
```

## RAG 全管道

```
Query Rewriting → 向量检索(带分数) → 距离阈值过滤 → Cross-Encoder Rerank → LLM生成 → 引用验证
```

- **Query Rewriting**：用户口语问题→LLM改写为精确检索关键词
- **Rerank**：Cross-Encoder（BAAI/bge-reranker-base）逐条精排
- **引用验证**：正则检测LLM标注的【来源N】是否真实存在，不通过强制重生成

## MCP 协议

内置真实 MCP 服务器 `coding_server.py`（stdio + JSON-RPC），提供 3 个工具：

- `count_lines` — 代码行数统计
- `check_syntax` — Python 语法检查
- `run_tests` — pytest 测试运行

Agent 通过 `connect_mcp("coding-tools")` 启动服务器子进程，自动发现工具，拼入动态工具池。

## 快速开始

```bash
# 1. 安装依赖
pip install streamlit langchain langchain-openai langchain-community langchain-chroma langchain-text-splitters langchain-huggingface sentence-transformers pyyaml python-dotenv

# 2. 配置 .env
DASHSCOPE_API_KEY=你的千问Key
DEEPSEEK_API_KEY=你的DeepSeek Key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1

# 3. 启动
streamlit run app.py --server.port 8502
```

首次启动会自动下载 Rerank 模型（278MB）并向量化知识库。

## 项目结构

```
ai-interview-agent/
├── agent/
│   ├── harness_agent.py      # 自研引擎（ReAct循环+工具分发+流式输出）
│   ├── context_compact.py    # 四层上下文压缩
│   └── tools/
│       └── harness_tools.py  # 7个工具+TOOLS+TOOL_HANDLERS
├── rag/
│   ├── vector_store.py       # 文档加载→切块→Embedding→ChromaDB
│   └── rag_service.py        # 改写→检索→过滤→Rerank→生成→引用验证
├── mcp/
│   ├── mcp_manager.py        # MCP客户端+动态工具池
│   └── coding_server.py      # 真实stdio MCP服务器
├── memory/
│   └── memory_manager.py     # 长期记忆：提取→写入→索引→注入
├── model/
│   └── factory.py            # LLM+Embedding工厂
├── prompts/
│   ├── main_prompt.txt       # Agent人设+工具规则
│   └── rag_prompt.txt        # RAG引用约束
├── data/
│   └── 面试题库.txt           # 知识库
└── app.py                    # Streamlit前端
```

## 版本

- v0.1-v0.4：基座 + RAG全管道 + Harness引擎
- v0.5：长期记忆（s09）
- v0.6：上下文压缩（s08）
- v0.7：权限Hook（s03）
- v0.8-v0.10：MCP 协议（s19）
- v0.11-v0.12：容错完善 + 引用来源
