"""Streamlit 网页版周报生成工具。

复用 weekly_report.py 的核心逻辑（提示词、API 调用、历史记录），
通过 Streamlit 提供网页界面。
"""

import os

import streamlit as st
from dotenv import load_dotenv
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
)

from weekly_report import (
    DEFAULT_BASE_URL,
    MAX_TOKENS,
    MODEL,
    TIMEOUT_SECONDS,
    TONE_NAMES,
    append_history_record,
    calc_total_usage,
    generate_report,
    get_recent_history,
    load_config,
)

load_dotenv()

st.set_page_config(page_title="AI 周报生成器", page_icon="📝", layout="wide")


def web_generate_report(client, points, tone, temperature):
    """网页版调用：返回 (报告正文, 错误文案, total_tokens)，不抛出异常。"""
    try:
        content, total_tokens = generate_report(client, points, tone, temperature)
        return content, None, total_tokens
    except AuthenticationError:
        return None, "❌ API Key 无效，请检查 .env 配置。", 0
    except APITimeoutError:
        return None, "❌ 网络连接超时，请检查网络后重试。", 0
    except APIConnectionError:
        return None, "❌ 网络连接失败，请检查网络后重试。", 0
    except APIStatusError as exc:
        if exc.status_code == 402:
            return None, "❌ 账户余额不足，请前往平台充值后再试。", 0
        return None, f"❌ 接口返回错误（HTTP {exc.status_code}），请检查 base_url 与 model 配置。", 0
    except Exception:
        return None, "❌ 发生未知错误，请稍后重试。", 0


st.title("📝 AI 周报生成器（网页版）")

config = load_config()
api_key = os.getenv("DEEPSEEK_API_KEY")
base_url = os.getenv("API_BASE_URL", DEFAULT_BASE_URL)

if "show_history" not in st.session_state:
    st.session_state.show_history = False

# 侧边栏
with st.sidebar:
    st.header("参数设置")
    tone = st.selectbox(
        "周报语气模式",
        options=[1, 2, 3],
        format_func=lambda t: TONE_NAMES.get(t, str(t)),
        index=config["tone"] - 1,
    )
    st.divider()
    st.subheader("API 参数")
    st.caption(f"model：{MODEL}")
    st.caption(f"temperature：{config['temperature']}")
    st.caption(f"max_tokens：{MAX_TOKENS}")
    st.caption(f"timeout：{TIMEOUT_SECONDS}s")
    st.caption(f"base_url：{base_url}")
    st.divider()
    if st.button("查看最近 10 条历史"):
        st.session_state.show_history = not st.session_state.show_history

# 主区域
if st.session_state.show_history:
    st.header("📜 历史记录")
    records = get_recent_history(10)
    usage = calc_total_usage()
    if not records:
        st.info("暂无历史记录")
    else:
        for i, r in enumerate(reversed(records), 1):
            tone_name = TONE_NAMES.get(r.get("tone"), "?")
            with st.expander(
                f"{i}. [{r.get('request_time', '?')}] {tone_name}语气｜"
                f"输入 {r.get('input_length', 0)} 字｜{r.get('total_tokens', 0)} token"
            ):
                st.markdown("**输入要点**")
                st.text(r.get("input_text", ""))
                st.markdown("**输出周报**")
                st.markdown(r.get("output_text", ""))
    st.metric("总 token", usage["total_tokens"])
    st.metric("估算累计花费（元）", f"{usage['estimated_cost']:.4f}")
else:
    points_input = st.text_area(
        "本周工作要点（每条一行）",
        height=220,
        placeholder="例如：\n完成登录模块开发\n修复订单页 bug\n下周计划接口联调",
    )
    if st.button("生成周报", type="primary"):
        points = [line.strip() for line in points_input.strip().split("\n") if line.strip()]
        if not points:
            st.warning("请先输入本周工作要点")
        elif not api_key:
            st.error("❌ 未检测到 DEEPSEEK_API_KEY，请先在 .env 中配置后再运行。")
        else:
            client = OpenAI(api_key=api_key, base_url=base_url, timeout=TIMEOUT_SECONDS)
            with st.spinner("正在生成周报，请稍候…"):
                report, error, total_tokens = web_generate_report(
                    client, points, tone, config["temperature"]
                )
            if error:
                st.error(error)
            elif report:
                append_history_record("\n".join(points), report, total_tokens, tone)
                st.markdown("### 生成的周报")
                st.markdown(report)
                st.divider()
                st.caption("复制：点击下方代码块右上角的复制按钮")
                st.code(report, language="markdown")
