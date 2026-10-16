"""Opt-in real-model evaluation; private output, never falsely grades factual correctness."""
import argparse
import json
from pathlib import Path
from .config import Settings
from .pdf import extract
from . import llm

QUESTIONS = [
    ("论文研究的任务是什么？", "任务范围"), ("为什么循环结构限制并行训练？", "动机"),
    ("Transformer 是否使用卷积或循环结构？", "架构"), ("编码器和解码器有什么区别？", "架构"),
    ("Query、Key 和 Value 各自做什么？", "机制"), ("为什么要除以根号 d_k？", "公式"),
    ("多头注意力与单头有什么区别？", "机制"), ("因果遮罩放在哪里？", "机制"),
    ("交叉注意力中的查询与键值来自哪里？", "机制"), ("位置编码如何提供顺序信息？", "机制"),
    ("逐位置前馈网络做什么？", "机制"), ("残差连接与层归一化如何使用？", "实现"),
    ("训练时使用了什么优化器与学习率安排？", "实现"), ("模型使用什么分词方式？", "实现"),
    ("训练数据来自哪些翻译任务？", "实验"), ("英德翻译的 BLEU 结果是多少？", "数字"),
    ("英法翻译的实验结果和训练条件是什么？", "数字"), ("基础模型与大模型的设置有什么不同？", "实验"),
    ("论文如何比较计算复杂度与信息路径长度？", "实验"), ("消融实验比较了哪些因素？", "实验"),
    ("头数变化会产生什么影响？", "消融"), ("论文还测试了什么非翻译任务？", "泛化"),
    ("附录中的注意力可视化展示了什么？", "跨页附录"), ("哪些结论只适用于文中的实验范围？", "局限"),
    ("是否证明注意力在任意长度下都比循环模型更省计算？", "证据不足"),
    ("是否证明 Transformer 能可靠回答所有事实问题？", "证据不足"),
    ("论文是否报告了 GPT-4 的实验？", "证据不足"), ("是否有 GPT-3 的人类偏好训练结果？", "证据不足"),
    ("如何区分原文结论与关于后来大模型的回顾？", "背景"), ("总结三个关键结论，并分别给出原文依据。", "引用"),
]


def main():
    parser = argparse.ArgumentParser(description="针对 Transformer 原文运行 30 个真实模型问题，需要人工复核内容质量")
    parser.add_argument("--paper", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("state/paper-api/evaluation.json"))
    parser.add_argument("--live", action="store_true", help="明确启用付费模型调用")
    args = parser.parse_args()
    settings = Settings()
    if not args.live or not settings.api_key:
        parser.error("需要 --live 和 PAPER_LLM_API_KEY；未配置时不会使用模拟回答冒充真实评测。")
    blocks = extract(args.paper)["blocks"]
    overview, usage = llm.analyze(settings, blocks)
    results = []
    for question, category in QUESTIONS:
        chosen = llm.retrieve(blocks, question, [], overview)
        try:
            value, metrics = llm.call(settings, question + ' 返回 {"answer":"中文回答，证据不足时说明", "citations":["原文块id"]}。', llm.evidence(chosen))
            valid = llm.citations(value.get("citations"), chosen)
            results.append({"question": question, "category": category, "answer": value.get("answer"), "citations": valid, "all_references_valid": valid == value.get("citations"), "manual_review": "pending", "usage": metrics})
        except llm.ModelError as exc:
            results.append({"question": question, "category": category, "error": str(exc), "manual_review": "pending"})
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps({"model": settings.model, "overview_usage": usage, "requires_manual_review": True, "results": results}, ensure_ascii=False, indent=2))
    print(f"完成 {len(results)} 个问题。请人工核对数字、推断、引用支持关系和依据不足回答：{args.output}")


if __name__ == "__main__":
    main()
