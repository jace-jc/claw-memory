# 贡献指南

欢迎贡献 Claw Memory！

## 开发环境设置

```bash
# 克隆仓库
git clone https://github.com/jace-jc/claw-memory.git
cd claw-memory

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -e ".[dev]"

# 运行测试
python3 tests/test_memory.py
```

## 代码规范

- 使用 Python 3.9+
- 遵循 PEP 8
- 添加类型注解 (type hints)
- 为新功能编写测试

## 分支命名

- `feature/` - 新功能
- `fix/` - Bug修复
- `docs/` - 文档更新
- `refactor/` - 重构

示例：
```bash
git checkout -b feature/add-image-captioning
```

## 提交规范

使用清晰的提交信息：

```
feat: 添加图像描述生成功能
fix: 修复temporal通道MRR为0的问题
docs: 更新快速入门指南
test: 添加意图分类器测试
```

## 测试要求

- 所有新功能必须包含测试
- 确保 `python3 tests/test_memory.py` 全部通过
- 测试覆盖新增代码路径

## Pull Request 流程

1. Fork 本仓库
2. 创建功能分支
3. 编写代码和测试
4. 提交并推送
5. 创建 Pull Request
6. 等待代码审查

## 问题反馈

- 使用 GitHub Issues 报告 bug
- 功能请求请描述使用场景
- 提交 PR 时说明改动内容

## 许可证

本项目使用 MIT 许可证
