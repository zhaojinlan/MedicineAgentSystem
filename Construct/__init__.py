"""
知识图谱自动化工作流包

主要功能：
1. 使用docling识别文献（PDF）并转换为HTML
2. 清洗HTML（去除DOI之前的内容、去除参考文献后面的内容、删除空格）
3. 使用智能体对文件进行实体识别和关系抽取
4. 将识别得到的实体和关系存入neo4j

使用方法：
    from Construct import KnowledgeWorkflow
    
    workflow = KnowledgeWorkflow()
    result = workflow.process_document("文件路径.pdf")
"""

from .knowledge_workflow import KnowledgeWorkflow

__all__ = ["KnowledgeWorkflow"]
__version__ = "1.0.0"

