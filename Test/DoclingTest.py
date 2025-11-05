"""该文件使用docling对文档进行扫描并且转为markdown文件"""

import warnings
from docling.document_converter import DocumentConverter

# 屏蔽 Pydantic 的 UserWarning
warnings.filterwarnings("ignore", category=UserWarning)

# 你的 PDF 路径
pdf_path = r"O:\MyProject\RAG\DB\uploads\坏死性软组织感染临床诊治急诊专家共识.pdf"

# 输出到 Test 文件夹的四个不同结果文件路径
md_path = r"O:\MyProject\Test\output_markdown.md"
doctags_path = r"O:\MyProject\Test\output_doctags.txt"
html_path = r"O:\MyProject\Test\output.html"
tree_path = r"O:\MyProject\Test\output_element_tree.txt"

def main():
    # 创建 Docling 转换器
    converter = DocumentConverter()

    # 转换 PDF
    result = converter.convert(pdf_path)

    # 导出四种不同格式
    markdown_text = result.document.export_to_markdown()
    doctags_text = result.document.export_to_doctags()
    html_text = result.document.export_to_html()
    element_tree_text = result.document.export_to_element_tree()

    # 打印一部分内容（Markdown 格式）
    print("=== 提取的 Markdown 内容 (前500字符) ===")
    print(markdown_text[:500])  
    print("\n=== 已保存四个文件到 Test 文件夹 ===")
    print("1) output_markdown.md (Markdown)")
    print("2) output_doctags.txt (Doctags)")
    print("3) output.html (HTML)")
    print("4) output_element_tree.txt (Element Tree)")

    # 保存四个不同结果到 Test 文件夹
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown_text)
    with open(doctags_path, "w", encoding="utf-8") as f:
        f.write(doctags_text)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_text)
    with open(tree_path, "w", encoding="utf-8") as f:
        f.write(element_tree_text)

if __name__ == "__main__":
    main()