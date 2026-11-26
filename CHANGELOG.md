# 变更记录

## [Unreleased]

### 变更
- 从项目仓 `ai-test-framework` 的 `.claude/skills` 独立为公共技能库，保留原有提交历史。
- 移除技能内的宿主项目绝对路径：`design-testcases` 的环境准备改为相对项目根目录解析，`test-report` 的凭证路径改为项目根目录 `.env`。
- 新增 `README.md` 与 `.gitignore`，约定技能产物不写回技能目录。
- 脱敏：`bug-analysis` 示例中的内网 Base URL 改为 `{base_url}` 占位。
- 技能产物目录由技能目录迁移到项目侧：`design-testcases` 工作区默认落在 `reports/.skill-workspaces/`，支持 `--workspace_root` 与 `SKILL_WORKSPACE_DIR` 覆盖；`db_config.json` 优先读项目根目录。
- `design-testcases` 与 `test-report` 增加产物归档到交付物库 `UR-*/` 的步骤。

### 待办
- `manual-order-quote-flow` 的业务参数改为读取项目配置，剥离业务常量。
