"""命令行周报生成工具。

逐条输入本周工作要点，调用大模型（OpenAI 兼容接口）生成包含
「本周完成 / 进行中 / 下周计划 / 风险」四板块的结构化周报。

运行前需在 .env 中配置：
    DEEPSEEK_API_KEY=sk-...
    API_BASE_URL=https://api.deepseek.com/v1   # 可选，缺省为 DeepSeek

语气模式与 temperature 保存在 config.json，下次启动自动读取。
"""

import json
import os

from dotenv import load_dotenv
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
)

MODEL = "deepseek-chat"
TEMPERATURE = 0.3
MAX_TOKENS = 1200
TIMEOUT_SECONDS = 30
DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
CONFIG_FILE = "config.json"
DEFAULT_TONE = 3

# 语气模式 → 写入 system 提示词的风格说明
TONE_STYLES = {
    1: "语气简洁：每条要点只用一句话概括，不展开背景与细节。",
    2: "语气详细：每条要点展开说明背景、具体动作与结果。",
    3: "语气汇报体：采用正式、客观的汇报语气，措辞严谨规范。",
}


def build_system_prompt(tone: int) -> str:
    """按语气模式生成 system 提示词。"""
    style = TONE_STYLES.get(tone, TONE_STYLES[DEFAULT_TONE])
    return (
        "你是一名资深周报助手，根据用户输入的本周工作要点生成结构化周报正文。\n"
        f"{style}\n"
        "要求：\n"
        "1. 必须包含且只包含四个板块，标题依次为「本周完成」「进行中」「下周计划」「风险」；\n"
        "2. 每个板块用要点式写法，语言简洁、专业、具体；\n"
        "3. 只输出周报正文本身，不要任何开场白、总结语或闲聊解释，不要用 Markdown 代码块包裹。"
    )


def load_config() -> dict:
    """读取 config.json；文件缺失或损坏时回退默认配置，不抛异常。"""
    config = {"tone": DEFAULT_TONE, "temperature": TEMPERATURE}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return config
    if isinstance(saved, dict):
        tone = saved.get("tone")
        if isinstance(tone, int) and tone in TONE_STYLES:
            config["tone"] = tone
        temperature = saved.get("temperature")
        if isinstance(temperature, (int, float)):
            config["temperature"] = float(temperature)
    return config


def save_config(config: dict) -> None:
    """把配置写入 config.json；失败仅提示，不影响继续运行。"""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except OSError as exc:
        print(f"⚠️ 配置保存失败（{exc}），本次选择不会被记住。")


def choose_tone(default_tone: int) -> int:
    """询问语气模式，回车用默认，非法输入则重新询问。"""
    while True:
        raw = input(
            "周报语气模式：1-简洁 / 2-详细 / 3-汇报体"
            f"，直接回车默认选 {default_tone}："
        ).strip()
        if raw == "":
            return default_tone
        if raw in ("1", "2", "3"):
            return int(raw)
        print("⚠️ 输入无效，请输入 1、2 或 3（直接回车使用默认）。")


def read_work_points() -> list[str]:
    """逐条读取工作要点，空行结束输入。"""
    print("请逐条输入本周工作要点（输入空行结束）：")
    points: list[str] = []
    while True:
        line = input()
        if not line.strip():
            break
        points.append(line.strip())
    return points


def generate_report(client: OpenAI, points: list[str], tone: int, temperature: float) -> str:
    """调用模型生成周报，返回正文文本。"""
    user_content = "本周工作要点如下：\n" + "\n".join(f"- {p}" for p in points)
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": build_system_prompt(tone)},
            {"role": "user", "content": user_content},
        ],
        temperature=temperature,
        max_tokens=MAX_TOKENS,
    )
    return resp.choices[0].message.content or ""


def safe_generate(client: OpenAI, points: list[str], tone: int, temperature: float) -> str | None:
    """调用模型并分别捕获三类异常；出错打印中文提示并返回 None，不向上抛出。"""
    try:
        return generate_report(client, points, tone, temperature)
    except AuthenticationError:
        print("❌ API Key 无效，请检查 .env 配置。")
    except APITimeoutError:
        print("❌ 网络连接超时，请检查网络后重试。")
    except APIConnectionError:
        print("❌ 网络连接失败，请检查网络后重试。")
    except APIStatusError as exc:
        if exc.status_code == 402:
            print("❌ 账户余额不足，请前往平台充值后再试。")
        else:
            print(f"❌ 接口返回错误（HTTP {exc.status_code}），请检查 base_url 与 model 配置。")
    except Exception:
        print("❌ 发生未知错误，请稍后重试。")
    return None


def main() -> None:
    load_dotenv()
    api_key = os.getenv("DEEPSEEK_API_KEY")
    base_url = os.getenv("API_BASE_URL", DEFAULT_BASE_URL)

    if not api_key:
        print("❌ 未检测到 DEEPSEEK_API_KEY，请先在 .env 中配置后再运行。")
        return

    try:
        config = load_config()
        tone = choose_tone(config["tone"])
        temperature = config["temperature"]
        config.update(tone=tone, temperature=temperature)
        save_config(config)

        client = OpenAI(api_key=api_key, base_url=base_url, timeout=TIMEOUT_SECONDS)

        print("=== 周报生成器 ===")
        while True:
            points = read_work_points()
            if not points:
                print("未输入任何要点，已跳过本轮。")
            else:
                report = safe_generate(client, points, tone, temperature)
                if report:
                    print("\n" + "=" * 40)
                    print(report)
                    print("=" * 40)

            answer = input("\n是否继续？（输入 y 继续，其他输入退出）：").strip().lower()
            if answer != "y":
                print("已退出，再见！")
                break
    except KeyboardInterrupt:
        print("\n已退出，再见！")


if __name__ == "__main__":
    main()
