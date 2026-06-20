"""
agents/knowledge_loader.py
--------------------------
从 knowledge/ 目录加载 YAML 知识节点，构建 Writer Agent 可用的上下文。
"""
from __future__ import annotations

import sys
import os
from pathlib import Path
from typing import Optional

import yaml

KNOWLEDGE_ROOT = Path(__file__).parent.parent / "knowledge" / "concepts"
KNOWLEDGE_BASE = Path(__file__).parent.parent / "knowledge"


def load_node(node_id: str) -> dict:
    """按 ID 加载知识节点（遍历 knowledge/ 所有子目录）。"""
    for yaml_file in KNOWLEDGE_BASE.rglob("*.yaml"):
        try:
            data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
            if data and data.get("id") == node_id:
                return data
        except Exception:
            continue
    raise FileNotFoundError(f"知识节点 {node_id} 未找到")


def load_nodes_by_domain(domain: str) -> list[dict]:
    """加载某个领域下的所有节点（domain 对应 knowledge/concepts/<domain>/ 目录名）。"""
    domain_dir = KNOWLEDGE_ROOT / domain
    if not domain_dir.exists():
        raise FileNotFoundError(f"领域目录不存在: {domain_dir}")
    nodes = []
    for yaml_file in sorted(domain_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
            if data:
                nodes.append(data)
        except Exception as e:
            print(f"  [WARN] 加载 {yaml_file.name} 失败: {e}")
    return nodes


def load_nodes_by_ids(node_ids: list[str]) -> list[dict]:
    """批量加载指定 ID 列表的节点（保持顺序）。"""
    id_set = set(node_ids)
    found: dict[str, dict] = {}
    for yaml_file in KNOWLEDGE_BASE.rglob("*.yaml"):
        if not id_set - set(found.keys()):
            break
        try:
            data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
            if data and data.get("id") in id_set:
                found[data["id"]] = data
        except Exception:
            continue
    return [found[nid] for nid in node_ids if nid in found]


def build_chapter_context(primary_node: dict, related_nodes: Optional[list[dict]] = None) -> str:
    """
    将主节点和相关节点序列化为适合注入 Writer Agent Prompt 的文本块。
    """
    lines = []

    def _field(label: str, value) -> None:
        if value:
            if isinstance(value, list):
                lines.append(f"【{label}】")
                for item in value:
                    if isinstance(item, dict):
                        lines.append(f"  - {item}")
                    else:
                        lines.append(f"  - {item}")
            elif isinstance(value, dict):
                lines.append(f"【{label}】")
                for k, v in value.items():
                    lines.append(f"  {k}: {v}")
            else:
                lines.append(f"【{label}】{value}")

    node = primary_node
    lines.append(f"=== 主知识节点: {node.get('id')} - {node.get('name')} ===")
    _field("类型", node.get("type"))
    _field("适用层级", node.get("level"))
    _field("一句话定义", node.get("one_liner"))
    _field("完整定义", node.get("definition"))
    _field("为什么重要", node.get("why"))
    _field("心智模型", node.get("mental_model"))
    _field("工作原理", node.get("how_it_works"))
    _field("核心原则", node.get("core_principles"))
    _field("最佳实践", node.get("best_practices"))
    _field("反模式", node.get("anti_patterns"))
    _field("常见误区", node.get("common_misconceptions"))
    _field("面试考点", node.get("interview_points"))
    _field("考试要点", node.get("exam_points"))
    _field("示例", node.get("examples"))

    if related_nodes:
        lines.append("\n=== 相关知识节点（供参考关联）===")
        for rn in related_nodes:
            lines.append(f"\n--- {rn.get('id')} - {rn.get('name')} ---")
            lines.append(f"一句话: {rn.get('one_liner', '')}")
            if rn.get("definition"):
                lines.append(f"定义: {str(rn['definition'])[:300]}...")

    return "\n".join(lines)


def list_all_nodes() -> list[dict]:
    """列出所有知识节点的摘要信息。"""
    nodes = []
    for yaml_file in sorted(KNOWLEDGE_BASE.rglob("*.yaml")):
        try:
            data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
            if data and data.get("id"):
                nodes.append({
                    "id": data["id"],
                    "name": data.get("name", ""),
                    "level": data.get("level", ""),
                    "domain": yaml_file.parent.name,
                    "file": str(yaml_file.relative_to(KNOWLEDGE_ROOT.parent.parent)),
                })
        except Exception:
            continue
    return nodes


if __name__ == "__main__":
    # 快速测试
    nodes = list_all_nodes()
    print(f"共加载 {len(nodes)} 个知识节点:")
    for n in nodes:
        print(f"  {n['id']:20s} {n['level']:10s} {n['name']}")
