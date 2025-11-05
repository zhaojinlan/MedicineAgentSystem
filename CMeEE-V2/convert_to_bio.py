"""
CMeEE-V2数据集转换脚本
将JSON格式转换为BIO格式，用于NER模型训练
"""

import json
from collections import Counter
from typing import List, Dict, Tuple
import os


def convert_to_bio(text: str, entities: List[Dict], strategy: str = 'longest') -> List[str]:
    """
    将span格式的实体转换为BIO标注格式
    
    Args:
        text: 原始文本
        entities: 实体列表 [{start_idx, end_idx, type, entity}, ...]
        strategy: 处理嵌套实体的策略
            - 'longest': 保留最长的实体（推荐）
            - 'first': 按出现顺序，先标注的优先
    
    Returns:
        BIO标签列表，与text中的字符一一对应
    """
    # 初始化所有位置为 O
    labels = ['O'] * len(text)
    
    if not entities:
        return labels
    
    # 处理嵌套：按长度降序排序，优先处理长实体
    if strategy == 'longest':
        entities_sorted = sorted(
            entities, 
            key=lambda x: x['end_idx'] - x['start_idx'], 
            reverse=True
        )
    else:
        entities_sorted = entities
    
    # 标注实体
    for entity in entities_sorted:
        start = entity['start_idx']
        end = entity['end_idx']
        ent_type = entity['type']
        
        # 检查起始位置是否已被标注
        if labels[start] == 'O':
            # 标注开始位置
            labels[start] = f'B-{ent_type}'
            
            # 标注内部位置
            for i in range(start + 1, end):
                if labels[i] == 'O':  # 只标注未被占用的位置
                    labels[i] = f'I-{ent_type}'
    
    return labels


def convert_dataset(data: List[Dict]) -> List[Dict]:
    """
    批量转换整个数据集
    
    Returns:
        转换后的数据，格式：[{"text": str, "labels": List[str], "entities": List[Dict]}, ...]
    """
    converted_data = []
    
    for item in data:
        text = item['text']
        entities = item.get('entities', [])
        labels = convert_to_bio(text, entities)
        
        converted_data.append({
            'text': text,
            'labels': labels,
            'entities': entities  # 保留原始实体信息，方便验证
        })
    
    return converted_data


def get_label_list(data: List[Dict]) -> List[str]:
    """获取所有唯一标签的列表"""
    labels = set()
    for item in data:
        labels.update(item['labels'])
    
    # 排序，确保O在第一位
    label_list = sorted(list(labels))
    if 'O' in label_list:
        label_list.remove('O')
        label_list = ['O'] + label_list
    
    return label_list


def analyze_dataset(data: List[Dict], name: str = "数据集"):
    """分析数据集统计信息"""
    print(f"\n{'='*60}")
    print(f"{name} 统计信息")
    print('='*60)
    
    # 基本统计
    print(f"样本数: {len(data)}")
    
    # 实体类型统计
    entity_types = Counter()
    total_entities = 0
    text_lengths = []
    
    for item in data:
        text_lengths.append(len(item['text']))
        entities = item.get('entities', [])
        total_entities += len(entities)
        for ent in entities:
            entity_types[ent['type']] += 1
    
    print(f"总实体数: {total_entities}")
    print(f"\n实体类型分布:")
    for ent_type, count in entity_types.most_common():
        percentage = count / total_entities * 100 if total_entities > 0 else 0
        print(f"  {ent_type:6s}: {count:6d} ({percentage:5.2f}%)")
    
    # 文本长度统计
    if text_lengths:
        print(f"\n文本长度:")
        print(f"  平均: {sum(text_lengths) / len(text_lengths):.1f} 字符")
        print(f"  最短: {min(text_lengths)}, 最长: {max(text_lengths)}")
        print(f"  中位数: {sorted(text_lengths)[len(text_lengths)//2]}")


def check_nested_entities(data: List[Dict]) -> int:
    """检查嵌套实体数量"""
    nested_count = 0
    
    for item in data:
        entities = item.get('entities', [])
        if len(entities) < 2:
            continue
        
        for i in range(len(entities)):
            for j in range(i+1, len(entities)):
                e1, e2 = entities[i], entities[j]
                # 检查是否重叠
                if not (e1['end_idx'] <= e2['start_idx'] or e2['end_idx'] <= e1['start_idx']):
                    nested_count += 1
    
    return nested_count


def main():
    print("="*60)
    print("CMeEE-V2 数据集转换工具")
    print("JSON格式 → BIO格式")
    print("="*60)
    
    # 1. 加载原始数据
    print("\n[1/6] 加载数据...")
    
    # 使用绝对路径
    base_dir = r'O:\MyProject\CMeEE-V2'
    
    with open(os.path.join(base_dir, 'CMeEE-V2_train.json'), 'r', encoding='utf-8') as f:
        train_data = json.load(f)
    
    with open(os.path.join(base_dir, 'CMeEE-V2_dev.json'), 'r', encoding='utf-8') as f:
        dev_data = json.load(f)
    
    with open(os.path.join(base_dir, 'CMeEE-V2_test.json'), 'r', encoding='utf-8') as f:
        test_data = json.load(f)
    
    print(f"✅ 训练集: {len(train_data)} 条")
    print(f"✅ 验证集: {len(dev_data)} 条")
    print(f"✅ 测试集: {len(test_data)} 条")
    
    # 2. 分析原始数据
    print("\n[2/6] 分析原始数据...")
    analyze_dataset(train_data, "训练集")
    
    # 检查嵌套实体
    nested_count = check_nested_entities(train_data)
    print(f"\n⚠️  检测到 {nested_count} 个嵌套/重叠实体对")
    print("   (将保留最长的实体)")
    
    # 3. 转换为BIO格式
    print("\n[3/6] 转换为BIO格式...")
    train_bio = convert_dataset(train_data)
    dev_bio = convert_dataset(dev_data)
    test_bio = convert_dataset(test_data)
    print("✅ 转换完成")
    
    # 4. 生成标签映射
    print("\n[4/6] 生成标签映射...")
    label_list = get_label_list(train_bio)
    label2id = {label: idx for idx, label in enumerate(label_list)}
    id2label = {idx: label for label, idx in label2id.items()}
    
    print(f"✅ 共有 {len(label_list)} 个不同的标签:")
    for label in label_list[:10]:  # 只显示前10个
        print(f"   {label}")
    if len(label_list) > 10:
        print(f"   ... (共{len(label_list)}个)")
    
    # 5. 保存转换后的数据
    print("\n[5/6] 保存文件...")
    
    # 保存BIO格式数据
    with open(os.path.join(base_dir, 'CMeEE-V2_train_bio.json'), 'w', encoding='utf-8') as f:
        json.dump(train_bio, f, ensure_ascii=False, indent=2)

    with open(os.path.join(base_dir, 'CMeEE-V2_dev_bio.json'), 'w', encoding='utf-8') as f:
        json.dump(dev_bio, f, ensure_ascii=False, indent=2)
    
    with open(os.path.join(base_dir, 'CMeEE-V2_test_bio.json'), 'w', encoding='utf-8') as f:
        json.dump(test_bio, f, ensure_ascii=False, indent=2)
    
    # 保存标签映射
    with open(os.path.join(base_dir, 'label2id.json'), 'w', encoding='utf-8') as f:
        json.dump(label2id, f, ensure_ascii=False, indent=2)
    
    with open(os.path.join(base_dir, 'id2label.json'), 'w', encoding='utf-8') as f:
        json.dump(id2label, f, ensure_ascii=False, indent=2)
    
    print("✅ CMeEE-V2_train_bio.json")
    print("✅ CMeEE-V2_dev_bio.json")
    print("✅ CMeEE-V2_test_bio.json")
    print("✅ label2id.json")
    print("✅ id2label.json")
    
    # 6. 验证转换
    print("\n[6/6] 验证转换...")
    errors = 0
    for orig, bio in zip(train_data[:100], train_bio[:100]):
        if len(bio['text']) != len(bio['labels']):
            errors += 1
    
    if errors == 0:
        print("✅ 验证通过！所有文本和标签长度匹配")
    else:
        print(f"⚠️  发现 {errors} 个长度不匹配的样本")
    
    # 显示一个转换示例
    print("\n" + "="*60)
    print("转换示例")
    print("="*60)
    sample = train_bio[0]
    print(f"\n文本: {sample['text'][:60]}{'...' if len(sample['text']) > 60 else ''}")
    print(f"\n前20个字符的标注:")
    for i in range(min(20, len(sample['text']))):
        print(f"  {sample['text'][i]} → {sample['labels'][i]}")
    
    print("\n" + "="*60)
    print("转换完成！")
    print("="*60)
    print("\n接下来你可以:")
    print("  1. 使用这些BIO格式文件进行模型训练")
    print("  2. 结合BERT tokenizer进一步处理")
    print("  3. 构建PyTorch Dataset")


if __name__ == '__main__':
    main()

