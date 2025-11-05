"""
患者数据模型 - 使用Pydantic进行结构化数据管理
每个患者的数据保存为独立的JSON文件
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import json
import os
from pathlib import Path


# ============================================================================
# Pydantic 模型定义
# ============================================================================

class TriageInfo(BaseModel):
    """分诊信息"""
    triage_level: Optional[str] = Field(None, description="分诊级别，如 I级、II级等")
    recommended_department: Optional[str] = Field(None, description="建议科室")
    triage_basis: Optional[str] = Field(None, description="分诊依据")
    triage_time: Optional[str] = Field(None, description="分诊时间")
    triage_questions: Optional[str] = Field(None, description="分诊时提出的问题")


class DiagnosisInfo(BaseModel):
    """诊断信息"""
    most_likely_disease: Optional[str] = Field(None, description="最可能的疾病")
    confidence: Optional[float] = Field(None, description="置信度（百分比）")
    disease_details: Optional[Dict[str, Any]] = Field(None, description="所有疾病的详细信息")
    recommended_tests: Optional[List[Dict[str, Any]]] = Field(None, description="推荐的检查方法，包含test_name、test_description、selected、result等字段")
    submitted_tests: Optional[List[Dict[str, Any]]] = Field(None, description="已提交的检查及结果，每个检查包含test_name、test_description、result")
    diagnosis_time: Optional[str] = Field(None, description="诊断时间")


class ExpertConsultation(BaseModel):
    """专家会诊信息"""
    consultation_date: Optional[str] = Field(None, description="会诊日期")
    diagnostic_expert_opinion: Optional[str] = Field(None, description="诊断专家意见")
    imaging_expert_opinion: Optional[str] = Field(None, description="影像专家意见")
    treatment_expert_opinion: Optional[str] = Field(None, description="治疗专家意见")
    final_diagnosis: Optional[str] = Field(None, description="最终诊断")
    treatment_plan: Optional[str] = Field(None, description="治疗方案")
    prognosis: Optional[str] = Field(None, description="预后评估")


class PatientData(BaseModel):
    """患者完整数据模型"""
    patient_id: str = Field(..., description="患者唯一标识符（UUID）")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="创建时间")
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="最后更新时间")
    
    # 患者基本信息
    patient_name: Optional[str] = Field(None, description="患者姓名")
    patient_age: Optional[int] = Field(None, description="患者年龄")
    patient_gender: Optional[str] = Field(None, description="患者性别")
    initial_symptoms: Optional[str] = Field(None, description="初始症状描述")
    patient_history: Optional[str] = Field(None, description="患者病史")
    test_results: Optional[str] = Field(None, description="检查结果")
    
    # 各节点的结构化数据
    triage_info: Optional[TriageInfo] = Field(None, description="分诊信息")
    diagnosis_info: Optional[DiagnosisInfo] = Field(None, description="诊断信息")
    expert_consultation: Optional[ExpertConsultation] = Field(None, description="专家会诊信息")
    
    # 对话历史
    conversation_history: List[Dict[str, str]] = Field(default_factory=list, description="对话历史记录")
    
    class Config:
        json_schema_extra = {
            "example": {
                "patient_id": "550e8400-e29b-41d4-a716-446655440000",
                "created_at": "2025-10-20T10:00:00",
                "initial_symptoms": "患者皮肤红肿、发热、气促",
                "triage_info": {
                    "triage_level": "III级（紧急）",
                    "recommended_department": "急诊内科",
                    "triage_basis": "患者出现发热及气促"
                }
            }
        }


# ============================================================================
# 患者数据管理类
# ============================================================================

class PatientDataManager:
    """患者数据管理器 - 负责保存和加载患者数据"""
    
    def __init__(self, data_dir: str = "patient_data"):
        """
        初始化患者数据管理器
        
        Args:
            data_dir: 患者数据存储目录
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
    
    def get_patient_file_path(self, patient_id: str) -> Path:
        """获取患者数据文件路径"""
        return self.data_dir / f"{patient_id}.json"
    
    def save_patient_data(self, patient_data: PatientData) -> bool:
        """
        保存患者数据到JSON文件
        
        Args:
            patient_data: 患者数据对象
            
        Returns:
            是否保存成功
        """
        try:
            # 更新时间戳
            patient_data.updated_at = datetime.now().isoformat()
            
            # 获取文件路径
            file_path = self.get_patient_file_path(patient_data.patient_id)
            
            # 保存为JSON（包含所有字段，即使是None）
            data_dict = patient_data.model_dump(mode='json', exclude_none=False)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data_dict, f, ensure_ascii=False, indent=2)
            
            print(f">>> 患者数据已保存: {file_path}")
            return True
            
        except Exception as e:
            print(f">>> 保存患者数据失败: {e}")
            return False
    
    def load_patient_data(self, patient_id: str) -> Optional[PatientData]:
        """
        从JSON文件加载患者数据
        
        Args:
            patient_id: 患者ID
            
        Returns:
            患者数据对象，如果不存在则返回None
        """
        try:
            file_path = self.get_patient_file_path(patient_id)
            
            if not file_path.exists():
                return None
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            return PatientData(**data)
            
        except Exception as e:
            print(f">>> 加载患者数据失败: {e}")
            return None
    
    def create_or_load_patient(self, patient_id: str) -> PatientData:
        """
        创建或加载患者数据
        
        Args:
            patient_id: 患者ID
            
        Returns:
            患者数据对象
        """
        # 尝试加载现有数据
        patient_data = self.load_patient_data(patient_id)
        
        # 如果不存在，创建新的患者数据
        if patient_data is None:
            patient_data = PatientData(patient_id=patient_id)
            print(f">>> 创建新患者记录: {patient_id}")
        else:
            print(f">>> 加载现有患者记录: {patient_id}")
        
        return patient_data
    
    def update_triage_info(self, patient_id: str, triage_level: str, 
                          recommended_department: str, triage_basis: str = "",
                          triage_questions: str = "") -> PatientData:
        """
        更新患者的分诊信息
        
        Args:
            patient_id: 患者ID
            triage_level: 分诊级别
            recommended_department: 建议科室
            triage_basis: 分诊依据
            triage_questions: 分诊问题
            
        Returns:
            更新后的患者数据
        """
        patient_data = self.create_or_load_patient(patient_id)
        
        patient_data.triage_info = TriageInfo(
            triage_level=triage_level,
            recommended_department=recommended_department,
            triage_basis=triage_basis,
            triage_time=datetime.now().isoformat(),
            triage_questions=triage_questions
        )
        
        self.save_patient_data(patient_data)
        return patient_data
    
    def update_diagnosis_info(self, patient_id: str, most_likely_disease: str,
                             confidence: float, disease_details: Dict[str, Any] = None,
                             recommended_tests: List[Dict[str, str]] = None) -> PatientData:
        """
        更新患者的诊断信息
        
        Args:
            patient_id: 患者ID
            most_likely_disease: 最可能的疾病
            confidence: 置信度
            disease_details: 疾病详情
            recommended_tests: 推荐检查
            
        Returns:
            更新后的患者数据
        """
        patient_data = self.create_or_load_patient(patient_id)
        
        patient_data.diagnosis_info = DiagnosisInfo(
            most_likely_disease=most_likely_disease,
            confidence=confidence,
            disease_details=disease_details or {},
            recommended_tests=recommended_tests or [],
            diagnosis_time=datetime.now().isoformat()
        )
        
        self.save_patient_data(patient_data)
        return patient_data
    
    def update_expert_consultation(self, patient_id: str, 
                                   diagnostic_opinion: str = "",
                                   imaging_opinion: str = "",
                                   treatment_opinion: str = "",
                                   final_diagnosis: str = "",
                                   treatment_plan: str = "",
                                   prognosis: str = "") -> PatientData:
        """
        更新专家会诊信息
        
        Args:
            patient_id: 患者ID
            diagnostic_opinion: 诊断专家意见
            imaging_opinion: 影像专家意见
            treatment_opinion: 治疗专家意见
            final_diagnosis: 最终诊断
            treatment_plan: 治疗方案
            prognosis: 预后评估
            
        Returns:
            更新后的患者数据
        """
        patient_data = self.create_or_load_patient(patient_id)
        
        patient_data.expert_consultation = ExpertConsultation(
            consultation_date=datetime.now().isoformat(),
            diagnostic_expert_opinion=diagnostic_opinion,
            imaging_expert_opinion=imaging_opinion,
            treatment_expert_opinion=treatment_opinion,
            final_diagnosis=final_diagnosis,
            treatment_plan=treatment_plan,
            prognosis=prognosis
        )
        
        self.save_patient_data(patient_data)
        return patient_data
    
    def add_conversation(self, patient_id: str, role: str, content: str) -> PatientData:
        """
        添加对话记录
        
        Args:
            patient_id: 患者ID
            role: 角色（user/assistant）
            content: 对话内容
            
        Returns:
            更新后的患者数据
        """
        patient_data = self.create_or_load_patient(patient_id)
        
        patient_data.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        
        self.save_patient_data(patient_data)
        return patient_data
    
    def update_patient_info(self, patient_id: str, **kwargs) -> PatientData:
        """
        更新患者基本信息
        
        Args:
            patient_id: 患者ID
            **kwargs: 要更新的字段
            
        Returns:
            更新后的患者数据
        """
        patient_data = self.create_or_load_patient(patient_id)
        
        for key, value in kwargs.items():
            if hasattr(patient_data, key):
                setattr(patient_data, key, value)
        
        self.save_patient_data(patient_data)
        return patient_data
    
    def submit_test_results(self, patient_id: str, submitted_tests: List[Dict[str, Any]]) -> PatientData:
        """
        提交检查结果
        
        Args:
            patient_id: 患者ID
            submitted_tests: 已提交的检查列表，每项包含 test_name、test_description 和 result
            
        Returns:
            更新后的患者数据
        """
        patient_data = self.create_or_load_patient(patient_id)
        
        # 确保诊断信息存在
        if patient_data.diagnosis_info is None:
            raise ValueError("患者尚未进行诊断分析，无法提交检查结果")
        
        # 验证所有检查都包含结果
        for test in submitted_tests:
            if 'result' not in test or not test['result']:
                raise ValueError(f"检查项目 {test.get('test_name', '未知')} 缺少结果")
        
        # 保存已提交的检查（每个检查都包含独立的结果）
        patient_data.diagnosis_info.submitted_tests = submitted_tests
        
        # 同时将所有检查结果汇总到test_results字段（保持向后兼容）
        results_summary = "\n\n".join([
            f"【{test['test_name']}】\n{test['result']}" 
            for test in submitted_tests
        ])
        patient_data.test_results = results_summary
        
        self.save_patient_data(patient_data)
        print(f">>> 已保存 {len(submitted_tests)} 项检查结果")
        return patient_data


# ============================================================================
# 全局患者数据管理器实例
# ============================================================================

# 创建全局实例
patient_manager = PatientDataManager()


# ============================================================================
# 测试代码
# ============================================================================

if __name__ == "__main__":
    import uuid
    
    # 测试创建患者
    test_patient_id = str(uuid.uuid4())
    print(f"测试患者ID: {test_patient_id}")
    
    # 更新分诊信息
    patient_manager.update_triage_info(
        patient_id=test_patient_id,
        triage_level="III级（紧急）",
        recommended_department="急诊内科",
        triage_basis="患者出现发热及气促"
    )
    
    # 更新诊断信息
    patient_manager.update_diagnosis_info(
        patient_id=test_patient_id,
        most_likely_disease="坏死性软组织感染",
        confidence=95.26,
        disease_details={
            "坏死性软组织感染": {"score": 8, "probability": 95.26},
            "蜂窝织炎": {"score": 2, "probability": 4.74}
        },
        recommended_tests=[
            {"test_name": "手术探查", "test_description": "通过手指试验和直视判断坏死组织"},
            {"test_name": "CT扫描", "test_description": "显示皮下气体影和筋膜水肿"}
        ]
    )
    
    # 加载并显示
    patient_data = patient_manager.load_patient_data(test_patient_id)
    print("\n患者数据:")
    print(json.dumps(patient_data.model_dump(), ensure_ascii=False, indent=2))

