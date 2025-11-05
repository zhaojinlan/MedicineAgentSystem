"""
知识图谱自动化工作流
功能：
1. 使用docling识别文献（PDF）并转换为HTML
2. 清洗HTML：去除DOI之前的内容、去除参考文献后面的内容、删除空格
3. 使用智能体对文件进行实体识别
4. 将识别得到的实体和关系存入neo4j

每次处理时在O:\MyProject\Knowledges下创建以上传文件命名的文件夹
保存每一步的内容（html、markdown、json）
"""

import warnings
warnings.filterwarnings("ignore", category=UserWarning)

import os
import re
import json
import time
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# Docling相关
from docling.document_converter import DocumentConverter

# HTML处理相关
from bs4 import BeautifulSoup
import html2text

# LLM相关
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

# Neo4j相关
from py2neo import Graph, Node, Relationship

# 导入全局配置
import sys
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from config import NEO4J_CONFIG, LLM_CONFIG, PROCESSING_CONFIG, get_path
    # 为了兼容性，创建 OUTPUT_CONFIG
    OUTPUT_CONFIG = {
        "base_dir": str(get_path("knowledges_dir"))
    }
except ImportError as e:
    print(f"警告: 无法导入全局配置 ({e})，使用默认配置")
    # 如果config.py不存在，使用默认配置
    NEO4J_CONFIG = {
        "uri": "bolt://localhost:7687",
        "user": "neo4j",
        "password": "test1234"
    }
    LLM_CONFIG = {
        "base_url": "https://zjlchat.vip.cpolar.cn/v1",
        "model": "qwen2.5:14b",
        "api_key": "EMPTY",
        "temperature": 0.1,
        "top_p": 0.8
    }
    OUTPUT_CONFIG = {
        "base_dir": str(Path(__file__).parent.parent / "Knowledges")
    }
    PROCESSING_CONFIG = {
        "chunk_size": 2000,
        "chunk_overlap": 200,
        "request_interval": 1
    }


class Entity(BaseModel):
    """实体定义"""
    name: str = Field(description="实体名称")
    entity_type: str = Field(description="实体类型：Disease/Symptom/Test/Treatment/Pathogen/RiskFactor/DifferentialDiagnosis")
    description: str = Field(description="实体描述")


class RelationshipModel(BaseModel):
    """关系定义"""
    source: str = Field(description="源实体名称")
    target: str = Field(description="目标实体名称")
    relation_type: str = Field(description="关系类型：HAS_SYMPTOM/DIAGNOSED_BY/TREATED_WITH/CAUSED_BY/HAS_RISK_FACTOR/DIFFERENTIAL_DIAGNOSIS")
    description: Optional[str] = Field(default="", description="关系描述")


class KnowledgeGraph(BaseModel):
    """知识图谱结构"""
    entities: List[Entity] = Field(description="实体列表")
    relationships: List[RelationshipModel] = Field(description="关系列表")


class KnowledgeWorkflow:
    """知识图谱构建自动化工作流"""
    
    def __init__(self, 
                 neo4j_uri=None,
                 neo4j_user=None,
                 neo4j_password=None,
                 llm_base_url=None,
                 llm_model=None):
        """
        初始化工作流
        
        Args:
            neo4j_uri: Neo4j数据库地址（如果为None，使用config.py中的配置）
            neo4j_user: Neo4j用户名（如果为None，使用config.py中的配置）
            neo4j_password: Neo4j密码（如果为None，使用config.py中的配置）
            llm_base_url: LLM API地址（如果为None，使用config.py中的配置）
            llm_model: LLM模型名称（如果为None，使用config.py中的配置）
        """
        # 使用配置文件或传入的参数
        self.base_dir = Path(OUTPUT_CONFIG["base_dir"])
        self.base_dir.mkdir(exist_ok=True)
        
        # 配置LLM
        self.llm = ChatOpenAI(
            model=llm_model or LLM_CONFIG["model"],
            base_url=llm_base_url or LLM_CONFIG["base_url"],
            api_key=LLM_CONFIG.get("api_key", "EMPTY"),
            temperature=LLM_CONFIG.get("temperature", 0.1),
            top_p=LLM_CONFIG.get("top_p", 0.8)
        )
        
        # Neo4j配置
        self.neo4j_uri = neo4j_uri or NEO4J_CONFIG["uri"]
        self.neo4j_user = neo4j_user or NEO4J_CONFIG["user"]
        self.neo4j_password = neo4j_password or NEO4J_CONFIG["password"]
        
        # 处理配置
        self.chunk_size = PROCESSING_CONFIG.get("chunk_size", 2000)
        self.chunk_overlap = PROCESSING_CONFIG.get("chunk_overlap", 200)
        self.request_interval = PROCESSING_CONFIG.get("request_interval", 1)
        
        print("=" * 80)
        print("知识图谱自动化工作流已初始化")
        print("=" * 80)
        print(f"输出目录: {self.base_dir}")
        print(f"LLM模型: {llm_model}")
        print(f"Neo4j地址: {neo4j_uri}")
        print("=" * 80)
    
    def process_document(self, pdf_path: str) -> Optional[str]:
        """
        处理单个PDF文档的完整流程
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            工作目录路径，失败返回None
        """
        pdf_path = Path(pdf_path)
        
        if not pdf_path.exists():
            print(f"错误：文件不存在 - {pdf_path}")
            return None
        
        # 创建工作目录（以文件名命名，去除扩展名）
        doc_name = pdf_path.stem
        work_dir = self.base_dir / doc_name
        work_dir.mkdir(exist_ok=True)
        
        print(f"\n{'='*80}")
        print(f"开始处理文档: {doc_name}")
        print(f"工作目录: {work_dir}")
        print(f"{'='*80}\n")
        
        try:
            # 步骤1: 使用docling扫描文献
            html_content = self._step1_docling_scan(pdf_path, work_dir)
            if not html_content:
                return None
            
            # 步骤2: 清洗HTML
            cleaned_html = self._step2_clean_html(html_content, work_dir)
            if not cleaned_html:
                return None
            
            # 步骤3: 转换为markdown
            markdown_content = self._step3_convert_to_markdown(cleaned_html, work_dir)
            if not markdown_content:
                return None
            
            # 步骤4: 实体识别和关系抽取
            knowledge_graph = self._step4_entity_extraction(markdown_content, work_dir)
            if not knowledge_graph:
                return None
            
            # 步骤5: 导入Neo4j
            success = self._step5_import_to_neo4j(knowledge_graph, work_dir)
            if not success:
                print("警告：Neo4j导入失败，但其他步骤已完成")
            
            print(f"\n{'='*80}")
            print(f"✓ 文档处理完成: {doc_name}")
            print(f"✓ 所有文件已保存到: {work_dir}")
            print(f"{'='*80}\n")
            
            return str(work_dir)
            
        except Exception as e:
            print(f"\n✗ 处理文档时发生错误: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _step1_docling_scan(self, pdf_path: Path, work_dir: Path) -> Optional[str]:
        """步骤1: 使用docling扫描文献并转换为HTML"""
        print("【步骤1/5】使用docling扫描文献...")
        
        try:
            converter = DocumentConverter()
            result = converter.convert(pdf_path)
            html_content = result.document.export_to_html()
            
            # 保存原始HTML
            html_path = work_dir / "01_raw.html"
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            print(f"  ✓ HTML已生成并保存: {html_path.name}")
            print(f"  ✓ HTML大小: {len(html_content)} 字符\n")
            
            return html_content
            
        except Exception as e:
            print(f"  ✗ Docling扫描失败: {e}\n")
            return None
    
    def _step2_clean_html(self, html_content: str, work_dir: Path) -> Optional[str]:
        """步骤2: 清洗HTML"""
        print("【步骤2/5】清洗HTML...")
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 2.1 删除DOI及之前的所有p标签（仅在前2000字符中查找DOI）
            # 首先获取文档前2000个字符的文本内容
            full_text = soup.get_text()
            first_2000_chars = full_text[:2000]
            
            # 检查前2000个字符中是否包含DOI
            if 'DOI:' in first_2000_chars or 'doi:' in first_2000_chars.lower():
                print(f"  • 在前2000个字符中检测到DOI，开始查找并删除...")
                all_p_tags = soup.find_all('p')
                doi_index = -1
                
                for i, p in enumerate(all_p_tags):
                    p_text = p.get_text()
                    if 'DOI:' in p_text or 'doi:' in p_text.lower():
                        doi_index = i
                        print(f"  • 找到DOI标签，位置: 第{i}个p标签")
                        break
                
                if doi_index >= 0:
                    for i in range(doi_index + 1):
                        all_p_tags[i].decompose()
                    print(f"  ✓ 已删除前 {doi_index + 1} 个p标签（DOI及之前的内容）")
                else:
                    print(f"  • DOI关键字存在但未在p标签中找到，跳过删除")
            else:
                print(f"  • 前2000个字符中未检测到DOI，跳过DOI删除步骤")
            
            # 2.2 删除参考文献及之后的所有内容（增强版）
            # 定义多种可能的参考文献关键词（包括中英文、繁体、各种变体）
            reference_keywords = [
                '参考文献', '参考资料', '参考文獻', '引用文献', '文献引用',
                'References', 'Reference', 'REFERENCES', 'REFERENCE',
                '參考文獻', '引用', '文献', '参考'
            ]
            
            reference_tag = None
            found_keyword = None
            
            # 在更多类型的标签中查找参考文献
            for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'div', 'section']):
                # 获取标签文本，去除所有空白字符
                clean_text = re.sub(r'\s+', '', tag.get_text())
                
                # 遍历所有可能的参考文献关键词
                for keyword in reference_keywords:
                    # 去除关键词中的空格进行匹配
                    keyword_no_space = re.sub(r'\s+', '', keyword)
                    
                    # 检查是否包含关键词（不区分大小写）
                    if keyword_no_space.lower() in clean_text.lower():
                        # 额外检查：确保是标题性质的内容（字符数较少）
                        # 避免误删正文中提到"参考某文献"的段落
                        if len(clean_text) <= 50:  # 参考文献标题通常很短
                            reference_tag = tag
                            found_keyword = keyword
                            print(f"  • 找到参考文献标签: {tag.name}, 关键词: '{found_keyword}', 内容: '{clean_text[:30]}'")
                            break
                
                if reference_tag:
                    break
            
            # 如果找到参考文献标签，删除它及其后面的所有内容
            if reference_tag:
                deleted_count = 0
                # 删除该标签之后的所有兄弟节点
                for sibling in list(reference_tag.next_siblings):
                    if hasattr(sibling, 'decompose'):
                        sibling.decompose()
                        deleted_count += 1
                # 删除参考文献标签本身
                reference_tag.decompose()
                deleted_count += 1
                print(f"  ✓ 已删除参考文献及之后的内容（共删除 {deleted_count} 个节点）")
            else:
                print(f"  • 未找到参考文献标记，尝试通过参考文献列表特征识别...")
                
                # 备用方案：通过参考文献列表的特征识别
                # 特征：连续出现多个以[数字]开头的段落
                all_remaining_tags = soup.find_all(['p', 'div'])
                reference_list_start = None
                
                for i, tag in enumerate(all_remaining_tags):
                    text = tag.get_text().strip()
                    # 检查是否以[1]、[2]等编号开头，或者1.、2.等格式
                    if re.match(r'^\[\d+\]', text) or re.match(r'^\d+\.', text):
                        # 检查后续是否有连续的编号（至少3个连续的才认为是参考文献列表）
                        consecutive_count = 1
                        for j in range(i + 1, min(i + 10, len(all_remaining_tags))):
                            next_text = all_remaining_tags[j].get_text().strip()
                            if re.match(r'^\[\d+\]', next_text) or re.match(r'^\d+\.', next_text):
                                consecutive_count += 1
                            else:
                                break
                        
                        if consecutive_count >= 3:  # 至少3个连续编号
                            reference_list_start = tag
                            print(f"  • 通过编号列表特征识别到参考文献（连续{consecutive_count}个编号）")
                            print(f"    起始内容: '{text[:50]}'")
                            break
                
                # 如果找到参考文献列表，删除从该位置开始的所有内容
                if reference_list_start:
                    deleted_count = 0
                    # 删除该标签及其后面的所有兄弟节点
                    for sibling in list(reference_list_start.next_siblings):
                        if hasattr(sibling, 'decompose'):
                            sibling.decompose()
                            deleted_count += 1
                    reference_list_start.decompose()
                    deleted_count += 1
                    print(f"  ✓ 已删除识别到的参考文献列表及之后内容（共删除 {deleted_count} 个节点）")
                else:
                    print(f"  • 未能识别参考文献区域，保留所有内容")
            
            # 2.3 删除所有table标签
            tables = soup.find_all('table')
            for table in tables:
                table.decompose()
            print(f"  ✓ 已删除 {len(tables)} 个table标签")
            
            # 2.4 去除所有p标签内部的空格、换行符以及[]符号及其内容
            p_tags = soup.find_all('p')
            for p in p_tags:
                text = p.get_text()
                text = re.sub(r'\[.*?\]', '', text)  # 去除[]及内容
                cleaned_text = re.sub(r'\s+', '', text)  # 去除空格和换行符
                p.string = cleaned_text
            
            print(f"  ✓ 已处理 {len(p_tags)} 个p标签，去除空格、换行符和[]符号")
            
            # 保存清洗后的HTML
            cleaned_html = str(soup)
            cleaned_html_path = work_dir / "02_cleaned.html"
            with open(cleaned_html_path, 'w', encoding='utf-8') as f:
                f.write(cleaned_html)
            
            print(f"  ✓ 清洗后的HTML已保存: {cleaned_html_path.name}\n")
            
            return cleaned_html
            
        except Exception as e:
            print(f"  ✗ HTML清洗失败: {e}\n")
            return None
    
    def _step3_convert_to_markdown(self, html_content: str, work_dir: Path) -> Optional[str]:
        """步骤3: 转换为markdown"""
        print("【步骤3/5】转换为markdown...")
        
        try:
            h = html2text.HTML2Text()
            h.ignore_links = False
            h.ignore_images = False
            h.body_width = 0  # 不限制宽度
            
            markdown_content = h.handle(html_content)
            
            # 保存markdown
            markdown_path = work_dir / "03_document.md"
            with open(markdown_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            print(f"  ✓ Markdown已生成并保存: {markdown_path.name}")
            print(f"  ✓ Markdown大小: {len(markdown_content)} 字符\n")
            
            return markdown_content
            
        except Exception as e:
            print(f"  ✗ Markdown转换失败: {e}\n")
            return None
    
    def _step4_entity_extraction(self, markdown_content: str, work_dir: Path) -> Optional[Dict]:
        """步骤4: 实体识别和关系抽取"""
        print("【步骤4/5】实体识别和关系抽取...")
        print("  （这可能需要几分钟，请耐心等待）\n")
        
        try:
            # 创建提取Prompt
            extraction_prompt = ChatPromptTemplate.from_messages([
                ("system", """你是一个专业的医学知识图谱构建专家。你的任务是从医学文本中提取结构化的实体和关系。

**实体类型定义：**
- Disease（疾病）：各种疾病名称，包括主要疾病和特殊类型
- Symptom（症状）：临床症状和体征
- Test（检查方法）：诊断检查和评分系统
- Treatment（治疗方法）：治疗手段和药物
- Pathogen（病原体）：致病微生物
- RiskFactor（风险因素）：**必须提取具体的、细粒度的风险因素**，包括：
  * 具体的年龄段（如：高龄/年龄≥60岁）
  * 具体的疾病史（如：糖尿病、慢性肝病、慢性肾病，不要概括为"慢性疾病"）
  * 具体的生活习惯（如：酗酒、吸烟）
  * 具体的身体状况（如：肥胖、营养不良、免疫功能低下）
  * 具体的用药史（如：使用免疫抑制剂、长期使用激素）
  * 具体的其他因素（如：长期卧床、外伤史、手术史）
  **禁止**：不要将多个具体因素概括为笼统的类别（如将糖尿病、慢性肝病概括为"慢性疾病"）
- DifferentialDiagnosis（鉴别诊断）：需要鉴别的其他疾病

**注意**：不要提取文献来源、作者姓名、单位名称等元信息，系统会自动处理这些信息。

**关系类型定义：**
- HAS_SYMPTOM：疾病具有某种症状
- DIAGNOSED_BY：疾病通过某种方法诊断
- TREATED_WITH：疾病使用某种方法治疗
- CAUSED_BY：疾病由某种病原体引起
- HAS_RISK_FACTOR：疾病具有某种风险因素
- DIFFERENTIAL_DIAGNOSIS：疾病需要与某疾病鉴别

**注意**：SOURCE_FROM关系会由系统自动创建，不需要手动提取。

**提取要求：**
1. 仔细阅读文本，识别所有相关实体
2. **重要**：同一实体的中英文名称、缩写应识别为同一个实体，优先使用中文全称作为实体名称
   - 例如："坏死性软组织感染"、"NSTIs"、"Necrotizing soft tissue infections"是同一个疾病
   - 实体name字段使用中文全称，在description字段中必须注明所有别名："英文名：XXX，缩写：XXX"
3. **识别别名**：在整个文本中，无论出现中文全称、英文名称还是缩写，都必须识别为同一个实体
   - 例如：文中出现"NSTIs的症状包括..."，应识别"坏死性软组织感染"是source实体
   - 例如：文中出现"MRSA导致..."，应识别"耐甲氧西林金黄色葡萄球菌"是source实体
   - **关键**：在relationships中的source和target字段，无论原文使用什么名称，都必须统一使用中文全称
4. **别名映射常见示例**：
   - "坏死性软组织感染" = "NSTIs" = "Necrotizing soft tissue infections"
   - "耐甲氧西林金黄色葡萄球菌" = "MRSA" = "methicillin-resistant Staphylococcus aureus"
   - "A族溶血性链球菌" = "GAS" = "group A Streptococcus"
5. **风险因素提取要求**（重要！）：
   - 必须提取每一个具体的风险因素，不要合并或概括
   - 例如：看到"糖尿病、慢性肝病、慢性肾病"，应提取3个RiskFactor实体，而非1个"慢性疾病"
   - 例如：看到"高龄（年龄≥60岁）"，应提取为"高龄（年龄≥60岁）"，保留具体信息
   - 对于并列列举的风险因素，每个都要单独提取
   - **正确示例**：
     文本："易患人群包括高龄（年龄≥60岁）、酗酒、肥胖、糖尿病、慢性肝病、慢性肾病、使用免疫抑制剂"
     应提取7个RiskFactor：高龄（年龄≥60岁）、酗酒、肥胖、糖尿病、慢性肝病、慢性肾病、使用免疫抑制剂
   - **错误示例**：
     ❌ 将"糖尿病、慢性肝病、慢性肾病"概括为1个"慢性疾病"
     ❌ 将"使用免疫抑制剂或免疫功能低下"只提取1个，应提取2个独立因素
6. 为每个实体提供简洁准确的描述，必须在描述中包含所有出现过的别名
7. 识别实体之间的关系，确保关系类型正确
8. 保持专业术语的准确性
9. 输出必须是有效的JSON格式
"""),
                ("user", """请从以下医学文本中提取实体和关系：

{text}

请按照以下JSON格式输出：
{format_instructions}
""")
            ])
            
            # 创建输出解析器
            parser = JsonOutputParser(pydantic_object=KnowledgeGraph)
            
            # 创建抽取链
            extraction_chain = extraction_prompt | self.llm | parser
            
            # 文档分块
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                separators=["\n## ", "\n### ", "\n", " ", ""]
            )
            
            chunks = text_splitter.split_text(markdown_content)
            print(f"  • 文档已分成 {len(chunks)} 个块\n")
            
            # 存储所有抽取结果
            all_entities = []
            all_relationships = []
            
            # 对每个块进行抽取
            for i, chunk in enumerate(chunks):
                print(f"  处理第 {i+1}/{len(chunks)} 块...")
                
                try:
                    result = extraction_chain.invoke({
                        "text": chunk,
                        "format_instructions": parser.get_format_instructions()
                    })
                    
                    if 'entities' in result:
                        all_entities.extend(result['entities'])
                        print(f"    ✓ 提取了 {len(result['entities'])} 个实体")
                    
                    if 'relationships' in result:
                        all_relationships.extend(result['relationships'])
                        print(f"    ✓ 提取了 {len(result['relationships'])} 个关系")
                    
                    time.sleep(self.request_interval)  # 避免请求过快
                    
                except Exception as e:
                    print(f"    ✗ 处理第 {i+1} 块时出错: {str(e)}")
                    continue
            
            # 实体去重（添加数据验证）
            unique_entities = {}
            invalid_entities = []
            
            for entity in all_entities:
                # 验证实体是否包含必需字段
                if not isinstance(entity, dict):
                    invalid_entities.append(("非字典类型", entity))
                    continue
                
                # 检查必需字段
                if 'name' not in entity or 'entity_type' not in entity:
                    invalid_entities.append(("缺少必需字段", entity))
                    continue
                
                # 检查字段值是否有效
                if not entity['name'] or not entity['entity_type']:
                    invalid_entities.append(("字段值为空", entity))
                    continue
                
                # 过滤掉LiteratureSource类型（文献来源由系统自动添加）
                if entity['entity_type'] == 'LiteratureSource':
                    continue
                
                key = (entity['name'], entity['entity_type'])
                if key not in unique_entities:
                    unique_entities[key] = entity
                else:
                    # 保留描述更详细的版本
                    current_desc_len = len(entity.get('description', ''))
                    existing_desc_len = len(unique_entities[key].get('description', ''))
                    if current_desc_len > existing_desc_len:
                        unique_entities[key] = entity
            
            unique_entities_list = list(unique_entities.values())
            
            # 报告无效实体
            if invalid_entities:
                print(f"  ⚠ 发现 {len(invalid_entities)} 个无效实体已忽略")
                for reason, entity_data in invalid_entities[:3]:  # 只显示前3个
                    print(f"    - 原因: {reason}, 数据: {entity_data}")
            
            # 关系去重（添加数据验证）
            unique_relationships = {}
            invalid_relationships = []
            
            for rel in all_relationships:
                # 验证关系是否包含必需字段
                if not isinstance(rel, dict):
                    invalid_relationships.append(("非字典类型", rel))
                    continue
                
                # 检查必需字段
                if 'source' not in rel or 'target' not in rel or 'relation_type' not in rel:
                    invalid_relationships.append(("缺少必需字段", rel))
                    continue
                
                # 检查字段值是否有效
                if not rel['source'] or not rel['target'] or not rel['relation_type']:
                    invalid_relationships.append(("字段值为空", rel))
                    continue
                
                # 过滤掉SOURCE_FROM关系（文献来源关系由系统自动添加）
                if rel['relation_type'] == 'SOURCE_FROM':
                    continue
                
                key = (rel['source'], rel['target'], rel['relation_type'])
                if key not in unique_relationships:
                    unique_relationships[key] = rel
            
            unique_relationships_list = list(unique_relationships.values())
            
            # 报告无效关系
            if invalid_relationships:
                print(f"  ⚠ 发现 {len(invalid_relationships)} 个无效关系已忽略")
                for reason, rel_data in invalid_relationships[:3]:  # 只显示前3个
                    print(f"    - 原因: {reason}, 数据: {rel_data}")
            
            print(f"\n  ✓ 去重后: {len(unique_entities_list)} 个实体, {len(unique_relationships_list)} 个关系")
            
            # 统计各类实体数量
            entity_type_counts = {}
            for entity in unique_entities_list:
                entity_type = entity['entity_type']
                entity_type_counts[entity_type] = entity_type_counts.get(entity_type, 0) + 1
            
            print(f"\n  各类实体数量：")
            for entity_type, count in sorted(entity_type_counts.items()):
                print(f"    - {entity_type}: {count}")
            
            # 保存知识图谱JSON
            output_data = {
                "entities": unique_entities_list,
                "relationships": unique_relationships_list,
                "metadata": {
                    "extraction_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "entity_count": len(unique_entities_list),
                    "relationship_count": len(unique_relationships_list),
                    "entity_type_counts": entity_type_counts
                }
            }
            
            json_path = work_dir / "04_knowledge_graph.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            
            print(f"\n  ✓ 知识图谱已保存: {json_path.name}\n")
            
            return output_data
            
        except Exception as e:
            print(f"  ✗ 实体抽取失败: {e}\n")
            import traceback
            traceback.print_exc()
            return None
    
    def _step5_import_to_neo4j(self, knowledge_graph: Dict, work_dir: Path) -> bool:
        """步骤5: 导入Neo4j"""
        print("【步骤5/5】导入Neo4j...")
        
        try:
            # 连接到Neo4j
            graph = Graph(self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password))
            print(f"  ✓ 已连接到Neo4j数据库")
            
            # 获取文档名称（从工作目录名称）
            document_name = work_dir.name
            print(f"  • 文档名称: {document_name}")
            
            # 创建节点映射
            node_map = {}
            
            # 1. 首先创建文献来源节点（基于文档名称，而非LLM抽取）
            literature_node = Node(
                "LiteratureSource",
                name=document_name,
                description=f"医学文献：{document_name}",
                source_type="clinical_consensus",  # 可以根据文档类型调整
                import_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            graph.merge(literature_node, "LiteratureSource", "name")  # 使用merge避免重复
            node_map[document_name] = literature_node
            print(f"  ✓ 已创建/更新文献来源节点: {document_name}")
            
            # 2. 创建实体节点
            entities = knowledge_graph['entities']
            print(f"  • 正在创建 {len(entities)} 个实体节点...")
            
            for entity in entities:
                node = Node(
                    entity['entity_type'],
                    name=entity['name'],
                    description=entity['description']
                )
                graph.create(node)
                node_map[entity['name']] = node
            
            print(f"  ✓ 已创建 {len(entities)} 个实体节点")
            
            # 3. 只为Disease类型的实体创建到文献来源的关系
            print(f"  • 正在为Disease节点创建到文献来源的关系...")
            source_relations_count = 0
            for entity in entities:
                # 只有Disease类型才创建SOURCE_FROM关系
                if entity['entity_type'] == 'Disease':
                    entity_node = node_map.get(entity['name'])
                    if entity_node:
                        source_relation = Relationship(
                            entity_node,
                            "SOURCE_FROM",
                            literature_node,
                            description=f"该疾病来源于文献《{document_name}》"
                        )
                        graph.create(source_relation)
                        source_relations_count += 1
            
            print(f"  ✓ 已创建 {source_relations_count} 个Disease->LiteratureSource关系")
            
            # 4. 创建实体间的关系
            relationships = knowledge_graph['relationships']
            print(f"  • 正在创建 {len(relationships)} 个实体间关系...")
            
            created_relations = 0
            for rel in relationships:
                source_node = node_map.get(rel['source'])
                target_node = node_map.get(rel['target'])
                
                if source_node and target_node:
                    relationship = Relationship(
                        source_node,
                        rel['relation_type'],
                        target_node,
                        description=rel.get('description', '')
                    )
                    graph.create(relationship)
                    created_relations += 1
            
            print(f"  ✓ 已创建 {created_relations} 个实体间关系")
            print(f"\n  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print(f"  ✓ 知识图谱导入成功！")
            print(f"    - 文献来源: 1个")
            print(f"    - 实体节点: {len(entities)}个")
            print(f"    - 来源关系: {source_relations_count}个")
            print(f"    - 实体关系: {created_relations}个")
            print(f"  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
            
            return True
            
        except Exception as e:
            print(f"  ✗ Neo4j导入失败: {e}")
            print(f"  提示：请确保Neo4j服务已启动，且连接配置正确\n")
            import traceback
            traceback.print_exc()
            return False


def main():
    """主函数：演示如何使用工作流"""
    
    # 创建工作流实例（使用config.py中的配置）
    workflow = KnowledgeWorkflow()
    
    # 示例：处理一个PDF文档
    pdf_path = r"O:\MyProject\RAG\DB\uploads\坏死性软组织感染临床诊治急诊专家共识.pdf"
    
    result = workflow.process_document(pdf_path)
    
    if result:
        print(f"\n✓ 工作流执行成功！")
        print(f"✓ 结果保存在: {result}")
    else:
        print(f"\n✗ 工作流执行失败！")


if __name__ == "__main__":
    main()

