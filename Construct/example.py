"""
使用示例：演示如何使用知识图谱自动化工作流

示例1：处理单个PDF文件
示例2：自定义配置
"""

from knowledge_workflow import KnowledgeWorkflow


def example1_single_file():
    """示例1：处理单个PDF文件（使用config.py中的配置）"""
    
    print("\n" + "="*80)
    print("示例1：处理单个PDF文件")
    print("="*80 + "\n")
    
    # 创建工作流实例
    workflow = KnowledgeWorkflow()
    
    # 处理PDF文件
    pdf_path = r"O:\MyProject\RAG\DB\uploads\坏死性软组织感染临床诊治急诊专家共识.pdf"
    result = workflow.process_document(pdf_path)
    
    if result:
        print(f"\n✓ 处理成功！结果保存在: {result}")
    else:
        print(f"\n✗ 处理失败！")


def example2_custom_config():
    """示例2：使用自定义配置"""
    
    print("\n" + "="*80)
    print("示例2：使用自定义配置")
    print("="*80 + "\n")
    
    # 创建工作流实例，自定义配置
    workflow = KnowledgeWorkflow(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="your_password",
        llm_base_url="https://your-llm-api.com/v1",
        llm_model="your-model-name"
    )
    
    # 处理PDF文件
    pdf_path = r"O:\MyProject\RAG\DB\uploads\坏死性软组织感染临床诊治急诊专家共识.pdf"
    result = workflow.process_document(pdf_path)
    
    if result:
        print(f"\n✓ 处理成功！结果保存在: {result}")
    else:
        print(f"\n✗ 处理失败！")


if __name__ == "__main__":
    # 运行示例1
    example1_single_file()
    
    # 如果需要运行示例2，取消下面的注释
    # example2_custom_config()

