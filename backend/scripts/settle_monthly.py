#!/usr/bin/env python3
"""Retired. Kept as a fail-closed entry point for old deployment schedules."""
def run_once(app=None):
    raise RuntimeError('自动月结已停用，请在 OA 手动生成报表并在收付款后确认结算')

if __name__ == '__main__':
    raise SystemExit('自动月结已停用；此脚本不连接数据库、不生成报表、不写结算状态。请移除旧定时任务。')
