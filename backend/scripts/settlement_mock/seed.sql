-- ONLY GUANGZHOU TEST DATABASE. No production use.
-- Run with run.py: hidden password, endpoint checks, transaction, backups and validation.
-- No COMMIT here: the runner commits ONLY after verification.

CREATE TEMPORARY TABLE `_mock_settlement_guard` (`ok` INT NOT NULL CHECK (`ok`=1));

INSERT INTO `_mock_settlement_guard` VALUES (IF(@gambit_mock_authorized='MOCK_SETTLE_20260927' AND @gambit_mock_target_db=DATABASE(),1,0));

UPDATE `settlement_controls` SET `cutoff`='2026-07-01 00:00:00' WHERE `id`=1 AND `cutoff`=@mock_original_cutoff;

INSERT INTO `stores` (`id`, `code`, `name`, `status`, `sort`, `address`, `business_hours`, `created_at`, `updated_at`) VALUES (870927001, 'mock-settle-a', 'MOCK-A-收款店', 1, 9001, '仅测试环境模拟门店，无真实地址', '模拟数据', '2026-07-01 00:00:00', '2026-07-01 00:00:00');

INSERT INTO `stores` (`id`, `code`, `name`, `status`, `sort`, `address`, `business_hours`, `created_at`, `updated_at`) VALUES (870927002, 'mock-settle-b', 'MOCK-B-跨店履约', 1, 9002, '仅测试环境模拟门店，无真实地址', '模拟数据', '2026-07-01 00:00:00', '2026-07-01 00:00:00');

INSERT INTO `stores` (`id`, `code`, `name`, `status`, `sort`, `address`, `business_hours`, `created_at`, `updated_at`) VALUES (870927003, 'mock-settle-c', 'MOCK-C-当期补款', 1, 9003, '仅测试环境模拟门店，无真实地址', '模拟数据', '2026-07-01 00:00:00', '2026-07-01 00:00:00');

INSERT INTO `stores` (`id`, `code`, `name`, `status`, `sort`, `address`, `business_hours`, `created_at`, `updated_at`) VALUES (870927004, 'mock-settle-d', 'MOCK-D-零净额', 1, 9004, '仅测试环境模拟门店，无真实地址', '模拟数据', '2026-07-01 00:00:00', '2026-07-01 00:00:00');

INSERT INTO `settlement_periods` (`month`, `status`) VALUES ('2026-07', 'draft');

INSERT INTO `settlement_periods` (`month`, `status`) VALUES ('2026-08', 'draft');

INSERT INTO `users` (`id`, `open_id`, `nick_name`, `role`, `user_type`, `gender`, `registered_store_id`, `registered_store_source`, `created_at`, `updated_at`) VALUES (870927011, 'MOCK_SETTLE_20260927_u1', 'MOCK-微信消费', 0, 0, 0, 870927001, 'mock', '2026-07-01 00:00:00', '2026-07-01 00:00:00');

INSERT INTO `users` (`id`, `open_id`, `nick_name`, `role`, `user_type`, `gender`, `registered_store_id`, `registered_store_source`, `created_at`, `updated_at`) VALUES (870927012, 'MOCK_SETTLE_20260927_u2', 'MOCK-储值跨批次退款', 0, 0, 0, 870927001, 'mock', '2026-07-01 00:00:00', '2026-07-01 00:00:00');

INSERT INTO `dishes` (`store_id`, `name`, `price`, `status`, `category_ids`, `options`, `tags`, `id`, `created_at`, `updated_at`) VALUES (870927002, 'MOCK-测试饮料', 2000, 0, '[]', '[]', '[]', 870927109, '2026-07-01 00:00:00', '2026-07-01 00:00:00');

INSERT INTO `play_orders` (`store_id`, `open_id`, `in_time`, `out_time`, `play_time`, `amount`, `settle_status`, `unit_price`, `comment`, `created_at`, `id`, `updated_at`, `billing_mode`) VALUES (870927001, 'MOCK_SETTLE_20260927_u1', '2026-07-05 10:00:00', '2026-07-05 12:00:00', 2, 10000, 1, 5000, 'MOCK模拟订单', '2026-07-05 12:00:00', 870927110, '2026-07-01 00:00:00', 0);

INSERT INTO `pay_orders` (`store_id`, `open_id`, `amount`, `total_amount`, `wallet_amount`, `wechat_amount`, `pay_type`, `pay_status`, `pay_end_time`, `created_at`, `order_id`, `description`, `play_order_id`, `id`, `updated_at`, `wallet_refund_amount`, `wechat_refund_amount`) VALUES (870927001, 'MOCK_SETTLE_20260927_u1', 10000, 10000, 0, 10000, 0, 1, '2026-07-05 12:00:00', '2026-07-05 12:00:00', 'MOCK_SETTLE_20260927_july-play', 'MOCK模拟支付', 870927110, 870927111, '2026-07-01 00:00:00', 0, 0);

INSERT INTO `caterings` (`store_id`, `open_id`, `total_price`, `status`, `settle_status`, `code`, `created_at`, `updated_at`, `comment`, `id`, `takeaway`) VALUES (870927002, 'MOCK_SETTLE_20260927_u1', 6000, 1, 1, 'MOCK_SETTLE_20260927-july-food', '2026-07-06 12:00:00', '2026-07-06 12:00:00', 'MOCK模拟订单', 870927112, 0);

INSERT INTO `catering_items` (`catering_id`, `dish_id`, `count`, `total_price`, `selections`, `id`, `created_at`, `updated_at`) VALUES (870927112, 870927109, 1, 6000, '[]', 870927113, '2026-07-01 00:00:00', '2026-07-01 00:00:00');

INSERT INTO `pay_orders` (`store_id`, `open_id`, `amount`, `total_amount`, `wallet_amount`, `wechat_amount`, `pay_type`, `pay_status`, `pay_end_time`, `created_at`, `order_id`, `description`, `catering_id`, `id`, `updated_at`, `wallet_refund_amount`, `wechat_refund_amount`) VALUES (870927002, 'MOCK_SETTLE_20260927_u1', 6000, 6000, 0, 6000, 0, 1, '2026-07-06 12:00:00', '2026-07-06 12:00:00', 'MOCK_SETTLE_20260927_july-food', 'MOCK模拟支付', 870927112, 870927114, '2026-07-01 00:00:00', 0, 0);

INSERT INTO `play_orders` (`store_id`, `open_id`, `in_time`, `out_time`, `play_time`, `amount`, `settle_status`, `unit_price`, `comment`, `created_at`, `id`, `updated_at`, `billing_mode`) VALUES (870927001, 'MOCK_SETTLE_20260927_u1', '2026-07-07 10:00:00', '2026-07-07 12:00:00', 2, 2000, 1, 1000, 'MOCK模拟订单', '2026-07-07 12:00:00', 870927115, '2026-07-01 00:00:00', 0);

INSERT INTO `pay_orders` (`store_id`, `open_id`, `amount`, `total_amount`, `wallet_amount`, `wechat_amount`, `pay_type`, `pay_status`, `pay_end_time`, `created_at`, `order_id`, `description`, `play_order_id`, `id`, `updated_at`, `wallet_refund_amount`, `wechat_refund_amount`, `refund_amount`) VALUES (870927001, 'MOCK_SETTLE_20260927_u1', 2000, 2000, 0, 2000, 0, 3, '2026-07-07 12:00:00', '2026-07-07 12:00:00', 'MOCK_SETTLE_20260927_same-month-refund', 'MOCK模拟支付', 870927115, 870927116, '2026-07-01 00:00:00', 0, 2000, 2000);

INSERT INTO `refund_requests` (`open_id`, `order_type`, `order_id`, `pay_order_id`, `amount`, `status`, `created_at`, `reviewed_at`, `refunded_at`, `out_refund_no`, `review_remark`, `id`, `updated_at`) VALUES ('MOCK_SETTLE_20260927_u1', 'play', 870927115, 870927116, 2000, 'refunded', '2026-07-08 12:00:00', '2026-07-08 12:00:00', '2026-07-08 12:00:00', 'MOCK_SETTLE_20260927870927116', 'MOCK已成功退款，无外部调用', 870927117, '2026-07-01 00:00:00');

INSERT INTO `play_orders` (`store_id`, `open_id`, `in_time`, `out_time`, `play_time`, `amount`, `settle_status`, `unit_price`, `comment`, `created_at`, `id`, `updated_at`, `billing_mode`) VALUES (870927002, 'MOCK_SETTLE_20260927_u1', '2026-07-25 10:00:00', '2026-07-25 12:00:00', 2, 5000, 1, 2500, 'MOCK模拟订单', '2026-07-25 12:00:00', 870927118, '2026-07-01 00:00:00', 0);

INSERT INTO `pay_orders` (`store_id`, `open_id`, `amount`, `total_amount`, `wallet_amount`, `wechat_amount`, `pay_type`, `pay_status`, `pay_end_time`, `created_at`, `order_id`, `description`, `play_order_id`, `id`, `updated_at`, `wallet_refund_amount`, `wechat_refund_amount`, `refund_amount`) VALUES (870927002, 'MOCK_SETTLE_20260927_u1', 5000, 5000, 0, 5000, 0, 3, '2026-07-25 12:00:00', '2026-07-25 12:00:00', 'MOCK_SETTLE_20260927_cross-month-refund', 'MOCK模拟支付', 870927118, 870927119, '2026-07-01 00:00:00', 0, 5000, 5000);

INSERT INTO `refund_requests` (`open_id`, `order_type`, `order_id`, `pay_order_id`, `amount`, `status`, `created_at`, `reviewed_at`, `refunded_at`, `out_refund_no`, `review_remark`, `id`, `updated_at`) VALUES ('MOCK_SETTLE_20260927_u1', 'play', 870927118, 870927119, 5000, 'refunded', '2026-08-03 12:00:00', '2026-08-03 12:00:00', '2026-08-03 12:00:00', 'MOCK_SETTLE_20260927870927119', 'MOCK已成功退款，无外部调用', 870927120, '2026-07-01 00:00:00');

INSERT INTO `play_orders` (`store_id`, `open_id`, `in_time`, `out_time`, `play_time`, `amount`, `settle_status`, `unit_price`, `comment`, `created_at`, `id`, `updated_at`, `billing_mode`) VALUES (870927004, 'MOCK_SETTLE_20260927_u1', '2026-07-09 10:00:00', '2026-07-09 12:00:00', 2, 1000, 1, 500, 'MOCK模拟订单', '2026-07-09 12:00:00', 870927121, '2026-07-01 00:00:00', 0);

INSERT INTO `pay_orders` (`store_id`, `open_id`, `amount`, `total_amount`, `wallet_amount`, `wechat_amount`, `pay_type`, `pay_status`, `pay_end_time`, `created_at`, `order_id`, `description`, `play_order_id`, `id`, `updated_at`, `wallet_refund_amount`, `wechat_refund_amount`, `refund_amount`) VALUES (870927004, 'MOCK_SETTLE_20260927_u1', 1000, 1000, 0, 1000, 0, 3, '2026-07-09 12:00:00', '2026-07-09 12:00:00', 'MOCK_SETTLE_20260927_zero-net', 'MOCK模拟支付', 870927121, 870927122, '2026-07-01 00:00:00', 0, 1000, 1000);

INSERT INTO `refund_requests` (`open_id`, `order_type`, `order_id`, `pay_order_id`, `amount`, `status`, `created_at`, `reviewed_at`, `refunded_at`, `out_refund_no`, `review_remark`, `id`, `updated_at`) VALUES ('MOCK_SETTLE_20260927_u1', 'play', 870927121, 870927122, 1000, 'refunded', '2026-07-10 12:00:00', '2026-07-10 12:00:00', '2026-07-10 12:00:00', 'MOCK_SETTLE_20260927870927122', 'MOCK已成功退款，无外部调用', 870927123, '2026-07-01 00:00:00');

INSERT INTO `play_orders` (`store_id`, `open_id`, `in_time`, `out_time`, `play_time`, `amount`, `settle_status`, `unit_price`, `comment`, `created_at`, `id`, `updated_at`, `billing_mode`) VALUES (870927001, 'MOCK_SETTLE_20260927_u1', '2026-08-08 10:00:00', '2026-08-08 12:00:00', 2, 3000, 1, 1500, 'MOCK模拟订单', '2026-08-08 12:00:00', 870927124, '2026-07-01 00:00:00', 0);

INSERT INTO `pay_orders` (`store_id`, `open_id`, `amount`, `total_amount`, `wallet_amount`, `wechat_amount`, `pay_type`, `pay_status`, `pay_end_time`, `created_at`, `order_id`, `description`, `play_order_id`, `id`, `updated_at`, `wallet_refund_amount`, `wechat_refund_amount`) VALUES (870927001, 'MOCK_SETTLE_20260927_u1', 3000, 3000, 0, 3000, 0, 1, '2026-08-08 12:00:00', '2026-08-08 12:00:00', 'MOCK_SETTLE_20260927_aug-play', 'MOCK模拟支付', 870927124, 870927125, '2026-07-01 00:00:00', 0, 0);

INSERT INTO `caterings` (`store_id`, `open_id`, `total_price`, `status`, `settle_status`, `code`, `created_at`, `updated_at`, `comment`, `id`, `takeaway`) VALUES (870927002, 'MOCK_SETTLE_20260927_u1', 8000, 1, 1, 'MOCK_SETTLE_20260927-aug-food', '2026-08-09 12:00:00', '2026-08-09 12:00:00', 'MOCK模拟订单', 870927126, 0);

INSERT INTO `catering_items` (`catering_id`, `dish_id`, `count`, `total_price`, `selections`, `id`, `created_at`, `updated_at`) VALUES (870927126, 870927109, 1, 8000, '[]', 870927127, '2026-07-01 00:00:00', '2026-07-01 00:00:00');

INSERT INTO `pay_orders` (`store_id`, `open_id`, `amount`, `total_amount`, `wallet_amount`, `wechat_amount`, `pay_type`, `pay_status`, `pay_end_time`, `created_at`, `order_id`, `description`, `catering_id`, `id`, `updated_at`, `wallet_refund_amount`, `wechat_refund_amount`) VALUES (870927002, 'MOCK_SETTLE_20260927_u1', 8000, 8000, 0, 8000, 0, 1, '2026-08-09 12:00:00', '2026-08-09 12:00:00', 'MOCK_SETTLE_20260927_aug-food', 'MOCK模拟支付', 870927126, 870927128, '2026-07-01 00:00:00', 0, 0);

INSERT INTO `play_orders` (`store_id`, `open_id`, `in_time`, `out_time`, `play_time`, `amount`, `settle_status`, `unit_price`, `comment`, `created_at`, `id`, `updated_at`, `billing_mode`) VALUES (870927001, 'MOCK_SETTLE_20260927_u1', '2026-07-12 10:00:00', '2026-07-12 12:00:00', 2, 99900, 1, 49950, 'MOCK模拟订单', '2026-07-12 12:00:00', 870927129, '2026-07-01 00:00:00', 0);

INSERT INTO `pay_orders` (`store_id`, `open_id`, `amount`, `total_amount`, `wallet_amount`, `wechat_amount`, `pay_type`, `pay_status`, `pay_end_time`, `created_at`, `order_id`, `description`, `play_order_id`, `id`, `updated_at`, `wallet_refund_amount`, `wechat_refund_amount`) VALUES (870927001, 'MOCK_SETTLE_20260927_u1', 99900, 99900, 0, 99900, 0, 0, '2026-07-12 12:00:00', '2026-07-12 12:00:00', 'MOCK_SETTLE_20260927_unpaid-excluded', 'MOCK模拟支付', 870927129, 870927130, '2026-07-01 00:00:00', 0, 0);

INSERT INTO `wallet_accounts` (`open_id`, `balance`, `frozen_balance`, `id`, `created_at`, `updated_at`, `status`) VALUES ('MOCK_SETTLE_20260927_u2', 13000, 0, 870927131, '2026-07-01 00:00:00', '2026-07-01 00:00:00', 0);

INSERT INTO `wallet_recharge_orders` (`open_id`, `amount`, `bonus_amount`, `status`, `paid_at`, `created_at`, `id`, `updated_at`, `pay_order_id`) VALUES ('MOCK_SETTLE_20260927_u2', 10000, 2000, 1, '2026-07-02 12:00:00', '2026-07-02 12:00:00', 870927132, '2026-07-01 00:00:00', 870927133);

INSERT INTO `pay_orders` (`store_id`, `open_id`, `amount`, `wechat_amount`, `pay_type`, `pay_status`, `pay_end_time`, `created_at`, `wallet_recharge_order_id`, `order_id`, `id`, `updated_at`, `wallet_amount`, `wallet_refund_amount`, `wechat_refund_amount`) VALUES (870927001, 'MOCK_SETTLE_20260927_u2', 10000, 10000, 0, 1, '2026-07-02 12:00:00', '2026-07-02 12:00:00', 870927132, 'MOCK_SETTLE_20260927_recharge0', 870927133, '2026-07-01 00:00:00', 0, 0, 0);

INSERT INTO `wallet_transactions` (`open_id`, `account_id`, `type`, `direction`, `amount`, `balance_before`, `balance_after`, `frozen_before`, `frozen_after`, `biz_key`, `remark`, `created_at`, `related_recharge_order_id`, `id`, `updated_at`) VALUES ('MOCK_SETTLE_20260927_u2', 870927131, 'recharge', 'in', 10000, 0, 10000, 0, 0, 'MOCK_SETTLE_20260927:wallet:33', 'MOCK储值流水', '2026-07-02 12:00:00', 870927132, 870927134, '2026-07-01 00:00:00');

INSERT INTO `wallet_transactions` (`open_id`, `account_id`, `type`, `direction`, `amount`, `balance_before`, `balance_after`, `frozen_before`, `frozen_after`, `biz_key`, `remark`, `created_at`, `related_recharge_order_id`, `id`, `updated_at`) VALUES ('MOCK_SETTLE_20260927_u2', 870927131, 'bonus', 'in', 2000, 10000, 12000, 0, 0, 'MOCK_SETTLE_20260927:wallet:34', 'MOCK储值流水', '2026-07-02 12:00:00', 870927132, 870927135, '2026-07-01 00:00:00');

INSERT INTO `settlement_batches` (`kind`, `open_id`, `source_key`, `source_store_id`, `responsible_store_id`, `face_total`, `principal_total`, `remaining`, `principal_remaining`, `created_at`, `id`, `frozen`, `legacy`) VALUES ('wallet', 'MOCK_SETTLE_20260927_u2', 'wallet:recharge:870927132', 870927001, 0, 12000, 10000, 6000, 5000, '2026-07-02 12:00:00', 870927136, 0, 0);

INSERT INTO `wallet_recharge_orders` (`open_id`, `amount`, `bonus_amount`, `status`, `paid_at`, `created_at`, `id`, `updated_at`, `pay_order_id`) VALUES ('MOCK_SETTLE_20260927_u2', 5000, 5000, 1, '2026-07-03 12:00:00', '2026-07-03 12:00:00', 870927137, '2026-07-01 00:00:00', 870927138);

INSERT INTO `pay_orders` (`store_id`, `open_id`, `amount`, `wechat_amount`, `pay_type`, `pay_status`, `pay_end_time`, `created_at`, `wallet_recharge_order_id`, `order_id`, `id`, `updated_at`, `wallet_amount`, `wallet_refund_amount`, `wechat_refund_amount`) VALUES (870927001, 'MOCK_SETTLE_20260927_u2', 5000, 5000, 0, 1, '2026-07-03 12:00:00', '2026-07-03 12:00:00', 870927137, 'MOCK_SETTLE_20260927_recharge1', 870927138, '2026-07-01 00:00:00', 0, 0, 0);

INSERT INTO `wallet_transactions` (`open_id`, `account_id`, `type`, `direction`, `amount`, `balance_before`, `balance_after`, `frozen_before`, `frozen_after`, `biz_key`, `remark`, `created_at`, `related_recharge_order_id`, `id`, `updated_at`) VALUES ('MOCK_SETTLE_20260927_u2', 870927131, 'recharge', 'in', 5000, 12000, 17000, 0, 0, 'MOCK_SETTLE_20260927:wallet:38', 'MOCK储值流水', '2026-07-03 12:00:00', 870927137, 870927139, '2026-07-01 00:00:00');

INSERT INTO `wallet_transactions` (`open_id`, `account_id`, `type`, `direction`, `amount`, `balance_before`, `balance_after`, `frozen_before`, `frozen_after`, `biz_key`, `remark`, `created_at`, `related_recharge_order_id`, `id`, `updated_at`) VALUES ('MOCK_SETTLE_20260927_u2', 870927131, 'bonus', 'in', 5000, 17000, 22000, 0, 0, 'MOCK_SETTLE_20260927:wallet:39', 'MOCK储值流水', '2026-07-03 12:00:00', 870927137, 870927140, '2026-07-01 00:00:00');

INSERT INTO `settlement_batches` (`kind`, `open_id`, `source_key`, `source_store_id`, `responsible_store_id`, `face_total`, `principal_total`, `remaining`, `principal_remaining`, `created_at`, `id`, `frozen`, `legacy`) VALUES ('wallet', 'MOCK_SETTLE_20260927_u2', 'wallet:recharge:870927137', 870927001, 0, 10000, 5000, 7000, 3500, '2026-07-03 12:00:00', 870927141, 0, 0);

INSERT INTO `play_orders` (`store_id`, `open_id`, `in_time`, `out_time`, `play_time`, `amount`, `settle_status`, `unit_price`, `comment`, `created_at`, `id`, `updated_at`, `billing_mode`) VALUES (870927001, 'MOCK_SETTLE_20260927_u2', '2026-07-15 10:00:00', '2026-07-15 12:00:00', 2, 12000, 1, 6000, 'MOCK模拟订单', '2026-07-15 12:00:00', 870927142, '2026-07-01 00:00:00', 0);

INSERT INTO `pay_orders` (`store_id`, `open_id`, `amount`, `total_amount`, `wallet_amount`, `wechat_amount`, `pay_type`, `pay_status`, `pay_end_time`, `created_at`, `order_id`, `description`, `play_order_id`, `id`, `updated_at`, `wallet_refund_amount`, `wechat_refund_amount`, `refund_amount`) VALUES (870927001, 'MOCK_SETTLE_20260927_u2', 12000, 12000, 6000, 6000, 4, 3, '2026-07-15 12:00:00', '2026-07-15 12:00:00', 'MOCK_SETTLE_20260927_mixed', 'MOCK模拟支付', 870927142, 870927143, '2026-07-01 00:00:00', 6000, 6000, 12000);

INSERT INTO `play_orders` (`store_id`, `open_id`, `in_time`, `out_time`, `play_time`, `amount`, `settle_status`, `unit_price`, `comment`, `created_at`, `id`, `updated_at`, `billing_mode`) VALUES (870927002, 'MOCK_SETTLE_20260927_u2', '2026-07-20 10:00:00', '2026-07-20 12:00:00', 2, 9000, 1, 4500, 'MOCK模拟订单', '2026-07-20 12:00:00', 870927144, '2026-07-01 00:00:00', 0);

INSERT INTO `pay_orders` (`store_id`, `open_id`, `amount`, `total_amount`, `wallet_amount`, `wechat_amount`, `pay_type`, `pay_status`, `pay_end_time`, `created_at`, `order_id`, `description`, `play_order_id`, `id`, `updated_at`, `wallet_refund_amount`, `wechat_refund_amount`) VALUES (870927002, 'MOCK_SETTLE_20260927_u2', 9000, 9000, 9000, 0, 3, 1, '2026-07-20 12:00:00', '2026-07-20 12:00:00', 'MOCK_SETTLE_20260927_cross-batch', 'MOCK模拟支付', 870927144, 870927145, '2026-07-01 00:00:00', 0, 0);

INSERT INTO `refund_requests` (`open_id`, `order_type`, `order_id`, `pay_order_id`, `amount`, `status`, `created_at`, `reviewed_at`, `refunded_at`, `out_refund_no`, `review_remark`, `id`, `updated_at`) VALUES ('MOCK_SETTLE_20260927_u2', 'play', 870927142, 870927143, 12000, 'refunded', '2026-08-05 12:00:00', '2026-08-05 12:00:00', '2026-08-05 12:00:00', 'MOCK_SETTLE_20260927870927143', 'MOCK已成功退款，无外部调用', 870927146, '2026-07-01 00:00:00');

INSERT INTO `settlement_allocations` (`biz_key`, `batch_id`, `kind`, `open_id`, `reference`, `store_id`, `amount`, `principal`, `state`, `created_at`, `id`, `expense_key`) VALUES ('MOCK_SETTLE_20260927:wallet:870927143:870927136', 870927136, 'wallet', 'MOCK_SETTLE_20260927_u2', 'pay:870927143', 870927001, 6000, 5000, 'returned', '2026-07-15 12:00:00', 870927147, '');

INSERT INTO `settlement_allocations` (`biz_key`, `batch_id`, `kind`, `open_id`, `reference`, `store_id`, `amount`, `principal`, `state`, `created_at`, `id`, `expense_key`) VALUES ('MOCK_SETTLE_20260927:wallet:870927145:870927136', 870927136, 'wallet', 'MOCK_SETTLE_20260927_u2', 'pay:870927145', 870927002, 6000, 5000, 'consumed', '2026-07-20 12:00:00', 870927148, '');

INSERT INTO `settlement_allocations` (`biz_key`, `batch_id`, `kind`, `open_id`, `reference`, `store_id`, `amount`, `principal`, `state`, `created_at`, `id`, `expense_key`) VALUES ('MOCK_SETTLE_20260927:wallet:870927145:870927141', 870927141, 'wallet', 'MOCK_SETTLE_20260927_u2', 'pay:870927145', 870927002, 3000, 1500, 'consumed', '2026-07-20 12:00:00', 870927149, '');

INSERT INTO `wallet_transactions` (`open_id`, `account_id`, `type`, `direction`, `amount`, `balance_before`, `balance_after`, `frozen_before`, `frozen_after`, `biz_key`, `remark`, `created_at`, `related_pay_order_id`, `id`, `updated_at`) VALUES ('MOCK_SETTLE_20260927_u2', 870927131, 'consume', 'out', 6000, 22000, 16000, 0, 0, 'MOCK_SETTLE_20260927:wallet:49', 'MOCK储值流水', '2026-07-15 12:00:00', 870927143, 870927150, '2026-07-01 00:00:00');

INSERT INTO `settlement_entries` (`biz_key`, `month`, `event_at`, `kind`, `reference`, `payer_id`, `receiver_id`, `amount`, `face_amount`, `detail`, `id`, `created_at`) VALUES ('MOCK_SETTLE_20260927:wallet:pay:870927143', '2026-07', '2026-07-15 12:00:00', 'wallet', 'pay:870927143', 0, 870927001, 5000, 6000, 'MOCK按原批次本金比例折算', 870927151, '2026-07-01 00:00:00');

INSERT INTO `wallet_transactions` (`open_id`, `account_id`, `type`, `direction`, `amount`, `balance_before`, `balance_after`, `frozen_before`, `frozen_after`, `biz_key`, `remark`, `created_at`, `related_pay_order_id`, `id`, `updated_at`) VALUES ('MOCK_SETTLE_20260927_u2', 870927131, 'consume', 'out', 9000, 16000, 7000, 0, 0, 'MOCK_SETTLE_20260927:wallet:51', 'MOCK储值流水', '2026-07-20 12:00:00', 870927145, 870927152, '2026-07-01 00:00:00');

INSERT INTO `settlement_entries` (`biz_key`, `month`, `event_at`, `kind`, `reference`, `payer_id`, `receiver_id`, `amount`, `face_amount`, `detail`, `id`, `created_at`) VALUES ('MOCK_SETTLE_20260927:wallet:pay:870927145', '2026-07', '2026-07-20 12:00:00', 'wallet', 'pay:870927145', 0, 870927002, 6500, 9000, 'MOCK按原批次本金比例折算', 870927153, '2026-07-01 00:00:00');

INSERT INTO `wallet_transactions` (`open_id`, `account_id`, `type`, `direction`, `amount`, `balance_before`, `balance_after`, `frozen_before`, `frozen_after`, `biz_key`, `remark`, `created_at`, `related_pay_order_id`, `related_refund_request_id`, `id`, `updated_at`) VALUES ('MOCK_SETTLE_20260927_u2', 870927131, 'refund', 'in', 6000, 7000, 13000, 0, 0, 'MOCK_SETTLE_20260927:wallet:53', 'MOCK储值流水', '2026-08-05 12:00:00', 870927143, 870927146, 870927154, '2026-07-01 00:00:00');

INSERT INTO `settlement_entries` (`biz_key`, `month`, `event_at`, `kind`, `reference`, `payer_id`, `receiver_id`, `amount`, `face_amount`, `detail`, `id`, `created_at`) VALUES ('MOCK_SETTLE_20260927:wallet:refund', '2026-08', '2026-08-05 12:00:00', 'wallet_refund', 'pay:870927143', 0, 870927001, -5000, -6000, 'MOCK跨月退款，退回原本金', 870927155, '2026-07-01 00:00:00');

INSERT INTO `users` (`id`, `open_id`, `nick_name`, `role`, `user_type`, `gender`, `registered_store_id`, `registered_store_source`, `created_at`, `updated_at`, `month_card_expire`) VALUES (870927013, 'MOCK_SETTLE_20260927_u3', 'MOCK-跨月线上卡', 0, 0, 0, 870927001, 'mock', '2026-07-01 00:00:00', '2026-07-01 00:00:00', '2026-08-16 00:00:00');

INSERT INTO `month_card_orders` (`open_id`, `open_period`, `duration_days`, `amount`, `open_type`, `settle_status`, `source`, `store_id`, `effective_at`, `created_at`, `request_key`, `operator`, `remark`, `id`, `updated_at`) VALUES ('MOCK_SETTLE_20260927_u3', 1, 30, 39900, 1, 1, 'wechat', 870927001, '2026-07-17 00:00:00', '2026-07-17 00:00:00', 'MOCK_SETTLE_20260927-card0', 'MOCK', 'MOCK历史卡期，不代表真实收款', 870927157, '2026-07-01 00:00:00');

INSERT INTO `settlement_card_pools` (`source_key`, `order_id`, `open_id`, `starts_at`, `ends_at`, `amount`, `payer_id`, `status`, `id`, `legacy`) VALUES ('card:870927157:0', 870927157, 'MOCK_SETTLE_20260927_u3', '2026-07-17 00:00:00', '2026-08-16 00:00:00', 39900, 0, 'open', 870927158, 0);

INSERT INTO `pay_orders` (`open_id`, `store_id`, `month_card_order_id`, `amount`, `wechat_amount`, `pay_type`, `pay_status`, `pay_end_time`, `created_at`, `order_id`, `id`, `updated_at`, `wallet_amount`, `wallet_refund_amount`, `wechat_refund_amount`) VALUES ('MOCK_SETTLE_20260927_u3', 870927001, 870927157, 39900, 39900, 1, 1, '2026-07-17 00:00:00', '2026-07-17 00:00:00', 'MOCK_SETTLE_20260927-cardpay0', 870927159, '2026-07-01 00:00:00', 0, 0, 0);

INSERT INTO `play_orders` (`store_id`, `open_id`, `in_time`, `out_time`, `play_time`, `amount`, `settle_status`, `billing_mode`, `created_at`, `comment`, `id`, `updated_at`) VALUES (870927001, 'MOCK_SETTLE_20260927_u3', '2026-07-20 00:00:00', '2026-07-20 01:00:00', 1, 0, 1, 2, '2026-07-20 00:00:00', 'MOCK月卡核销', 870927160, '2026-07-01 00:00:00');

INSERT INTO `settlement_card_usages` (`pool_id`, `play_order_id`, `store_id`, `started_at`, `ended_at`, `seconds`, `status`, `note`, `id`) VALUES (870927158, 870927160, 870927001, '2026-07-20 00:00:00', '2026-07-20 01:00:00', 3600, 'review', 'MOCK待核验', 870927161);

INSERT INTO `play_orders` (`store_id`, `open_id`, `in_time`, `out_time`, `play_time`, `amount`, `settle_status`, `billing_mode`, `created_at`, `comment`, `id`, `updated_at`) VALUES (870927002, 'MOCK_SETTLE_20260927_u3', '2026-07-21 00:00:00', '2026-07-21 02:00:00', 2, 0, 1, 2, '2026-07-21 00:00:00', 'MOCK月卡核销', 870927162, '2026-07-01 00:00:00');

INSERT INTO `settlement_card_usages` (`pool_id`, `play_order_id`, `store_id`, `started_at`, `ended_at`, `seconds`, `status`, `note`, `id`) VALUES (870927158, 870927162, 870927002, '2026-07-21 00:00:00', '2026-07-21 02:00:00', 7200, 'valid', 'MOCK正常核销', 870927163);

INSERT INTO `play_orders` (`store_id`, `open_id`, `in_time`, `out_time`, `play_time`, `amount`, `settle_status`, `billing_mode`, `created_at`, `comment`, `id`, `updated_at`) VALUES (870927001, 'MOCK_SETTLE_20260927_u3', '2026-08-02 00:00:00', '2026-08-02 03:00:00', 3, 0, 1, 2, '2026-08-02 00:00:00', 'MOCK月卡核销', 870927164, '2026-07-01 00:00:00');

INSERT INTO `settlement_card_usages` (`pool_id`, `play_order_id`, `store_id`, `started_at`, `ended_at`, `seconds`, `status`, `note`, `id`) VALUES (870927158, 870927164, 870927001, '2026-08-02 00:00:00', '2026-08-02 03:00:00', 10800, 'valid', 'MOCK正常核销', 870927165);

INSERT INTO `play_orders` (`store_id`, `open_id`, `in_time`, `out_time`, `play_time`, `amount`, `settle_status`, `billing_mode`, `created_at`, `comment`, `id`, `updated_at`) VALUES (870927002, 'MOCK_SETTLE_20260927_u3', '2026-08-03 00:00:00', '2026-08-03 01:00:00', 1, 0, 1, 2, '2026-08-03 00:00:00', 'MOCK月卡核销', 870927166, '2026-07-01 00:00:00');

INSERT INTO `settlement_card_usages` (`pool_id`, `play_order_id`, `store_id`, `started_at`, `ended_at`, `seconds`, `status`, `note`, `id`) VALUES (870927158, 870927166, 870927002, '2026-08-03 00:00:00', '2026-08-03 01:00:00', 3600, 'valid', 'MOCK正常核销', 870927167);

INSERT INTO `users` (`id`, `open_id`, `nick_name`, `role`, `user_type`, `gender`, `registered_store_id`, `registered_store_source`, `created_at`, `updated_at`, `month_card_expire`) VALUES (870927014, 'MOCK_SETTLE_20260927_u4', 'MOCK-总部赠卡', 0, 0, 0, 870927001, 'mock', '2026-07-01 00:00:00', '2026-07-01 00:00:00', '2026-07-31 00:00:00');

INSERT INTO `month_card_orders` (`open_id`, `open_period`, `duration_days`, `amount`, `open_type`, `settle_status`, `source`, `store_id`, `effective_at`, `created_at`, `request_key`, `operator`, `remark`, `id`, `updated_at`) VALUES ('MOCK_SETTLE_20260927_u4', 1, 30, 39900, 1, 1, 'gift', 870927001, '2026-07-01 00:00:00', '2026-07-01 00:00:00', 'MOCK_SETTLE_20260927-card1', 'MOCK', 'MOCK历史卡期，不代表真实收款', 870927169, '2026-07-01 00:00:00');

INSERT INTO `settlement_card_pools` (`source_key`, `order_id`, `open_id`, `starts_at`, `ends_at`, `amount`, `payer_id`, `status`, `id`, `legacy`) VALUES ('card:870927169:0', 870927169, 'MOCK_SETTLE_20260927_u4', '2026-07-01 00:00:00', '2026-07-31 00:00:00', 39900, 0, 'open', 870927170, 0);

INSERT INTO `play_orders` (`store_id`, `open_id`, `in_time`, `out_time`, `play_time`, `amount`, `settle_status`, `billing_mode`, `created_at`, `comment`, `id`, `updated_at`) VALUES (870927003, 'MOCK_SETTLE_20260927_u4', '2026-07-18 00:00:00', '2026-07-18 01:00:00', 1, 0, 1, 2, '2026-07-18 00:00:00', 'MOCK月卡核销', 870927171, '2026-07-01 00:00:00');

INSERT INTO `settlement_card_usages` (`pool_id`, `play_order_id`, `store_id`, `started_at`, `ended_at`, `seconds`, `status`, `note`, `id`) VALUES (870927170, 870927171, 870927003, '2026-07-18 00:00:00', '2026-07-18 01:00:00', 3600, 'valid', 'MOCK正常核销', 870927172);

INSERT INTO `users` (`id`, `open_id`, `nick_name`, `role`, `user_type`, `gender`, `registered_store_id`, `registered_store_source`, `created_at`, `updated_at`, `month_card_expire`) VALUES (870927015, 'MOCK_SETTLE_20260927_u5', 'MOCK-第三方验券', 0, 0, 0, 870927001, 'mock', '2026-07-01 00:00:00', '2026-07-01 00:00:00', '2026-07-31 00:00:00');

INSERT INTO `month_card_orders` (`open_id`, `open_period`, `duration_days`, `amount`, `open_type`, `settle_status`, `source`, `store_id`, `effective_at`, `created_at`, `request_key`, `operator`, `remark`, `id`, `updated_at`) VALUES ('MOCK_SETTLE_20260927_u5', 1, 30, 39900, 1, 1, 'third_party', 870927001, '2026-07-01 00:00:00', '2026-07-01 00:00:00', 'MOCK_SETTLE_20260927-card2', 'MOCK', 'MOCK历史卡期，不代表真实收款', 870927174, '2026-07-01 00:00:00');

INSERT INTO `settlement_card_pools` (`source_key`, `order_id`, `open_id`, `starts_at`, `ends_at`, `amount`, `payer_id`, `status`, `id`, `legacy`) VALUES ('card:870927174:0', 870927174, 'MOCK_SETTLE_20260927_u5', '2026-07-01 00:00:00', '2026-07-31 00:00:00', 39900, 0, 'open', 870927175, 0);

INSERT INTO `settlement_card_remittances` (`order_id`, `voucher_key`, `channel`, `external_no`, `store_id`, `amount`, `created_at`, `status`, `id`, `payment_ref`) VALUES (870927174, '9999999999999999999999999999999999999999999999999999999999999999', 'MOCK美团', 'MOCK_SETTLE_20260927-voucher', 870927001, 39900, '2026-07-01 00:00:00', 'pending', 870927176, '');

INSERT INTO `play_orders` (`store_id`, `open_id`, `in_time`, `out_time`, `play_time`, `amount`, `settle_status`, `billing_mode`, `created_at`, `comment`, `id`, `updated_at`) VALUES (870927001, 'MOCK_SETTLE_20260927_u5', '2026-07-18 00:00:00', '2026-07-18 01:00:00', 1, 0, 1, 2, '2026-07-18 00:00:00', 'MOCK月卡核销', 870927177, '2026-07-01 00:00:00');

INSERT INTO `settlement_card_usages` (`pool_id`, `play_order_id`, `store_id`, `started_at`, `ended_at`, `seconds`, `status`, `note`, `id`) VALUES (870927175, 870927177, 870927001, '2026-07-18 00:00:00', '2026-07-18 01:00:00', 3600, 'valid', 'MOCK正常核销', 870927178);

INSERT INTO `users` (`id`, `open_id`, `nick_name`, `role`, `user_type`, `gender`, `registered_store_id`, `registered_store_source`, `created_at`, `updated_at`, `month_card_expire`) VALUES (870927016, 'MOCK_SETTLE_20260927_u6', 'MOCK-从未使用归总部', 0, 0, 0, 870927001, 'mock', '2026-07-01 00:00:00', '2026-07-01 00:00:00', '2026-07-31 00:00:00');

INSERT INTO `month_card_orders` (`open_id`, `open_period`, `duration_days`, `amount`, `open_type`, `settle_status`, `source`, `store_id`, `effective_at`, `created_at`, `request_key`, `operator`, `remark`, `id`, `updated_at`) VALUES ('MOCK_SETTLE_20260927_u6', 1, 30, 39900, 1, 1, 'wechat', 870927001, '2026-07-01 00:00:00', '2026-07-01 00:00:00', 'MOCK_SETTLE_20260927-card3', 'MOCK', 'MOCK历史卡期，不代表真实收款', 870927180, '2026-07-01 00:00:00');

INSERT INTO `settlement_card_pools` (`source_key`, `order_id`, `open_id`, `starts_at`, `ends_at`, `amount`, `payer_id`, `status`, `id`, `legacy`) VALUES ('card:870927180:0', 870927180, 'MOCK_SETTLE_20260927_u6', '2026-07-01 00:00:00', '2026-07-31 00:00:00', 39900, 0, 'open', 870927181, 0);

INSERT INTO `pay_orders` (`open_id`, `store_id`, `month_card_order_id`, `amount`, `wechat_amount`, `pay_type`, `pay_status`, `pay_end_time`, `created_at`, `order_id`, `id`, `updated_at`, `wallet_amount`, `wallet_refund_amount`, `wechat_refund_amount`) VALUES ('MOCK_SETTLE_20260927_u6', 870927001, 870927180, 39900, 39900, 1, 1, '2026-07-01 00:00:00', '2026-07-01 00:00:00', 'MOCK_SETTLE_20260927-cardpay3', 870927182, '2026-07-01 00:00:00', 0, 0, 0);

INSERT INTO `users` (`id`, `open_id`, `nick_name`, `role`, `user_type`, `gender`, `registered_store_id`, `registered_store_source`, `created_at`, `updated_at`, `month_card_expire`) VALUES (870927017, 'MOCK_SETTLE_20260927_u7', 'MOCK-七月未用八月补分', 0, 0, 0, 870927001, 'mock', '2026-07-01 00:00:00', '2026-07-01 00:00:00', '2026-08-16 00:00:00');

INSERT INTO `month_card_orders` (`open_id`, `open_period`, `duration_days`, `amount`, `open_type`, `settle_status`, `source`, `store_id`, `effective_at`, `created_at`, `request_key`, `operator`, `remark`, `id`, `updated_at`) VALUES ('MOCK_SETTLE_20260927_u7', 1, 30, 39900, 1, 1, 'wechat', 870927001, '2026-07-17 00:00:00', '2026-07-17 00:00:00', 'MOCK_SETTLE_20260927-card4', 'MOCK', 'MOCK历史卡期，不代表真实收款', 870927184, '2026-07-01 00:00:00');

INSERT INTO `settlement_card_pools` (`source_key`, `order_id`, `open_id`, `starts_at`, `ends_at`, `amount`, `payer_id`, `status`, `id`, `legacy`) VALUES ('card:870927184:0', 870927184, 'MOCK_SETTLE_20260927_u7', '2026-07-17 00:00:00', '2026-08-16 00:00:00', 39900, 0, 'open', 870927185, 0);

INSERT INTO `pay_orders` (`open_id`, `store_id`, `month_card_order_id`, `amount`, `wechat_amount`, `pay_type`, `pay_status`, `pay_end_time`, `created_at`, `order_id`, `id`, `updated_at`, `wallet_amount`, `wallet_refund_amount`, `wechat_refund_amount`) VALUES ('MOCK_SETTLE_20260927_u7', 870927001, 870927184, 39900, 39900, 1, 1, '2026-07-17 00:00:00', '2026-07-17 00:00:00', 'MOCK_SETTLE_20260927-cardpay4', 870927186, '2026-07-01 00:00:00', 0, 0, 0);

INSERT INTO `play_orders` (`store_id`, `open_id`, `in_time`, `out_time`, `play_time`, `amount`, `settle_status`, `billing_mode`, `created_at`, `comment`, `id`, `updated_at`) VALUES (870927002, 'MOCK_SETTLE_20260927_u7', '2026-08-04 00:00:00', '2026-08-04 01:00:00', 1, 0, 1, 2, '2026-08-04 00:00:00', 'MOCK月卡核销', 870927187, '2026-07-01 00:00:00');

INSERT INTO `settlement_card_usages` (`pool_id`, `play_order_id`, `store_id`, `started_at`, `ended_at`, `seconds`, `status`, `note`, `id`) VALUES (870927185, 870927187, 870927002, '2026-08-04 00:00:00', '2026-08-04 01:00:00', 3600, 'valid', 'MOCK正常核销', 870927188);

INSERT INTO `point_product_categories` (`name`, `status`, `id`, `sort`, `created_at`, `updated_at`) VALUES ('MOCK结算测试', 0, 870927189, 0, '2026-07-01 00:00:00', '2026-07-01 00:00:00');

INSERT INTO `point_products` (`name`, `category_id`, `points_price`, `stock`, `status`, `id`, `sort`, `max_redeem_per_user`, `created_at`, `updated_at`) VALUES ('MOCK积分礼品', 870927189, 100, 10, 0, 870927190, 0, -1, '2026-07-01 00:00:00', '2026-07-01 00:00:00');

INSERT INTO `raffles` (`created_at`, `updated_at`, `title`, `description`, `cover_url`, `store_id`, `store_name`, `pickup_instructions`, `entry_mode`, `points_cost`, `draw_mode`, `max_participants`, `participant_count`, `status`, `drawn_at`, `cancel_reason`, `creator_id`, `operator_id`, `request_key`, `request_hash`, `id`) VALUES ('2026-07-10 00:00:00', '2026-07-23 00:00:00', 'MOCK-积分抽奖已开奖', 'MOCK仅结算测试，不发送通知', '', 870927002, 'MOCK-B-跨店履约', '模拟已领取', 'points', 100, 'manual', 2, 1, 'drawn', '2026-07-23 00:00:00', '', 870927011, 870927011, 'MOCK_SETTLE_20260927-raffle', '8888888888888888888888888888888888888888888888888888888888888888', 870927191);

INSERT INTO `raffle_prizes` (`raffle_id`, `name`, `quantity`, `sort`, `id`) VALUES (870927191, 'MOCK奖品', 1, 1, 870927192);

INSERT INTO `users` (`id`, `open_id`, `nick_name`, `role`, `user_type`, `gender`, `registered_store_id`, `registered_store_source`, `created_at`, `updated_at`) VALUES (870927020, 'MOCK_SETTLE_20260927_u10', 'MOCK-积分场景0', 0, 0, 0, 870927001, 'mock', '2026-07-01 00:00:00', '2026-07-01 00:00:00');

INSERT INTO `point_accounts` (`open_id`, `balance`, `status`, `id`, `created_at`, `updated_at`) VALUES ('MOCK_SETTLE_20260927_u10', 0, 0, 870927194, '2026-07-01 00:00:00', '2026-07-01 00:00:00');

INSERT INTO `point_redeem_orders` (`order_no`, `request_key`, `open_id`, `product_id`, `product_name`, `points_price`, `quantity`, `total_points`, `status`, `pickup_store_id`, `verified_at`, `created_at`, `id`, `updated_at`) VALUES ('MOCK_SETTLE_20260927-redeem0', 'MOCK_SETTLE_20260927-redeem0', 'MOCK_SETTLE_20260927_u10', 870927190, 'MOCK积分礼品', 100, 1, 100, 1, 870927001, '2026-07-22 00:00:00', '2026-07-22 00:00:00', 870927195, '2026-07-01 00:00:00');

INSERT INTO `point_transactions` (`open_id`, `account_id`, `type`, `direction`, `amount`, `balance_before`, `balance_after`, `biz_key`, `remark`, `created_at`, `id`, `updated_at`) VALUES ('MOCK_SETTLE_20260927_u10', 870927194, 'mock_earn', 'in', 60, 0, 60, 'MOCK_SETTLE_20260927:earn:0:870927002', 'MOCK来源积分', '2026-07-21 00:00:00', 870927196, '2026-07-01 00:00:00');

INSERT INTO `settlement_batches` (`kind`, `open_id`, `source_key`, `source_store_id`, `responsible_store_id`, `face_total`, `remaining`, `created_at`, `id`, `principal_total`, `principal_remaining`, `frozen`, `legacy`) VALUES ('point', 'MOCK_SETTLE_20260927_u10', 'MOCK_SETTLE_20260927:earn:0:870927002', 870927002, 870927002, 60, 0, '2026-07-21 00:00:00', 870927197, 0, 0, 0, 0);

INSERT INTO `settlement_allocations` (`biz_key`, `batch_id`, `kind`, `open_id`, `reference`, `expense_key`, `store_id`, `amount`, `state`, `created_at`, `id`, `principal`) VALUES ('MOCK_SETTLE_20260927:spend:0:870927002', 870927197, 'point', 'MOCK_SETTLE_20260927_u10', 'redeem:870927195', 'redeem:870927195', 870927001, 60, 'consumed', '2026-07-22 00:00:00', 870927198, 0);

INSERT INTO `point_transactions` (`open_id`, `account_id`, `type`, `direction`, `amount`, `balance_before`, `balance_after`, `biz_key`, `remark`, `created_at`, `id`, `updated_at`) VALUES ('MOCK_SETTLE_20260927_u10', 870927194, 'mock_earn', 'in', 40, 60, 100, 'MOCK_SETTLE_20260927:earn:0:870927003', 'MOCK来源积分', '2026-07-21 00:00:00', 870927199, '2026-07-01 00:00:00');

INSERT INTO `settlement_batches` (`kind`, `open_id`, `source_key`, `source_store_id`, `responsible_store_id`, `face_total`, `remaining`, `created_at`, `id`, `principal_total`, `principal_remaining`, `frozen`, `legacy`) VALUES ('point', 'MOCK_SETTLE_20260927_u10', 'MOCK_SETTLE_20260927:earn:0:870927003', 870927003, 870927003, 40, 0, '2026-07-21 00:00:00', 870927200, 0, 0, 0, 0);

INSERT INTO `settlement_allocations` (`biz_key`, `batch_id`, `kind`, `open_id`, `reference`, `expense_key`, `store_id`, `amount`, `state`, `created_at`, `id`, `principal`) VALUES ('MOCK_SETTLE_20260927:spend:0:870927003', 870927200, 'point', 'MOCK_SETTLE_20260927_u10', 'redeem:870927195', 'redeem:870927195', 870927001, 40, 'consumed', '2026-07-22 00:00:00', 870927201, 0);

INSERT INTO `point_transactions` (`open_id`, `account_id`, `type`, `direction`, `amount`, `balance_before`, `balance_after`, `biz_key`, `related_redeem_order_id`, `remark`, `created_at`, `id`, `updated_at`) VALUES ('MOCK_SETTLE_20260927_u10', 870927194, 'redeem', 'out', 100, 100, 0, 'MOCK_SETTLE_20260927:spent:0', 870927195, 'MOCK积分消费', '2026-07-22 00:00:00', 870927202, '2026-07-01 00:00:00');

INSERT INTO `settlement_expenses` (`expense_key`, `kind`, `source_id`, `created_at`, `completed_at`, `amount`, `provider_id`, `status`, `note`, `id`) VALUES ('redeem:870927195', 'redeem', 870927195, '2026-07-22 00:00:00', '2026-07-22 00:00:00', 10000, 870927001, 'ready', 'MOCK成本已核对', 870927203);

INSERT INTO `users` (`id`, `open_id`, `nick_name`, `role`, `user_type`, `gender`, `registered_store_id`, `registered_store_source`, `created_at`, `updated_at`) VALUES (870927021, 'MOCK_SETTLE_20260927_u11', 'MOCK-积分场景1', 0, 0, 0, 870927001, 'mock', '2026-07-01 00:00:00', '2026-07-01 00:00:00');

INSERT INTO `point_accounts` (`open_id`, `balance`, `status`, `id`, `created_at`, `updated_at`) VALUES ('MOCK_SETTLE_20260927_u11', 0, 0, 870927205, '2026-07-01 00:00:00', '2026-07-01 00:00:00');

INSERT INTO `point_transactions` (`open_id`, `account_id`, `type`, `direction`, `amount`, `balance_before`, `balance_after`, `biz_key`, `remark`, `created_at`, `id`, `updated_at`) VALUES ('MOCK_SETTLE_20260927_u11', 870927205, 'mock_earn', 'in', 100, 0, 100, 'MOCK_SETTLE_20260927:earn:1:870927003', 'MOCK来源积分', '2026-07-22 00:00:00', 870927206, '2026-07-01 00:00:00');

INSERT INTO `settlement_batches` (`kind`, `open_id`, `source_key`, `source_store_id`, `responsible_store_id`, `face_total`, `remaining`, `created_at`, `id`, `principal_total`, `principal_remaining`, `frozen`, `legacy`) VALUES ('point', 'MOCK_SETTLE_20260927_u11', 'MOCK_SETTLE_20260927:earn:1:870927003', 870927003, 870927003, 100, 0, '2026-07-22 00:00:00', 870927207, 0, 0, 0, 0);

INSERT INTO `settlement_allocations` (`biz_key`, `batch_id`, `kind`, `open_id`, `reference`, `expense_key`, `store_id`, `amount`, `state`, `created_at`, `id`, `principal`) VALUES ('MOCK_SETTLE_20260927:spend:1:870927003', 870927207, 'point', 'MOCK_SETTLE_20260927_u11', 'raffle:870927191', 'raffle:870927191', 870927002, 100, 'consumed', '2026-07-23 00:00:00', 870927208, 0);

INSERT INTO `point_transactions` (`open_id`, `account_id`, `type`, `direction`, `amount`, `balance_before`, `balance_after`, `biz_key`, `related_redeem_order_id`, `remark`, `created_at`, `id`, `updated_at`) VALUES ('MOCK_SETTLE_20260927_u11', 870927205, 'raffle', 'out', 100, 100, 0, 'MOCK_SETTLE_20260927:spent:1', NULL, 'MOCK积分消费', '2026-07-23 00:00:00', 870927209, '2026-07-01 00:00:00');

INSERT INTO `settlement_expenses` (`expense_key`, `kind`, `source_id`, `created_at`, `completed_at`, `amount`, `provider_id`, `status`, `note`, `id`) VALUES ('raffle:870927191', 'raffle', 870927191, '2026-07-23 00:00:00', '2026-07-23 00:00:00', 30000, 870927002, 'ready', 'MOCK成本已核对', 870927210);

INSERT INTO `raffle_entries` (`created_at`, `updated_at`, `raffle_id`, `user_id`, `number`, `open_id`, `nick_name`, `avatar`, `points_paid`, `subscribed`, `prize_id`, `id`) VALUES ('2026-07-23 00:00:00', '2026-07-23 00:00:00', 870927191, 870927021, 1, 'MOCK_SETTLE_20260927_u11', 'MOCK-积分场景1', '', 100, 0, 870927192, 870927211);

INSERT INTO `users` (`id`, `open_id`, `nick_name`, `role`, `user_type`, `gender`, `registered_store_id`, `registered_store_source`, `created_at`, `updated_at`) VALUES (870927022, 'MOCK_SETTLE_20260927_u12', 'MOCK-积分场景2', 0, 0, 0, 870927001, 'mock', '2026-07-01 00:00:00', '2026-07-01 00:00:00');

INSERT INTO `point_accounts` (`open_id`, `balance`, `status`, `id`, `created_at`, `updated_at`) VALUES ('MOCK_SETTLE_20260927_u12', 0, 0, 870927213, '2026-07-01 00:00:00', '2026-07-01 00:00:00');

INSERT INTO `point_redeem_orders` (`order_no`, `request_key`, `open_id`, `product_id`, `product_name`, `points_price`, `quantity`, `total_points`, `status`, `pickup_store_id`, `verified_at`, `created_at`, `id`, `updated_at`) VALUES ('MOCK_SETTLE_20260927-redeem2', 'MOCK_SETTLE_20260927-redeem2', 'MOCK_SETTLE_20260927_u12', 870927190, 'MOCK积分礼品', 100, 1, 100, 1, 870927001, '2026-07-24 00:00:00', '2026-07-24 00:00:00', 870927214, '2026-07-01 00:00:00');

INSERT INTO `point_transactions` (`open_id`, `account_id`, `type`, `direction`, `amount`, `balance_before`, `balance_after`, `biz_key`, `remark`, `created_at`, `id`, `updated_at`) VALUES ('MOCK_SETTLE_20260927_u12', 870927213, 'mock_earn', 'in', 100, 0, 100, 'MOCK_SETTLE_20260927:earn:2:870927003', 'MOCK来源积分', '2026-07-23 00:00:00', 870927215, '2026-07-01 00:00:00');

INSERT INTO `settlement_batches` (`kind`, `open_id`, `source_key`, `source_store_id`, `responsible_store_id`, `face_total`, `remaining`, `created_at`, `id`, `principal_total`, `principal_remaining`, `frozen`, `legacy`) VALUES ('point', 'MOCK_SETTLE_20260927_u12', 'MOCK_SETTLE_20260927:earn:2:870927003', 870927003, 870927003, 100, 0, '2026-07-23 00:00:00', 870927216, 0, 0, 0, 0);

INSERT INTO `settlement_allocations` (`biz_key`, `batch_id`, `kind`, `open_id`, `reference`, `expense_key`, `store_id`, `amount`, `state`, `created_at`, `id`, `principal`) VALUES ('MOCK_SETTLE_20260927:spend:2:870927003', 870927216, 'point', 'MOCK_SETTLE_20260927_u12', 'redeem:870927214', 'redeem:870927214', 870927001, 100, 'consumed', '2026-07-24 00:00:00', 870927217, 0);

INSERT INTO `point_transactions` (`open_id`, `account_id`, `type`, `direction`, `amount`, `balance_before`, `balance_after`, `biz_key`, `related_redeem_order_id`, `remark`, `created_at`, `id`, `updated_at`) VALUES ('MOCK_SETTLE_20260927_u12', 870927213, 'redeem', 'out', 100, 100, 0, 'MOCK_SETTLE_20260927:spent:2', 870927214, 'MOCK积分消费', '2026-07-24 00:00:00', 870927218, '2026-07-01 00:00:00');

INSERT INTO `settlement_expenses` (`expense_key`, `kind`, `source_id`, `created_at`, `completed_at`, `amount`, `provider_id`, `status`, `note`, `id`) VALUES ('redeem:870927214', 'redeem', 870927214, '2026-07-24 00:00:00', '2026-07-24 00:00:00', NULL, 870927001, 'needs_cost', '', 870927219);

INSERT INTO `users` (`id`, `open_id`, `nick_name`, `role`, `user_type`, `gender`, `registered_store_id`, `registered_store_source`, `created_at`, `updated_at`) VALUES (870927023, 'MOCK_SETTLE_20260927_u13', 'MOCK-积分场景3', 0, 0, 0, 870927001, 'mock', '2026-07-01 00:00:00', '2026-07-01 00:00:00');

INSERT INTO `point_accounts` (`open_id`, `balance`, `status`, `id`, `created_at`, `updated_at`) VALUES ('MOCK_SETTLE_20260927_u13', 0, 0, 870927221, '2026-07-01 00:00:00', '2026-07-01 00:00:00');

INSERT INTO `point_redeem_orders` (`order_no`, `request_key`, `open_id`, `product_id`, `product_name`, `points_price`, `quantity`, `total_points`, `status`, `pickup_store_id`, `verified_at`, `created_at`, `id`, `updated_at`) VALUES ('MOCK_SETTLE_20260927-redeem3', 'MOCK_SETTLE_20260927-redeem3', 'MOCK_SETTLE_20260927_u13', 870927190, 'MOCK积分礼品', 100, 1, 100, 1, 870927002, '2026-08-10 00:00:00', '2026-08-10 00:00:00', 870927222, '2026-07-01 00:00:00');

INSERT INTO `point_transactions` (`open_id`, `account_id`, `type`, `direction`, `amount`, `balance_before`, `balance_after`, `biz_key`, `remark`, `created_at`, `id`, `updated_at`) VALUES ('MOCK_SETTLE_20260927_u13', 870927221, 'mock_earn', 'in', 100, 0, 100, 'MOCK_SETTLE_20260927:earn:3:870927003', 'MOCK来源积分', '2026-08-09 00:00:00', 870927223, '2026-07-01 00:00:00');

INSERT INTO `settlement_batches` (`kind`, `open_id`, `source_key`, `source_store_id`, `responsible_store_id`, `face_total`, `remaining`, `created_at`, `id`, `principal_total`, `principal_remaining`, `frozen`, `legacy`) VALUES ('point', 'MOCK_SETTLE_20260927_u13', 'MOCK_SETTLE_20260927:earn:3:870927003', 870927003, 870927003, 100, 0, '2026-08-09 00:00:00', 870927224, 0, 0, 0, 0);

INSERT INTO `settlement_allocations` (`biz_key`, `batch_id`, `kind`, `open_id`, `reference`, `expense_key`, `store_id`, `amount`, `state`, `created_at`, `id`, `principal`) VALUES ('MOCK_SETTLE_20260927:spend:3:870927003', 870927224, 'point', 'MOCK_SETTLE_20260927_u13', 'redeem:870927222', 'redeem:870927222', 870927002, 100, 'consumed', '2026-08-10 00:00:00', 870927225, 0);

INSERT INTO `point_transactions` (`open_id`, `account_id`, `type`, `direction`, `amount`, `balance_before`, `balance_after`, `biz_key`, `related_redeem_order_id`, `remark`, `created_at`, `id`, `updated_at`) VALUES ('MOCK_SETTLE_20260927_u13', 870927221, 'redeem', 'out', 100, 100, 0, 'MOCK_SETTLE_20260927:spent:3', 870927222, 'MOCK积分消费', '2026-08-10 00:00:00', 870927226, '2026-07-01 00:00:00');

INSERT INTO `settlement_expenses` (`expense_key`, `kind`, `source_id`, `created_at`, `completed_at`, `amount`, `provider_id`, `status`, `note`, `id`) VALUES ('redeem:870927222', 'redeem', 870927222, '2026-08-10 00:00:00', '2026-08-10 00:00:00', 5000, 870927002, 'ready', 'MOCK成本已核对', 870927227);

INSERT INTO `users` (`id`, `open_id`, `nick_name`, `role`, `user_type`, `gender`, `registered_store_id`, `registered_store_source`, `created_at`, `updated_at`) VALUES (870927030, 'MOCK_SETTLE_20260927_u20', 'MOCK-总部赠分余额', 0, 0, 0, 870927001, 'mock', '2026-07-01 00:00:00', '2026-07-01 00:00:00');

INSERT INTO `point_accounts` (`open_id`, `balance`, `status`, `id`, `created_at`, `updated_at`) VALUES ('MOCK_SETTLE_20260927_u20', 200, 0, 870927229, '2026-07-01 00:00:00', '2026-07-01 00:00:00');

INSERT INTO `point_transactions` (`open_id`, `account_id`, `type`, `direction`, `amount`, `balance_before`, `balance_after`, `biz_key`, `remark`, `id`, `created_at`, `updated_at`) VALUES ('MOCK_SETTLE_20260927_u20', 870927229, 'mock_earn', 'in', 200, 0, 200, 'MOCK_SETTLE_20260927:hq-points', 'MOCK总部活动赠分', 870927230, '2026-07-01 00:00:00', '2026-07-01 00:00:00');

INSERT INTO `settlement_batches` (`kind`, `open_id`, `source_key`, `source_store_id`, `responsible_store_id`, `face_total`, `remaining`, `id`, `created_at`, `principal_total`, `principal_remaining`, `frozen`, `legacy`) VALUES ('point', 'MOCK_SETTLE_20260927_u20', 'MOCK_SETTLE_20260927:hq-points', 0, 0, 200, 200, 870927231, '2026-07-01 00:00:00', 0, 0, 0, 0);

DROP TEMPORARY TABLE `_mock_settlement_guard`;
