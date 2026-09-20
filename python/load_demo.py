#! /usr/bin/env python
# -*- coding: utf-8 -*-
# 在 192.168.1.11 的 MariaDB 上创建 test_account_demo 库并灌入假账号数据。
# 用法:
#   python load_demo.py              # 默认追加 10000 条
#   python load_demo.py 5000         # 追加 5000 条
#   python load_demo.py 10000 42     # 追加 10000 条，随机种子 42（结果可复现）
# 说明:
#   - init=True 自动建库建表；库/表已存在则复用，可反复运行以“追加”更多数据
#   - populate_fake_data 随机生成 urs（set 去重），撞库自动换号重试，可反复追加
import sys, os, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from accountz import AccountMySQL, populate_fake_data

HOST = '192.168.1.11'
USER = 'test'
PASSWD = '678900'
DBNAME = 'test_account_demo'


def main ():
	count = int(sys.argv[1]) if len(sys.argv) > 1 else 10000
	seed = int(sys.argv[2]) if len(sys.argv) > 2 else None
	print('连接 %s，初始化数据库 %s ...' % (HOST, DBNAME))
	db = AccountMySQL(host=HOST, user=USER, passwd=PASSWD, db=DBNAME, init=True)
	before = db.count()
	print('数据库就绪，现有记录: %d，本次追加: %d' % (before, count))
	t = time.time()
	n = populate_fake_data(db, count, seed=seed, verbose=True)
	after = db.count()
	print('完成: 本次写入 %d 条，库内总计 %d 条，耗时 %.1fs' % (n, after, time.time() - t))
	db.close()


if __name__ == '__main__':
	main()
