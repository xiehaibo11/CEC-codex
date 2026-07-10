# 数据库表结构（随项目分发，可直接导入）

本目录是两套库的**完整表结构 SQL**（纯文本、已入 git），用于在新环境快速建表：

| 文件 | 对应库 | 表数量 |
|---|---|---|
| `alpha_arena_schema.sql` | 主库 `alpha_arena`（用户、K线、回测、纸盘、AI 决策日志等） | 74 |
| `alpha_snapshots_schema.sql` | 快照库 `alpha_snapshots`（Hyperliquid 账户快照/成交） | 2 |
| `import.sh` | 一键建库+导入脚本（幂等；非空库默认拒绝导入，防误操作） | — |

## 快速导入

```bash
cd database_schema
./import.sh                # 默认容器 cec-codex-postgres、用户 alpha_user
```

只建结构、不含数据。要恢复**数据**，用 `backups/` 里的二进制备份（见 `backups/README.md`）。

## 与 migration 体系的关系

应用启动时 `database.migration_manager` 会跑幂等迁移，正常部署**不需要**手动导入本目录。
本目录用于：脱离应用直接建库、数据分析环境、恢复演练、或团队成员快速拿到全量表定义。

## 重新导出（表结构变更后）

```bash
docker exec cec-codex-postgres pg_dump -U alpha_user -d alpha_arena    --schema-only --no-owner --no-privileges > database_schema/alpha_arena_schema.sql
docker exec cec-codex-postgres pg_dump -U alpha_user -d alpha_snapshots --schema-only --no-owner --no-privileges > database_schema/alpha_snapshots_schema.sql
```

导出时间：2026-07-07（已在全新空库验证一次性导入成功）
