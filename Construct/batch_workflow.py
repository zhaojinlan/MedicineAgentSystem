"""
批量处理知识图谱工作流

使用方法：
    python batch_workflow.py <PDF文件夹路径>
    
示例：
    python batch_workflow.py "O:\MyProject\RAG\DB\uploads"
"""

import sys
import os
from pathlib import Path
from knowledge_workflow import KnowledgeWorkflow


def main():
    """批量处理主函数"""
    
    print("=" * 80)
    print("知识图谱批量处理工作流")
    print("=" * 80)
    print()
    
    # 检查命令行参数
    if len(sys.argv) > 1:
        folder_path = sys.argv[1]
    else:
        # 交互式输入
        print("请输入包含PDF文件的文件夹路径（或直接回车使用默认路径）：")
        folder_path = input("> ").strip()
        
        if not folder_path:
            # 使用默认文件夹
            folder_path = r"O:\MyProject\RAG\DB\uploads"
            print(f"使用默认文件夹: {folder_path}")
    
    # 检查文件夹是否存在
    folder_path = Path(folder_path)
    if not folder_path.exists():
        print(f"\n✗ 错误：文件夹不存在 - {folder_path}")
        sys.exit(1)
    
    # 查找所有PDF文件
    pdf_files = list(folder_path.glob("*.pdf"))
    
    if not pdf_files:
        print(f"\n✗ 错误：文件夹中没有找到PDF文件 - {folder_path}")
        sys.exit(1)
    
    print(f"\n找到 {len(pdf_files)} 个PDF文件：")
    for i, pdf in enumerate(pdf_files, 1):
        print(f"  {i}. {pdf.name}")
    print()
    
    # 创建工作流实例（使用config.py中的配置）
    workflow = KnowledgeWorkflow()
    
    # 处理每个PDF文件
    success_count = 0
    failed_files = []
    
    for i, pdf_path in enumerate(pdf_files, 1):
        print(f"\n{'='*80}")
        print(f"处理文件 {i}/{len(pdf_files)}: {pdf_path.name}")
        print(f"{'='*80}\n")
        
        result = workflow.process_document(str(pdf_path))
        
        if result:
            success_count += 1
            print(f"\n✓ [{i}/{len(pdf_files)}] 成功: {pdf_path.name}")
        else:
            failed_files.append(pdf_path.name)
            print(f"\n✗ [{i}/{len(pdf_files)}] 失败: {pdf_path.name}")
        
        print(f"\n当前进度: {success_count}/{i} 成功")
    
    # 最终总结
    print(f"\n{'='*80}")
    print(f"批量处理完成")
    print(f"{'='*80}")
    print(f"\n总文件数: {len(pdf_files)}")
    print(f"成功: {success_count}")
    print(f"失败: {len(failed_files)}")
    
    if failed_files:
        print(f"\n失败的文件：")
        for filename in failed_files:
            print(f"  - {filename}")
    
    print(f"\n所有结果已保存到: O:\\MyProject\\Knowledges")


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

