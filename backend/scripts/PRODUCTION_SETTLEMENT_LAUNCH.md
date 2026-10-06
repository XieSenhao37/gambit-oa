# 2026 年 10 月首次正式结算上线

准备材料，不表示已执行。正式库保持不动，等小程序审核通过后安排维护窗口。此前演练的 7/8 月 Mock、旧期开账参数及赠卡/验券清单不得用于正式库。

## 完整结构迁移包

已准备相邻 `GambitServer/sql/releases/20261006/01_schema.sql` 和同目录 `README.md`。正式库共享结构迁移统一执行该 SQL；下文 `schema` 命令仅为结算局部备用入口，不代替完整版本迁移。结构就绪后仍需在实际维护窗口执行 `preview/apply` 期初初始化，不能仅执行 SQL 就启用记账。

## 已确认的业务口径

- 首次结算月份为 2026-10，2026-11-01 起生成报表。
- 切换点 T 是维护窗口暂停写入后的真实北京时间，精确到秒。不能倒填 10 月 1 日；本次脚本禁止正式切换月份不是 2026-10。
- 切换前消费、退款、已完成积分成本、月卡卡期和核销不补结算。旧业务订单和账户余额保留。
- 历史储值、积分、旧月卡的来源和承担方统一南山店。后续实际消费或履约仍记实际门店。
- 储值按原充值本金/到账余额比例保留剩余本金。初始化只用历史流水重建余额批次，不生成历史结算分录。
- 旧月卡仅导入尚未结束的剩余卡期；进行中的卡期金额为原金额减已过卡期金额（按秒分摊，整数分保留尾差）。后续续卡期保留全额。玩家原到期时间不变。
- 剩余月卡金额按之后的有效核销门店分配；无核销金额沿用现有暂留、到期补分、整卡零使用归总部规则。旧卡分配的出款承担方是南山；不是把后续实际核销门店也改成南山。
- 未提货积分兑换、未结束抽奖和储值冻结不丢弃，保留在途资产与之后履约/退款关联。已完成历史履约不补成本。
- 上线前储值消费在上线后退款，恢复玩家余额和本金，不冲减未曾结算的门店款。若上线前冻结、上线后扣款已入结算，则正常冲回该结算款。

## 审核通过前

1. 在隔离测试环境确认结算生成、核对、确认、凭证上传及玩家自购月卡。生产 schema、期初和数据都不执行。
2. 构建并记录 Go 服务、小程序和 OA 的具体版本及镜像摘要，保留当前版本用于回退。镜像构建/推送与实际部署分开。
3. 核对正式南山门店 `stores.code=nanshan`、旧月卡有效期与原订单能对应、储值流水能重建当前余额。预演会在不一致时停止，不猜测本金或改玩家资产。
4. 核对正式库是否已完成其他功能所需的员工权限、商品、支付等 schema 迁移；本脚本仅覆盖结算表及月卡订单快照字段，不代替全部版本迁移。

## 维护窗口执行顺序

先备份正式库，暂停玩家充值/消费/开卡/积分及 OA 写入，停止旧实例、定时任务和异步写入。处理支付回调与退款重试，核对在玩订单、冻结款和未完成开卡单；支付成功但未发卡等异常须先处理，不能通过忽略旧账丢失玩家权益。未提货兑换或未结束抽奖可以按期初脚本保留。

在已暂停写入后记录 T，并确保 preview/apply 使用完全相同的 T。数据库密码由终端隐藏输入，不写进命令、脚本或报告。下面从 `gambit-oa` 根目录执行，数据库用户名按正式账号填写。

```bash
backend/.venv/bin/python backend/scripts/migrate_settlement.py schema \
  --production-launch \
  --host sh-cynosdbmysql-grp-a7usn35k.sql.tencentcdb.com --port 22120 \
  --database gambit --user root --report /tmp/gambit-production-schema.json
```

schema 创建缺失结算表，补充月卡订单 `duration_days/request_key` 和凭证字段，不执行期初。MySQL DDL 会提交，执行前务必备份。

将下面时间占位符替换为本次真实 T。**不要直接复制占位符执行，也不要使用演练日期。**

```bash
backend/.venv/bin/python backend/scripts/migrate_settlement.py preview \
  --production-launch \
  --host sh-cynosdbmysql-grp-a7usn35k.sql.tencentcdb.com --port 22120 \
  --database gambit --user root --cutoff 'YYYY-MM-DD HH:MM:SS' \
  --report /tmp/gambit-production-preview.json
```

preview 在事务内建立期初后回滚。核对 `FirstSettlementMonth=2026-10`、`CardPolicy=prospective`、`HistoricalEntries=0`、余额与本金、积分数量和旧卡池数量。报告没有密码或客户身份。正式环境已有结算账、切换后资产变动或原始依据不一致时会停止；不要清库或覆盖重跑。

核对完成后，仍保持暂停写入：

```bash
backend/.venv/bin/python backend/scripts/migrate_settlement.py apply \
  --production-launch --maintenance-confirmed \
  --host sh-cynosdbmysql-grp-a7usn35k.sql.tencentcdb.com --port 22120 \
  --database gambit --user root --cutoff 'YYYY-MM-DD HH:MM:SS' \
  --report /tmp/gambit-production-applied.json
```

成功报告须有 `Committed=true`。同规则重复初始化不重新开账；不同切换点或口径会被拒绝。

随后部署一致版本的 Go 服务和 OA，并在两端持久配置 `STORE_SETTLEMENT_ENABLED=true`，再发布已审核小程序和恢复业务。当前 OA `deploy.sh` 的正式默认仍是 false，首次启用时须把默认值或服务器持久部署配置改为 true，保证以后照常执行部署脚本不会关闭记账。**不能在期初初始化完成之前开启 Go 记账开关。**

## 上线后核验

- 10 月报表只能从真实 T 起计，页面/CSV 显示首次覆盖范围；11 月 1 日前不能生成 10 月完整报表。
- 用正常业务核对微信支付、储值扣款、退款、积分来源、月卡核销的门店归属和分录，无需在正式库写 Mock。
- 生成报表时仅固定核算草稿，月卡与积分确认结算才正式入账。完成各门店实际收付款后确认。
- 如果开启后已有交易，不能简单关开关回退到旧版本，否则新业务会漏记；应暂停业务核对后处理，不能重新跑期初覆盖。

当前生产数据、schema 和部署开关均未验证或修改。实际维护窗口预演、核对和执行是上线前剩余步骤。
