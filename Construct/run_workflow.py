"""
知识图谱工作流命令行接口

使用方法：
    python run_workflow.py <PDF文件路径>
    
示例：
    python run_workflow.py "O:\MyProject\RAG\DB\uploads\坏死性软组织感染临床诊治急诊专家共识.pdf"
    
或者在交互模式下运行：
    python run_workflow.py
"""

import sys
import os
from pathlib import Path
from knowledge_workflow import KnowledgeWorkflow


def main():
    """命令行主函数"""
    
    print("=" * 80)
    print("知识图谱自动化工作流")
    print("=" * 80)
    print()
    
    # 检查命令行参数
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        # 交互式输入
        print("请输入PDF文件路径（或直接回车使用默认示例文件）：")
        pdf_path = input("> ").strip()
        
        if not pdf_path:
            # 使用默认示例文件
            pdf_path = r"O:\MyProject\RAG\DB\uploads\坏死性软组织感染临床诊治急诊专家共识.pdf"
            print(f"使用默认文件: {pdf_path}")
    
    # 检查文件是否存在
    if not os.path.exists(pdf_path):
        print(f"\n✗ 错误：文件不存在 - {pdf_path}")
        sys.exit(1)
    
    print(f"\n准备处理: {Path(pdf_path).name}")
    print()
    
    # 创建工作流实例（使用config.py中的配置）
    workflow = KnowledgeWorkflow()
    
    # 执行工作流
    result = workflow.process_document(pdf_path)
    
    if result:
        print(f"\n{'='*80}")
        print(f"✓ 工作流执行成功！")
        print(f"{'='*80}")
        print(f"\n结果保存在: {result}")
        print(f"\n生成的文件：")
        print(f"  - 01_raw.html         : 原始HTML文件")
        print(f"  - 02_cleaned.html     : 清洗后的HTML文件")
        print(f"  - 03_document.md      : Markdown文档")
        print(f"  - 04_knowledge_graph.json : 知识图谱（实体和关系）")
        print(f"\n知识图谱已导入Neo4j数据库")
    else:
        print(f"\n{'='*80}")
        print(f"✗ 工作流执行失败！")
        print(f"{'='*80}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n用户中断执行")
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

