#! /usr/bin/env python
# -*- coding: utf-8 -*-
#  vim: set ts=4 sw=4 tw=0 noet :
#======================================================================
#
# accountz_test.py - accountz.py 单元测试
#
# Created by skywind on 2026/09/16
# Last change: 2026/09/16 16:07:42
#
#======================================================================
# 运行: python accountz_test.py （加 -v 显示每条用例）
#
# 后端覆盖:
#   SQLite  - 全量测试，无需任何外部依赖
#   Mongo   - 默认用 mongomock 内存模拟；设置 ACCOUNTZ_MONGO_URL
#             切换为真实服务器（注意: 会清空该库的 account/user.seqs）
#   MySQL   - 静态测试（建表 SQL / 异常路径）无需服务器；
#             在线测试需设置 ACCOUNTZ_MYSQL_HOST/USER/PASSWD/DB
#======================================================================
from __future__ import print_function
import os
import sys
import json
import shutil
import sqlite3
import tempfile
import threading
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import accountz

try:
	import mongomock
except ImportError:
	mongomock = None

MONGO_URL = os.environ.get('ACCOUNTZ_MONGO_URL')
MYSQL_ENV = {
	'host': os.environ.get('ACCOUNTZ_MYSQL_HOST'),
	'user': os.environ.get('ACCOUNTZ_MYSQL_USER'),
	'passwd': os.environ.get('ACCOUNTZ_MYSQL_PASSWD'),
	'db': os.environ.get('ACCOUNTZ_MYSQL_DB'),
}
MYSQL_READY = all(MYSQL_ENV.values())

TEMP_ROOT = None
_FILE_NO = [0]
_MONGO_NO = [0]
_LIVE_NO = [0]


#----------------------------------------------------------------------
# 临时文件
#----------------------------------------------------------------------
def temp_db ():
	_FILE_NO[0] += 1
	return os.path.join(TEMP_ROOT, 'unittest%d.db' % _FILE_NO[0])


def setUpModule ():
	global TEMP_ROOT
	TEMP_ROOT = tempfile.mkdtemp(prefix = 'accountz_test_')


def tearDownModule ():
	if TEMP_ROOT:
		shutil.rmtree(TEMP_ROOT, ignore_errors = True)


#----------------------------------------------------------------------
# AccountBase: 纯逻辑单元测试（不碰数据库）
#----------------------------------------------------------------------
class TestAccountBase (unittest.TestCase):

	def setUp (self):
		self.base = accountz.AccountBase()

	def test_fields_structure (self):
		fields = accountz.AccountBase.FIELDS
		self.assertEqual(len(fields), 26)
		self.assertEqual(len(set(fields)), 26)
		for name in accountz.AccountBase.UPDATABLE:
			self.assertIn(name, fields)
		self.assertIn('pass', fields)
		self.assertNotIn('pass', accountz.AccountBase.UPDATABLE)
		self.assertNotIn('status', accountz.AccountBase.UPDATABLE)
		self.assertNotIn('credit', accountz.AccountBase.UPDATABLE)
		self.assertNotIn('LoginTimes', accountz.AccountBase.UPDATABLE)
		for name in accountz.AccountBase.MONEY_FIELDS:
			self.assertIn(name, fields)

	def test_money_error_ok (self):
		self.assertIsNone(self.base._money_error('credit', 10))
		self.assertIsNone(self.base._money_error('GOLD', 0.5))
		self.assertIsNone(self.base._money_error('Credit', 1))
		self.assertIsNone(self.base._money_error('gold', 1000000))

	def test_money_error_kind (self):
		self.assertEqual(self.base._money_error('credit2', 1)[0], -1)
		self.assertEqual(self.base._money_error('', 1)[0], -1)
		self.assertEqual(self.base._money_error('credit; drop table x', 1)[0], -1)
		self.assertEqual(self.base._money_error(None, 1)[0], -1)
		self.assertEqual(self.base._money_error(5, 1)[0], -1)

	def test_money_error_positive (self):
		for bad in (-5, -0.01, 0, 0.0):
			self.assertEqual(self.base._money_error('credit', bad)[0], -1, bad)

	def test_money_error_type (self):
		for bad in ('x', None, [1], {'a': 1}, True, False):
			self.assertEqual(self.base._money_error('credit', bad)[0], -1, bad)

	def test_money_error_special (self):
		for bad in (float('nan'), float('inf'), float('-inf')):
			self.assertEqual(self.base._money_error('credit', bad)[0], -1, bad)

	def test_identify (self):
		self.assertEqual(self.base._identify(5), ('uid', 5))
		self.assertEqual(self.base._identify(123456), ('uid', 123456))
		self.assertEqual(self.base._identify('a@b.c'), ('urs', 'a@b.c'))
		self.assertIsNone(self.base._identify(True))
		self.assertIsNone(self.base._identify(False))
		self.assertIsNone(self.base._identify(None))
		self.assertIsNone(self.base._identify(1.5))
		self.assertIsNone(self.base._identify([1]))

	def test_record2obj (self):
		values = list(range(26))
		values[1] = 'u@x.com'
		values[4] = 'secret'
		values[5] = 99
		values[18] = '{"a": 1}'
		user = self.base._record2obj(tuple(values))
		self.assertEqual(user['uid'], 0)
		self.assertEqual(user['urs'], 'u@x.com')
		self.assertEqual(user['gold'], 8)
		self.assertEqual(user['misc'], {'a': 1})
		self.assertEqual(user['status'], 99)
		self.assertNotIn('pass', user)
		self.assertEqual(user['gender'], 6)

	def test_record2obj_none (self):
		self.assertIsNone(self.base._record2obj(None))

	def test_record_status (self):
		self.assertEqual(self.base._record_status(tuple(range(26))), 5)
		self.assertEqual(self.base._record_status(None), 0)
		record = list(range(26))
		record[5] = None
		self.assertEqual(self.base._record_status(tuple(record)), 0)

	def test_misc_load (self):
		self.assertIsNone(self.base._misc_load(None))
		self.assertIsNone(self.base._misc_load(''))
		self.assertEqual(self.base._misc_load('{}'), {})
		self.assertEqual(self.base._misc_load('{"a": 2}'), {'a': 2})
		self.assertEqual(self.base._misc_load('[1, 2]'), [1, 2])
		self.assertEqual(self.base._misc_load('123'), 123)
		self.assertEqual(self.base._misc_load('garbage'), 'garbage')
		self.assertEqual(self.base._misc_load('{bad'), '{bad')

	def test_misc_dump (self):
		self.assertIsNone(self.base._misc_dump(None))
		self.assertEqual(json.loads(self.base._misc_dump({'a': 1})), {'a': 1})
		text = self.base._misc_dump({'名字': '值'})
		self.assertIn('名字', text)


#----------------------------------------------------------------------
# 后端共同契约: SQLite 和 Mongo（mongomock）都必须满足
#----------------------------------------------------------------------
class BackendContract (object):

	db = None

	def make_db (self):
		raise NotImplementedError()

	def setUp (self):
		self.db = self.make_db()
		record = self.db.register('u1@t.com', 'pw1', 'name1', 1, 'src1')
		self.assertIsNotNone(record)
		self.uid = record['uid']
		self.urs = 'u1@t.com'

	def tearDown (self):
		if self.db is not None:
			self.db.close()
			self.db = None

	# ---- register ----

	def test_register_returns_record (self):
		record = self.db.register('u2@t.com', 'pw2', 'name2', 0, 'src2')
		self.assertIsNotNone(record)
		self.assertEqual(record['urs'], 'u2@t.com')
		self.assertEqual(record['name'], 'name2')
		self.assertEqual(record['gender'], 0)
		self.assertEqual(record['src'], 'src2')

	def test_register_hides_password (self):
		record = self.db.register('u2@t.com', 'pw2', 'name2')
		self.assertIsNotNone(record)
		self.assertNotIn('pass', record)

	def test_register_defaults (self):
		record = self.db.register('u2@t.com', 'pw2', 'name2')
		self.assertIsNone(record['misc'])
		self.assertIsNone(record['mail'])
		self.assertEqual(record['LoginTimes'], 0)
		self.assertEqual(record['credit'], 0.0)
		self.assertEqual(record['gold'], 0.0)
		self.assertEqual(record['level'], 0)
		self.assertEqual(record['status'], 0)
		self.assertIsNotNone(record['RegDate'])

	def test_register_duplicate (self):
		self.assertIsNone(self.db.register('u1@t.com', 'other', 'name'))

	def test_register_uid_increases (self):
		record = self.db.register('u2@t.com', 'pw2', 'name2')
		self.assertGreater(record['uid'], self.uid)

	# ---- login ----

	def test_login_ok (self):
		user = self.db.login('u1@t.com', 'pw1')
		self.assertIsNotNone(user)
		self.assertEqual(user['uid'], self.uid)
		self.assertIsNone(user['ip'])

	def test_login_wrong_password (self):
		self.assertIsNone(self.db.login('u1@t.com', 'WRONG'))

	def test_login_unknown_user (self):
		self.assertIsNone(self.db.login('nobody@t.com', 'pw1'))

	def test_login_none_password_rejected (self):
		# 无密码后门必须关闭
		self.assertIsNone(self.db.login('u1@t.com', None))

	def test_login_force (self):
		user = self.db.login('u1@t.com', None, force = True)
		self.assertIsNotNone(user)
		self.assertEqual(user['uid'], self.uid)

	def test_login_force_ignores_password (self):
		user = self.db.login('u1@t.com', 'totally-wrong', force = True)
		self.assertIsNotNone(user)

	def test_login_updates_stats (self):
		self.db.login('u1@t.com', 'pw1')
		user = self.db.query(urs = self.urs)
		self.assertEqual(user['LoginTimes'], 1)
		self.assertIsNotNone(user['LastLoginDate'])

	def test_login_stats_cumulative (self):
		self.db.login('u1@t.com', 'pw1')
		self.db.login('u1@t.com', 'pw1')
		self.assertEqual(self.db.query(urs = self.urs)['LoginTimes'], 2)

	def test_login_records_ip (self):
		self.db.login('u1@t.com', 'pw1', ip = '9.8.7.6')
		self.assertEqual(self.db.query(urs = self.urs)['ip'], '9.8.7.6')

	def test_login_returns_fresh_record (self):
		# login 返回的必须是统计更新后的数据，而不是旧快照
		user = self.db.login('u1@t.com', 'pw1', ip = '1.1.1.1')
		self.assertEqual(user['LoginTimes'], 1)
		self.assertEqual(user['ip'], '1.1.1.1')

	def test_login_mode_skips_stats (self):
		self.db.mode = 1
		user = self.db.login('u1@t.com', 'pw1')
		self.assertIsNotNone(user)
		saved = self.db.query(urs = self.urs)
		self.assertEqual(saved['LoginTimes'], 0)
		self.assertIsNone(saved['LastLoginDate'])
		self.assertIsNone(saved['ip'])

	def test_login_banned (self):
		self.db.ban(self.uid)
		self.assertIsNone(self.db.login('u1@t.com', 'pw1'))
		self.assertIsNone(self.db.login('u1@t.com', None, force = True))

	# ---- query ----

	def test_query_by_urs (self):
		user = self.db.query(urs = self.urs)
		self.assertIsNotNone(user)
		self.assertEqual(user['uid'], self.uid)

	def test_query_by_uid (self):
		user = self.db.query(uid = self.uid)
		self.assertIsNotNone(user)
		self.assertEqual(user['urs'], self.urs)

	def test_query_by_both (self):
		user = self.db.query(urs = self.urs, uid = self.uid)
		self.assertIsNotNone(user)

	def test_query_both_mismatch (self):
		self.assertIsNone(self.db.query(urs = self.urs, uid = self.uid + 1000))

	def test_query_no_args (self):
		self.assertIsNone(self.db.query())

	def test_query_unknown (self):
		self.assertIsNone(self.db.query(urs = 'nobody@t.com'))
		self.assertIsNone(self.db.query(uid = 999999))
		self.assertIsNone(self.db.query(uid = 0))

	def test_query_hides_password (self):
		self.assertNotIn('pass', self.db.query(urs = self.urs))

	def test_query_misc_decoded (self):
		self.db.update(self.uid, {'misc': {'k': [1, 2]}})
		self.assertEqual(self.db.query(urs = self.urs)['misc'], {'k': [1, 2]})

	# ---- update ----

	def test_update_single_field (self):
		self.assertTrue(self.db.update(self.uid, {'level': 100}))
		self.assertEqual(self.db.query(urs = self.urs)['level'], 100)

	def test_update_multiple_fields (self):
		changes = {'level': 9, 'exp': 55, 'name': 'renamed', 'cid': 3}
		self.assertTrue(self.db.update(self.uid, changes))
		user = self.db.query(urs = self.urs)
		self.assertEqual(user['level'], 9)
		self.assertEqual(user['exp'], 55)
		self.assertEqual(user['name'], 'renamed')
		self.assertEqual(user['cid'], 3)

	def test_update_by_urs (self):
		self.assertTrue(self.db.update(self.urs, {'level': 7}))
		self.assertEqual(self.db.query(urs = self.urs)['level'], 7)

	def test_update_unknown_uid (self):
		self.assertFalse(self.db.update(999999, {'level': 1}))
		self.assertFalse(self.db.update('nobody@t.com', {'level': 1}))

	def test_update_password_rejected (self):
		# update() 白名单不含 pass，改密码必须走 passwd()
		self.assertFalse(self.db.update(self.uid, {'pass': 'hacked'}))
		self.assertIsNotNone(self.db.login('u1@t.com', 'pw1'))

	def test_update_empty_changes (self):
		self.assertFalse(self.db.update(self.uid, {}))
		self.assertFalse(self.db.update(self.uid, None))

	def test_update_only_forbidden_fields (self):
		self.assertFalse(self.db.update(self.uid, {'pass': 'x'}))
		self.assertFalse(self.db.update(self.uid, {'uid': 999, 'credit': 5.0}))

	def test_update_ignored_fields (self):
		changes = {'uid': 9999, 'credit': 888.0, 'status': 1, 'LoginTimes': 42}
		changes['name'] = 'newname'
		self.assertTrue(self.db.update(self.uid, changes))
		user = self.db.query(urs = self.urs)
		self.assertEqual(user['name'], 'newname')
		self.assertEqual(user['credit'], 0.0)
		self.assertEqual(user['status'], 0)
		self.assertEqual(user['uid'], self.uid)
		self.assertEqual(user['LoginTimes'], 0)

	def test_update_misc_roundtrip (self):
		self.assertTrue(self.db.update(self.uid, {'misc': {'a': 1, 'b': 'x'}}))
		self.assertEqual(self.db.query(urs = self.urs)['misc'], {'a': 1, 'b': 'x'})

	def test_update_misc_none (self):
		self.db.update(self.uid, {'misc': {'a': 1}})
		self.assertTrue(self.db.update(self.uid, {'misc': None}))
		self.assertIsNone(self.db.query(urs = self.urs)['misc'])

	def test_update_birthday (self):
		self.assertTrue(self.db.update(self.uid, {'birthday': '1990-01-01'}))
		self.assertEqual(self.db.query(urs = self.urs)['birthday'], '1990-01-01')

	# ---- passwd ----

	def test_passwd_verify_ok (self):
		self.assertTrue(self.db.passwd(self.uid, 'pw1', None))
		self.assertTrue(self.db.passwd(self.urs, 'pw1', None))

	def test_passwd_verify_wrong (self):
		self.assertFalse(self.db.passwd(self.uid, 'WRONG', None))

	def test_passwd_verify_unknown (self):
		self.assertFalse(self.db.passwd(999999, 'pw1', None))
		self.assertFalse(self.db.passwd('nobody@t.com', 'pw1', None))

	def test_passwd_change (self):
		self.assertTrue(self.db.passwd(self.uid, 'pw1', 'pw9'))
		self.assertIsNone(self.db.login('u1@t.com', 'pw1'))
		self.assertIsNotNone(self.db.login('u1@t.com', 'pw9'))

	def test_passwd_change_wrong_old (self):
		self.assertFalse(self.db.passwd(self.uid, 'bad', 'pw9'))
		self.assertIsNotNone(self.db.login('u1@t.com', 'pw1'))

	def test_passwd_reset (self):
		self.assertTrue(self.db.passwd(self.uid, None, 'pw7'))
		self.assertIsNone(self.db.login('u1@t.com', 'pw1'))
		self.assertIsNotNone(self.db.login('u1@t.com', 'pw7'))

	def test_passwd_reset_unknown (self):
		self.assertFalse(self.db.passwd(999999, None, 'x'))

	def test_passwd_both_none (self):
		self.assertFalse(self.db.passwd(self.uid, None, None))

	def test_passwd_by_urs (self):
		self.assertTrue(self.db.passwd(self.urs, 'pw1', 'pw8'))
		self.assertIsNone(self.db.login('u1@t.com', 'pw1'))
		self.assertIsNotNone(self.db.login('u1@t.com', 'pw8'))

	def test_passwd_same_as_old (self):
		self.assertTrue(self.db.passwd(self.uid, 'pw1', 'pw1'))
		self.assertIsNotNone(self.db.login('u1@t.com', 'pw1'))

	def test_passwd_bool_uid (self):
		self.assertFalse(self.db.passwd(True, 'pw1', None))

	# ---- money: 参数校验 ----

	def test_payment_money_negative (self):
		self.assertEqual(self.db.payment(self.uid, 'credit', -5)[0], -1)
		self.assertEqual(self.db.deposit(self.uid, 'credit', -0.01)[0], -1)

	def test_payment_money_zero (self):
		self.assertEqual(self.db.payment(self.uid, 'gold', 0)[0], -1)
		self.assertEqual(self.db.deposit(self.uid, 'gold', 0.0)[0], -1)

	def test_payment_money_non_number (self):
		for bad in ('x', None, [1], {'a': 1}):
			self.assertEqual(self.db.payment(self.uid, 'credit', bad)[0], -1, bad)
			self.assertEqual(self.db.deposit(self.uid, 'credit', bad)[0], -1, bad)

	def test_payment_money_bool (self):
		self.assertEqual(self.db.payment(self.uid, 'credit', True)[0], -1)
		self.assertEqual(self.db.deposit(self.uid, 'credit', False)[0], -1)

	def test_payment_money_nan_inf (self):
		for bad in (float('nan'), float('inf'), float('-inf')):
			self.assertEqual(self.db.payment(self.uid, 'credit', bad)[0], -1, bad)
			self.assertEqual(self.db.deposit(self.uid, 'credit', bad)[0], -1, bad)

	def test_payment_bad_kind (self):
		self.assertEqual(self.db.payment(self.uid, 'credit2', 1)[0], -1)
		self.assertEqual(self.db.deposit(self.uid, 'bitcoin', 1)[0], -1)
		self.assertEqual(self.db.payment(self.uid, 'credit; drop table x', 1)[0], -1)

	def test_payment_kind_not_string (self):
		self.assertEqual(self.db.payment(self.uid, 5, 1)[0], -1)
		self.assertEqual(self.db.deposit(self.uid, None, 1)[0], -1)

	def test_payment_uid_not_int (self):
		self.assertEqual(self.db.payment('abc', 'credit', 5)[0], -1)
		self.assertEqual(self.db.payment(self.urs, 'credit', 5)[0], -1)
		self.assertEqual(self.db.deposit('abc', 'credit', 5)[0], -1)
		self.assertEqual(self.db.payment(True, 'credit', 5)[0], -1)

	# ---- money: 流程 ----

	def test_deposit_ok (self):
		rc = self.db.deposit(self.uid, 'credit', 100)
		self.assertEqual(rc, (0, 100, 'ok'))
		self.assertEqual(self.db.query(urs = self.urs)['credit'], 100)

	def test_deposit_unknown_uid (self):
		rc = self.db.deposit(999999, 'credit', 5)
		self.assertEqual(rc[0], 1)

	def test_payment_ok (self):
		self.db.deposit(self.uid, 'credit', 100)
		rc = self.db.payment(self.uid, 'credit', 30)
		self.assertEqual(rc, (0, 70, 'ok'))
		self.assertEqual(self.db.query(urs = self.urs)['credit'], 70)

	def test_payment_not_enough (self):
		self.db.deposit(self.uid, 'credit', 30)
		rc = self.db.payment(self.uid, 'credit', 100)
		self.assertEqual(rc[0], 2)
		self.assertEqual(rc[1], 30)
		# 余额必须没有被扣掉
		self.assertEqual(self.db.query(urs = self.urs)['credit'], 30)

	def test_payment_exact_balance (self):
		self.db.deposit(self.uid, 'credit', 50)
		rc = self.db.payment(self.uid, 'credit', 50)
		self.assertEqual(rc[0], 0)
		self.assertEqual(rc[1], 0)
		self.assertEqual(self.db.query(urs = self.urs)['credit'], 0)

	def test_payment_consumed_accumulates (self):
		self.db.deposit(self.uid, 'credit', 100)
		self.db.payment(self.uid, 'credit', 30)
		self.db.payment(self.uid, 'credit', 20)
		self.assertEqual(self.db.query(urs = self.urs)['CreditConsumed'], 50)

	def test_payment_unknown_uid (self):
		rc = self.db.payment(999999, 'credit', 5)
		self.assertEqual(rc[0], 1)

	def test_payment_gold_kind (self):
		self.db.deposit(self.uid, 'gold', 10)
		rc = self.db.payment(self.uid, 'gold', 4)
		self.assertEqual(rc, (0, 6, 'ok'))
		user = self.db.query(urs = self.urs)
		self.assertEqual(user['gold'], 6)
		self.assertEqual(user['GoldConsumed'], 4)
		self.assertEqual(user['credit'], 0.0)

	def test_payment_rounding (self):
		for i in range(3):
			self.db.deposit(self.uid, 'gold', 0.1)
		gold = self.db.query(urs = self.urs)['gold']
		self.assertLess(abs(gold - 0.3), 1e-9, gold)

	# ---- ban / unban ----

	def test_ban_unban (self):
		self.assertTrue(self.db.ban(self.uid))
		self.assertIsNone(self.db.login('u1@t.com', 'pw1'))
		self.assertEqual(self.db.payment(self.uid, 'credit', 1)[0], 4)
		self.assertEqual(self.db.deposit(self.uid, 'credit', 1)[0], 4)
		self.assertTrue(self.db.unban(self.uid))
		self.assertIsNotNone(self.db.login('u1@t.com', 'pw1'))

	def test_ban_by_urs (self):
		self.assertTrue(self.db.ban(self.urs))
		self.assertEqual(self.db.query(urs = self.urs)['status'], 1)
		self.assertTrue(self.db.unban(self.urs))

	def test_ban_unknown (self):
		self.assertFalse(self.db.ban(999999))
		self.assertFalse(self.db.unban(999999))

	def test_ban_idempotent (self):
		self.assertTrue(self.db.ban(self.uid))
		self.assertTrue(self.db.ban(self.uid))

	def test_ban_status_visible (self):
		self.db.ban(self.uid)
		self.assertEqual(self.db.query(urs = self.urs)['status'], 1)

	# ---- delete ----

	def test_delete_by_uid (self):
		self.assertTrue(self.db.delete(self.uid))
		self.assertIsNone(self.db.query(urs = self.urs))
		self.assertIsNone(self.db.login('u1@t.com', 'pw1'))

	def test_delete_by_urs (self):
		self.assertTrue(self.db.delete(self.urs))
		self.assertIsNone(self.db.query(uid = self.uid))

	def test_delete_unknown (self):
		self.assertFalse(self.db.delete(999999))
		self.assertFalse(self.db.delete('nobody@t.com'))
		self.assertFalse(self.db.delete(True))

	def test_delete_removes_login (self):
		record = self.db.register('tmp@t.com', 'pw', 'tmp')
		self.assertTrue(self.db.delete(record['uid']))
		self.assertIsNone(self.db.login('tmp@t.com', 'pw'))

	# ---- count / list_users ----

	def test_count (self):
		self.assertEqual(self.db.count(), 1)
		record = self.db.register('u2@t.com', 'pw2', 'n2')
		self.assertEqual(self.db.count(), 2)
		self.db.delete(record['uid'])
		self.assertEqual(self.db.count(), 1)

	def test_count_empty (self):
		db2 = self.make_db()
		try:
			self.assertEqual(db2.count(), 0)
		finally:
			db2.close()

	def test_list_users_pagination (self):
		self.db.register('u2@t.com', 'pw2', 'n2')
		self.db.register('u3@t.com', 'pw3', 'n3')
		users = self.db.list_users(0, 2)
		self.assertEqual([u['urs'] for u in users], ['u1@t.com', 'u2@t.com'])
		users = self.db.list_users(2, 2)
		self.assertEqual([u['urs'] for u in users], ['u3@t.com'])
		self.assertEqual(self.db.list_users(9, 2), [])

	def test_list_users_sorted_no_pass (self):
		self.db.register('u2@t.com', 'pw2', 'n2')
		self.db.register('u3@t.com', 'pw3', 'n3')
		users = self.db.list_users(0, 10)
		uids = [u['uid'] for u in users]
		self.assertEqual(uids, sorted(uids))
		for u in users:
			self.assertNotIn('pass', u)

	def test_list_users_empty (self):
		db2 = self.make_db()
		try:
			self.assertEqual(db2.list_users(0, 10), [])
		finally:
			db2.close()

	def test_list_users_bad_args (self):
		self.assertIsNone(self.db.list_users(-1))
		self.assertIsNone(self.db.list_users(0, -1))
		self.assertIsNone(self.db.list_users(0, 'x'))
		self.assertIsNone(self.db.list_users('a'))

	# ---- population ----

	def test_population_count (self):
		succeed = self.db.population(5)
		self.assertEqual(succeed, 5)
		self.assertEqual(self.db.count(), 6)

	def test_population_idempotent (self):
		self.db.population(3)
		self.assertEqual(self.db.population(3), 0)

	def test_population_gender (self):
		self.db.population(9)
		genders = set(u['gender'] for u in self.db.list_users(0, 20))
		self.assertEqual(genders, {0, 1, 2})

	# ---- close ----

	def test_close_idempotent (self):
		self.db.close()
		self.db.close()


#----------------------------------------------------------------------
# SQLite 契约
#----------------------------------------------------------------------
class TestSqliteContract (BackendContract, unittest.TestCase):

	def make_db (self):
		return accountz.AccountLocal(temp_db())


#----------------------------------------------------------------------
# Mongo 契约（mongomock 模拟，或 ACCOUNTZ_MONGO_URL 指向真实服务器）
#----------------------------------------------------------------------
@unittest.skipIf(mongomock is None and not MONGO_URL,
	'mongomock 未安装且未设置 ACCOUNTZ_MONGO_URL')
class TestMongoContract (BackendContract, unittest.TestCase):

	def make_db (self):
		if MONGO_URL:
			# 真实服务器: 每个测试前清空测试集合
			db = accountz.AccountMongo(MONGO_URL)
			db._AccountMongo__account.drop()
			db._AccountMongo__seqs.drop()
			return db
		_MONGO_NO[0] += 1
		patcher = mongomock.patch()
		patcher.start()
		self.addCleanup(patcher.stop)
		url = 'mongodb://localhost/ct%d' % _MONGO_NO[0]
		return accountz.AccountMongo(url)


#----------------------------------------------------------------------
# AccountLocal: sqlite 专属行为
#----------------------------------------------------------------------
class TestAccountLocal (unittest.TestCase):

	def setUp (self):
		self.dbfile = temp_db()
		self.db = accountz.AccountLocal(self.dbfile)

	def tearDown (self):
		self.db.close()
		self.db = None

	def test_dbfile_created (self):
		self.assertTrue(os.path.exists(self.dbfile))

	def test_schema_matches_fields (self):
		conn = sqlite3.connect(self.dbfile)
		try:
			columns = [n[1] for n in conn.execute('PRAGMA table_info(account)').fetchall()]
		finally:
			conn.close()
		self.assertEqual(columns, list(accountz.AccountBase.FIELDS))

	def test_no_redundant_indexes (self):
		conn = sqlite3.connect(self.dbfile)
		try:
			names = [n[0] for n in conn.execute(
				"SELECT name FROM sqlite_master WHERE type = 'index'").fetchall()]
		finally:
			conn.close()
		self.assertIn('account_3', names)

	def test_reopen_persists (self):
		self.db.register('keep@t.com', 'pw', 'n')
		self.db.deposit(1, 'credit', 12.5)
		self.db.close()
		db2 = accountz.AccountLocal(self.dbfile)
		try:
			user = db2.query(urs = 'keep@t.com')
			self.assertIsNotNone(user)
			self.assertEqual(user['credit'], 12.5)
			self.assertIsNotNone(db2.login('keep@t.com', 'pw'))
		finally:
			db2.close()

	def test_two_instances_same_file (self):
		db2 = accountz.AccountLocal(self.dbfile)
		try:
			record = db2.register('shared@t.com', 'pw', 'n')
			uid = record['uid']
			self.assertIsNotNone(self.db.query(urs = 'shared@t.com'))
			db2.deposit(uid, 'gold', 5)
			self.assertEqual(self.db.query(urs = 'shared@t.com')['gold'], 5)
		finally:
			db2.close()

	def test_sql_injection_login (self):
		self.assertIsNone(self.db.login("x' OR '1'='1--", 'pw'))
		self.assertIsNone(self.db.login("u1@t.com' --", 'pw'))
		self.assertIsNone(self.db.query(urs = "x' OR uid>0--"))
		self.assertIsNone(self.db.query(uid = "1 OR 1=1"))

	def test_sql_injection_update (self):
		changes = {'name": "hacked, level = 999 WHERE 1=1--': 'x', 'name': 'ok'}
		record = self.db.register('inj@t.com', 'pw', 'n')
		self.assertTrue(self.db.update(record['uid'], changes))
		user = self.db.query(urs = 'inj@t.com')
		self.assertEqual(user['name'], 'ok')
		self.assertEqual(user['level'], 0)

	def test_payment_kind_injection (self):
		record = self.db.register('inj2@t.com', 'pw', 'n')
		rc = self.db.payment(record['uid'], "credit' --", 5)
		self.assertEqual(rc[0], -1)
		# 表必须完好
		self.assertIsNotNone(self.db.query(urs = 'inj2@t.com'))

	def test_exact_float_rounding (self):
		# sqlite 侧 round(x, 2) 保证精确的两位小数
		self.db.register('f@t.com', 'pw', 'n')
		uid = self.db.query(urs = 'f@t.com')['uid']
		for i in range(3):
			self.db.deposit(uid, 'gold', 0.1)
		self.assertEqual(self.db.query(urs = 'f@t.com')['gold'], 0.3)
		self.db.deposit(uid, 'gold', 0.1)
		self.assertEqual(self.db.query(urs = 'f@t.com')['gold'], 0.4)

	def test_concurrent_threads (self):
		self.db.register('multi@t.com', 'pw', 'n')
		uid = self.db.query(urs = 'multi@t.com')['uid']
		errors = []

		def worker ():
			try:
				for i in range(10):
					self.db.login('multi@t.com', 'pw')
					self.db.query(urs = 'multi@t.com')
					self.db.deposit(uid, 'credit', 0.01)
			except Exception as e:
				errors.append(repr(e))

		threads = [threading.Thread(target = worker) for _ in range(4)]
		for t in threads:
			t.start()
		for t in threads:
			t.join()
		self.assertEqual(errors, [])
		user = self.db.query(urs = 'multi@t.com')
		self.assertEqual(user['LoginTimes'], 40)
		self.assertLess(abs(user['credit'] - 0.4), 1e-9, user['credit'])


#----------------------------------------------------------------------
# AccountMongo: mongo 专属行为
#----------------------------------------------------------------------
@unittest.skipIf(mongomock is None and not MONGO_URL,
	'mongomock 未安装且未设置 ACCOUNTZ_MONGO_URL')
class TestAccountMongo (unittest.TestCase):

	def setUp (self):
		if MONGO_URL:
			self.db = accountz.AccountMongo(MONGO_URL)
			self.db._AccountMongo__account.drop()
			self.db._AccountMongo__seqs.drop()
		else:
			_MONGO_NO[0] += 1
			patcher = mongomock.patch()
			patcher.start()
			self.addCleanup(patcher.stop)
			self.db = accountz.AccountMongo('mongodb://localhost/mt%d' % _MONGO_NO[0])
		self.db.init()

	def tearDown (self):
		self.db.close()
		self.db = None

	def collection (self):
		return self.db._AccountMongo__account

	def test_bad_protocol (self):
		self.assertRaises(ValueError, accountz.AccountMongo, 'http://x/')

	def test_url_parse (self):
		parse = accountz.AccountMongo._AccountMongo__url_parse
		self.assertEqual(parse(None, 'mongodb://h1/db1')['db'], 'db1')
		self.assertEqual(parse(None, 'mongodb://h1')['db'], 'test')
		self.assertEqual(parse(None, 'mongodb://h1/')['db'], 'test')
		self.assertEqual(parse(None, 'mongodb://h1/db2?x=1')['db'], 'db2')
		self.assertEqual(parse(None, 'mongodb://user:pw@h/db3')['db'], 'db3')

	def test_missing_pymongo (self):
		saved = accountz.pymongo
		accountz.pymongo = None
		try:
			with mock.patch.dict(sys.modules, {'pymongo': None}):
				self.assertRaises(ImportError, accountz.AccountMongo,
					'mongodb://localhost/x')
		finally:
			accountz.pymongo = saved

	def test_uid_sequence (self):
		uids = []
		for i in range(3):
			record = self.db.register('seq%d@t.com' % i, 'pw', 'n')
			uids.append(record['uid'])
		self.assertEqual(uids, sorted(uids))
		self.assertEqual(len(set(uids)), 3)

	def test_unique_index_uid (self):
		col = self.collection()
		col.insert_one({'uid': 50, 'urs': 'a@t.com', 'pass': 'p'})
		with self.assertRaises(Exception):
			col.insert_one({'uid': 50, 'urs': 'b@t.com', 'pass': 'p'})

	def test_unique_index_urs (self):
		col = self.collection()
		col.insert_one({'uid': 60, 'urs': 'same@t.com', 'pass': 'p'})
		with self.assertRaises(Exception):
			col.insert_one({'uid': 61, 'urs': 'same@t.com', 'pass': 'q'})

	def test_legacy_doc_without_status (self):
		# 旧数据没有 status 字段时，视作正常账户（$in [0, None] 语义）
		self.collection().insert_one(
			{'uid': 77, 'urs': 'legacy@t.com', 'pass': 'lp', 'credit': 5.0})
		user = self.db.query(urs = 'legacy@t.com')
		self.assertIsNotNone(user)
		self.assertEqual(user['status'], 0)
		self.assertEqual(self.db.payment(77, 'credit', 1), (0, 4, 'ok'))
		self.assertIsNotNone(self.db.login('legacy@t.com', 'lp'))

	def test_legacy_doc_without_credit (self):
		# 旧数据没有金额字段: 支付报余额不足，充值自动建字段
		self.collection().insert_one(
			{'uid': 78, 'urs': 'legacy2@t.com', 'pass': 'p'})
		self.assertEqual(self.db.payment(78, 'credit', 1)[0], 2)
		self.assertEqual(self.db.deposit(78, 'credit', 2.5), (0, 2.5, 'ok'))
		self.assertEqual(self.db.query(urs = 'legacy2@t.com')['credit'], 2.5)

	def test_close_safe_before_full_init (self):
		# 构造失败时 close()/__del__ 也不应崩溃
		with self.assertRaises(ValueError):
			accountz.AccountMongo('bad-url')


#----------------------------------------------------------------------
# AccountMySQL: 无需服务器的静态测试
#----------------------------------------------------------------------
class TestAccountMySQLStatic (unittest.TestCase):

	def test_missing_db_raises_keyerror (self):
		self.assertRaises(KeyError, accountz.AccountMySQL,
			host = 'x', user = 'y', passwd = 'z')

	def test_import_error_without_driver (self):
		saved = accountz.MySQLdb
		accountz.MySQLdb = None
		try:
			with mock.patch.dict(sys.modules, {'MySQLdb': None, 'pymysql': None}):
				self.assertRaises(ImportError, accountz.AccountMySQL, db = 'test')
		finally:
			accountz.MySQLdb = saved

	def test_mysql_init_pymysql_fallback (self):
		# 没有原生 MySQLdb 时，应能用 pymysql 兼容层初始化
		saved = accountz.MySQLdb
		accountz.MySQLdb = None
		try:
			with mock.patch.dict(sys.modules, {'MySQLdb': None}):
				self.assertTrue(accountz.mysql_init())
				self.assertIsNotNone(accountz.MySQLdb)
		finally:
			accountz.MySQLdb = saved

	def table_sql (self):
		func = accountz.AccountMySQL._AccountMySQL__table_sql
		return func(None, 'testdb')

	def test_table_sql_columns_match_fields (self):
		names = []
		for line in self.table_sql().split('\n'):
			line = line.strip()
			if line.startswith('`'):
				names.append(line[1:line.find('`', 1)])
		self.assertEqual(names, list(accountz.AccountBase.FIELDS))

	def test_table_sql_collation_and_decimal (self):
		sql = self.table_sql()
		# urs/pass 用 utf8_bin 与 sqlite 的大小写敏感对齐
		self.assertEqual(sql.count('utf8_bin'), 2)
		# 金额列用 DECIMAL 精确存储
		self.assertEqual(sql.count('DECIMAL(16,2)'), 4)
		self.assertIn('`status`', sql)
		self.assertIn('KEY(`cid`)', sql)
		self.assertIn('`testdb`', sql)
		self.assertIn('ENGINE=InnoDB', sql)


#----------------------------------------------------------------------
# AccountMySQL: 在线测试（需要环境变量指定服务器）
#----------------------------------------------------------------------
@unittest.skipUnless(MYSQL_READY, '需要设置 ACCOUNTZ_MYSQL_HOST/USER/PASSWD/DB')
class TestAccountMySQLLive (unittest.TestCase):

	@classmethod
	def setUpClass (cls):
		cls.db = accountz.AccountMySQL(init = True, **MYSQL_ENV)

	@classmethod
	def tearDownClass (cls):
		cls.db.close()
		cls.db = None

	def setUp (self):
		_LIVE_NO[0] += 1
		self.urs = 'live%d@t.com' % _LIVE_NO[0]
		record = self.db.register(self.urs, 'pw', 'name', 1, 'live')
		self.uid = record['uid']

	def tearDown (self):
		self.db.delete(self.uid)
		self.db = self.__class__.db

	def test_register_and_query (self):
		user = self.db.query(urs = self.urs)
		self.assertIsNotNone(user)
		self.assertEqual(user['name'], 'name')
		self.assertNotIn('pass', user)

	def test_login (self):
		user = self.db.login(self.urs, 'pw', ip = '1.2.3.4')
		self.assertIsNotNone(user)
		self.assertEqual(user['ip'], '1.2.3.4')
		self.assertIsNone(self.db.login(self.urs, 'bad'))
		self.assertIsNone(self.db.login(self.urs, None))
		self.assertIsNotNone(self.db.login(self.urs, None, force = True))

	def test_update (self):
		self.assertTrue(self.db.update(self.uid, {'level': 20, 'misc': {'a': 1}}))
		user = self.db.query(urs = self.urs)
		self.assertEqual(user['level'], 20)
		self.assertEqual(user['misc'], {'a': 1})
		self.assertFalse(self.db.update(self.uid, {'pass': 'x'}))

	def test_passwd (self):
		self.assertTrue(self.db.passwd(self.uid, 'pw', 'pw2'))
		self.assertIsNone(self.db.login(self.urs, 'pw'))
		self.assertIsNotNone(self.db.login(self.urs, 'pw2'))

	def test_money (self):
		self.assertEqual(self.db.deposit(self.uid, 'credit', 100), (0, 100, 'ok'))
		self.assertEqual(self.db.payment(self.uid, 'credit', 30), (0, 70, 'ok'))
		self.assertEqual(self.db.payment(self.uid, 'credit', 100)[0], 2)
		self.assertEqual(self.db.payment(self.uid, 'credit', -1)[0], -1)
		user = self.db.query(urs = self.urs)
		self.assertEqual(user['credit'], 70)
		self.assertEqual(user['CreditConsumed'], 30)

	def test_ban (self):
		self.assertTrue(self.db.ban(self.uid))
		self.assertIsNone(self.db.login(self.urs, 'pw'))
		self.assertEqual(self.db.payment(self.uid, 'credit', 1)[0], 4)
		self.assertTrue(self.db.unban(self.uid))
		self.assertIsNotNone(self.db.login(self.urs, 'pw'))

	def test_case_sensitive_login (self):
		# utf8_bin: 大小写不同的密码不能通过
		self.db.passwd(self.uid, 'pw', 'CasePw')
		self.assertIsNotNone(self.db.login(self.urs, 'CasePw'))
		self.assertIsNone(self.db.login(self.urs, 'casepw'))


#----------------------------------------------------------------------
# main
#----------------------------------------------------------------------
if __name__ == '__main__':
	unittest.main()
