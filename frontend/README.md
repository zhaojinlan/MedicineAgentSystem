# 医疗多智能体系统 - 前端

基于 Vue 3 + Element Plus 的现代化医疗诊断系统前端界面。

## 功能特性

### 三栏布局设计

- **左侧栏：患者管理**
  - 新建患者（姓名、年龄、初始症状）
  - 患者列表展示
  - 搜索患者
  - 删除患者

- **中间栏：患者详情**
  - 患者基本信息
  - 初始症状
  - 分诊信息（级别、科室、依据）
  - 诊断信息（疾病、置信度、推荐检查）
  - 专家会诊（诊断、影像、治疗意见）
  - JSON原始数据查看

- **右侧栏：AI对话**
  - 实时与AI助手对话
  - 对话历史记录
  - 支持多轮交互

## 技术栈

- **Vue 3** - 渐进式JavaScript框架
- **Vite** - 下一代前端构建工具
- **Element Plus** - Vue 3 组件库
- **Axios** - HTTP客户端

## 安装依赖

```bash
cd frontend
npm install
```

## 启动开发服务器

```bash
npm run dev
```

前端将在 `http://localhost:3000` 启动

## 构建生产版本

```bash
npm run build
```

构建产物将生成在 `dist` 目录

## 项目结构

```
frontend/
├── src/
│   ├── api/
│   │   └── patient.js          # API接口封装
│   ├── components/
│   │   ├── PatientList.vue     # 患者列表组件（左侧）
│   │   ├── PatientDetail.vue   # 患者详情组件（中间）
│   │   └── ChatPanel.vue       # AI对话组件（右侧）
│   ├── App.vue                 # 主应用组件
│   └── main.js                 # 应用入口
├── index.html                  # HTML模板
├── vite.config.js             # Vite配置
└── package.json               # 项目配置
```

## 使用说明

### 1. 新建患者

1. 点击左侧"新建患者"按钮
2. 填写患者姓名、年龄
3. 可选填写初始症状
4. 点击"创建"

### 2. 查看患者详情

- 在左侧患者列表中点击患者
- 中间栏将显示该患者的完整信息

### 3. 与AI对话

1. 选择一个患者
2. 在右侧输入框输入消息
3. 点击"发送"或按 Ctrl+Enter
4. AI将分析并回复

### 4. 对话类型

- **症状分诊**：输入"患者出现..."
- **回答问题**：回答AI提出的风险因素问题
- **检查结果**：输入检查报告结果
- **知识查询**：询问医学知识

## API接口

前端通过以下API与后端通信（后端端口：8001）：

- `GET /api/patients` - 获取患者列表
- `GET /api/patients/:id` - 获取患者详情
- `POST /api/patients` - 创建患者
- `PUT /api/patients/:id` - 更新患者
- `DELETE /api/patients/:id` - 删除患者
- `POST /api/chat` - 发送对话消息

## 注意事项

1. 确保后端API服务已启动（端口8001）
2. 前端开发服务器配置了代理，自动转发API请求到8001端口
3. MCP服务使用8000端口，不要与后端API冲突
4. 首次使用需要先创建患者
5. 对话需要选中患者后才能进行

## 浏览器兼容性

- Chrome/Edge (推荐)
- Firefox
- Safari

建议使用最新版本的现代浏览器以获得最佳体验。

