# CEC-codex 数据库备份

## 本目录内容
- `alpha_arena_<时间戳>.dump` — 主库（74 张表：用户、交易、回测、纸盘、AI 决策日志、K 线等），pg_dump 自定义压缩格式
- `alpha_snapshots_<时间戳>.dump` — 快照库（2 张表：Hyperliquid 账户快照/成交）
- `globals_<时间戳>.sql` — 角色与全局对象定义

最近一次备份：20260707_142528（已通过完整恢复演练验证：74/74 表、关键表行数逐一比对一致）

## 恢复方法（容器内）
```bash
# 1. 如角色不存在，先恢复全局对象
docker exec -i cec-codex-postgres psql -U alpha_user -d postgres < globals_20260707_142528.sql

# 2. 建空库并恢复（示例：主库恢复到 alpha_arena_restored）
docker exec cec-codex-postgres psql -U alpha_user -d postgres -c "CREATE DATABASE alpha_arena_restored;"
docker exec -i cec-codex-postgres pg_restore -U alpha_user -d alpha_arena_restored --no-owner < alpha_arena_20260707_142528.dump

# 3. 只恢复单张表（自定义格式支持选择性恢复）
docker exec -i cec-codex-postgres pg_restore -U alpha_user -d <目标库> --no-owner -t event_contract_paper_bets < alpha_arena_20260707_142528.dump
```

## 重新备份
```bash
cd "/Volumes/Install macOS Sequoia/CEC-codex/backups"
TS=$(date +%Y%m%d_%H%M%S)
docker exec cec-codex-postgres pg_dump -U alpha_user -d alpha_arena -Fc > "alpha_arena_${TS}.dump"
docker exec cec-codex-postgres pg_dump -U alpha_user -d alpha_snapshots -Fc > "alpha_snapshots_${TS}.dump"
docker exec cec-codex-postgres pg_dumpall -U alpha_user --globals-only > "globals_${TS}.sql"
```
