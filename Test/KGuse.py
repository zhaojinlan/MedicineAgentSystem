#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NSTI 知识图谱用法演示
运行：
    python nsti_graph_demo.py
"""
from neo4j import GraphDatabase
import pandas as pd

# ---------- 连接配置（同你写入脚本） ----------
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASS = "test1234"

class NSTIHelper:
    def __init__(self, uri, user, pwd):
        self.driver = GraphDatabase.driver(uri, auth=(user, pwd))

    def close(self):
        self.driver.close()

    # ------------ 场景 1 ------------
    def urgent_tests(self):
        cypher = """
        MATCH (d:Disease {name:'坏死性软组织感染'})-[:SUGGESTS_TEST]->(t:Test)
        WHERE t.urgency = 'immediate'
        RETURN t.name AS 检查项目,
               t.abbr AS 缩写,
               t.threshold AS 警戒值,
               t.unit AS 单位
        ORDER BY t.name
        """
        with self.driver.session() as s:
            return [dict(r) for r in s.run(cypher)]

    # ------------ 场景 2 ------------
    def lrinec_indications(self):
        cypher = """
        MATCH (t:Test {name:'LRINEC评分'})-[r:INDICATES_HIGH_SUSPICION]->(d)
        WHERE r.threshold = '>=6'
        RETURN d.name AS 高危疾病
        """
        with self.driver.session() as s:
            return [r["高危疾病"] for r in s.run(cypher)]

    # ------------ 场景 3 ------------
    def treatment_priority(self):
        cypher = """
        MATCH (d:Disease {name:'坏死性软组织感染'})-[r]->(tr:Treatment)
        WHERE type(r) IN ['TREATED_WITH','SUPPORTIVE_CARE']
        RETURN tr.name AS 治疗,
               tr.evidence AS 证据等级,
               r.priority AS 优先序,
               tr.time_window AS 时间窗
        ORDER BY r.priority
        """
        with self.driver.session() as s:
            return [dict(r) for r in s.run(cypher)]

    # ------------ 场景 4 ------------
    def diff_dx(self):
        cypher = """
        MATCH (d:Disease {name:'坏死性软组织感染'})-[:DIFFERENTIAL_DIAGNOSIS]->(diff)
        MATCH (diff)-[ex:EXCLUDED_BY]->(nsti)
        RETURN diff.name AS 鉴别诊断,
               ex.findings AS 排除要点
        """
        with self.driver.session() as s:
            return [dict(r) for r in s.run(cypher)]

    # ------------ 场景 5 ------------
    def subgraph_for_vis(self, depth: int = 3):
        cypher = f"""
        MATCH p=(d:Disease {{name:'坏死性软组织感染'}})-[*..{depth}]-(n)
        RETURN p
        """
        with self.driver.session() as s:
            # 返回的是 Path 对象，可直接给 Bloom 或 pyvis
            return [r["p"] for r in s.run(cypher)]

    # ------------ 场景 6 ------------
    def next_step_from_finding(self, finding: str):
        cypher = """
        MATCH (d:Disease {name:'坏死性软组织感染'})
        MATCH (d)-[r]->(n)
        WHERE ($finding IN labels(n) OR n.name=$finding)
        RETURN type(r) AS 关系,
               n.name AS 名称,
               n.stage AS 分期,
               r.time_window AS 时间窗
        """
        with self.driver.session() as s:
            return [dict(r) for r in s.run(cypher, finding=finding)]

# ------------ CLI 演示菜单 ------------
def demo():
    h = NSTIHelper(NEO4J_URI, NEO4J_USER, NEO4J_PASS)
    menu = {
        "1": ("急诊必做检查", h.urgent_tests),
        "2": ("LRINEC≥6 提示哪些病", h.lrinec_indications),
        "3": ("治疗优先级清单", h.treatment_priority),
        "4": ("鉴别诊断 & 排除要点", h.diff_dx),
        "5": ("输入一个症状/检查，返回下一步", lambda: h.next_step_from_finding(input("请输入症状或检查名：")))
    }
    print("=== NSTI 知识图谱 快速查询 ===")
    for k, (desc, _) in menu.items():
        print(f"{k}. {desc}")
    choice = input("选功能（1-5，q 退出）：").strip()
    if choice == "q":
        return
    func = menu.get(choice)
    if not func:
        print("输入有误"); return
    result = func[1]()
    # 美化输出
    if result:
        df = pd.DataFrame(result)
        print(df.to_string(index=False))
    else:
        print("未命中数据")

if __name__ == "__main__":
    demo()