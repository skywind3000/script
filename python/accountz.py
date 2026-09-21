#! /usr/bin/env python
# -*- coding: utf-8 -*-
#  vim: set ts=4 sw=4 tw=0 noet :
#======================================================================
#
# accountz.py - 账号存储：sqlite / mysql / mongo 三个后端
#
# Created by skywind on 2017/03/16
# Last change: 2026/09/21 15:09:16
#
# 重要字段说明：
#
# - uid: 整数 64 位自增量，内部用户唯一标识
# - urs: 用户字符串唯一标识，一般是用户的登录名
# - cid: 外部 uid，帮忙存储外部用户数据库的整数主键，方便做数据关联
#
# 设计说明：
# 
# 1. 密码按传入值原样存储，哈希/加盐由外层决定，本模块不介入算法；
#    pass 列宽 98，可容纳 bcrypt(60) / argon2id(约 96) 等常见哈希串
# 2. 金额一律以「整数分」记账（BIGINT，1 元 = 100 分），模块内不做小数
#    运算，读出即为分；payment/deposit 的 money 也必须是整数分且大于 0，
#    应用层自己 /100 转成元来显示
# 3. status: 0=正常, 1=封禁（封禁后禁止登录/支付/充值）
# 4. mode: 0/登录时更新统计(LastLoginDate/LoginTimes/ip)，非 0 只验证
# 5. 三个后端行为对齐：字段表、错误码、大小写敏感比较、应用侧时间
# 6. update() 不能修改密码（白名单不含 pass），改密码请用 passwd()
# 7. 索引三端统一为 cid / name（另加 uid/urs 唯一），不再建 src 索引
# 8. 表级约束：status/gender 值域、金额与登录次数非负，DDL 内置 CHECK
#    （MySQL 8.0.16 之前会解析但忽略 CHECK，属预期行为）
# 9. 时间字段以机房所在时区的本地时间为准，不存 UTC
# 10. 数值/状态列一律 NOT NULL DEFAULT 0（cid/status/gender/credit/gold/
#     level/exp/icon/LoginTimes/CreditConsumed/GoldConsumed），RegDate 也是
#     NOT NULL。NULL 会打穿 SQL 三值逻辑（LoginTimes+1、credit>=? 全变 NULL），
#     也会污染 SUM()/AVG() 统计口径；NULL status 还会被当成「未封禁」。
#     cid 是「外部指定的外部 uid」（非自增、非渠道号），BIGINT，0=未绑定。
#     真正的可选资料（birthday/mail/mobile/sign/photo/intro/misc/ip/
#     LastLoginDate/src）保持可空——NULL 与空串语义不同
# 11. uid/cid 三端统一为 int64（有符号 64 位）：sqlite 的 INTEGER 本身就是
#     64 位，mysql 用 BIGINT；超出值域的 uid/cid 参数一律拒绝；mongo 写入侧
#     显式转 bson.Int64（pymongo 默认把 int32 范围内的整数存成 Int32，不转
#     的话存储类型与另两端不一致），自增计数器同样用 Int64
#
#======================================================================
from __future__ import print_function
import sys
import time
import os
import datetime
import sqlite3
import decimal
import threading

try:
	import json
except ImportError:
	import simplejson as json

MySQLdb = None
_MySQLdb_is_pymysql = False		# True: 正在使用 PyMySQL 的 MySQLdb 兼容层
pymongo = None
bson = None


#----------------------------------------------------------------------
# python3 compatible
#----------------------------------------------------------------------
if sys.version_info[0] >= 3:
	unicode = str
	long = int
	xrange = range


#----------------------------------------------------------------------
# AccountBase
#----------------------------------------------------------------------
class AccountBase (object):

	# 字段表，顺序必须与 SELECT * 返回的列顺序一致（SQL 后端按位置取值）
	FIELDS = ( 'uid', 'urs', 'cid', 'name', 'pass', 'status', 'gender',
		'credit', 'gold', 'level', 'exp', 'birthday', 'icon', 'mail',
		'mobile', 'sign', 'photo', 'intro', 'misc', 'src', 'ip', 'RegDate',
		'LastLoginDate', 'LoginTimes', 'CreditConsumed', 'GoldConsumed' )

	# 金额相关字段
	MONEY_FIELDS = ( 'credit', 'gold', 'CreditConsumed', 'GoldConsumed' )

	# NOT NULL DEFAULT 0 的整数字段：三端统一「缺失即 0」，不允许 NULL。
	# cid 是外部指定的外部 uid（非自增、非渠道号），0 表示未绑定。
	# uid 不在此列（mongo 由自增序列提供，SQL 端是主键）。
	ZERO_FIELDS = ( 'cid', 'status', 'gender', 'credit', 'gold', 'level',
		'exp', 'icon', 'LoginTimes', 'CreditConsumed', 'GoldConsumed' )

	# 统一按 int64（有符号 64 位整数）处理的字段：sqlite 的 INTEGER 本身就是
	# 64 位，mysql 用 BIGINT；mongo 写入前需显式转 bson.Int64（pymongo 会把
	# int32 范围内的整数编码成 Int32）。超出值域的参数一律拒绝。
	INT64_FIELDS = ( 'uid', 'cid' )
	INT64_MIN = -(2 ** 63)
	INT64_MAX = 2 ** 63 - 1

	# 日期字段：对外 API 统一用字符串（与 sqlite 一致），mysql/mongo 内部转换。
	# key=字段名，value=strftime 格式（birthday 只有日期，另两个含时分秒）
	DATE_FIELDS = {
		'birthday': '%Y-%m-%d',
		'RegDate': '%Y-%m-%d %H:%M:%S',
		'LastLoginDate': '%Y-%m-%d %H:%M:%S',
	}

	# update() 允许修改的字段（不含 pass，密码只能通过 passwd() 修改）
	UPDATABLE = ( 'cid', 'name', 'gender', 'icon', 'mail', 'mobile',
		'photo', 'misc', 'level', 'exp', 'birthday', 'sign',
		'intro', 'src' )

	def __init__ (self):
		self.mode = 0
		self._names = {}
		for i, v in enumerate(self.FIELDS):
			self._names[v] = i
		self._updatable = set(self.UPDATABLE)

	# 检查金额参数（单位：分，必须是非 0 整数），无错误返回 None，
	# 有错误返回 (-1, 0, 原因) 元组
	def _money_error (self, kind, money):
		if not isinstance(kind, (str, unicode)):
			return (-1, 0, 'money kind must be a string: %s' % (repr(kind),))
		if kind.lower() not in ('credit', 'gold'):
			return (-1, 0, 'money kind error %s' % (kind,))
		if isinstance(money, bool) or not isinstance(money, (int, float, long)):
			return (-1, 0, 'money must be a number: %s' % (repr(money),))
		if isinstance(money, float):
			if money != money or money == float('inf') or money == float('-inf'):
				return (-1, 0, 'money must be a finite number: %s' % (money,))
		if money != int(money):
			# 金额单位是「分」：30.5 这类小数要拒绝，不能被当成 30.5 分
			return (-1, 0, 'money must be integer cents: %s' % (money,))
		if money <= 0:
			return (-1, 0, 'money must be positive: %s' % (money,))
		return None

	# 识别账号标识：int -> ('uid', 值)，str -> ('urs', 值)，无效 -> None
	# 注意 bool 是 int 的子类，True 会被当作 uid=1，这里显式拒绝
	def _identify (self, uid):
		if self._is_int64(uid):
			return ('uid', uid)
		if isinstance(uid, (str, unicode)):
			return ('urs', uid)
		return None

	# 是否为合法 int64 整数（bool 不算，超出 64 位值域的 int 也不算）：
	# uid/cid 三端统一按 int64 处理，超界值直接拒绝，避免 sqlite 绑定溢出、
	# mysql 截断告警、mongo 存成任意精度长整型三种不一致的失败方式
	def _is_int64 (self, v):
		if isinstance(v, bool) or not isinstance(v, (int, long)):
			return False
		return self.INT64_MIN <= v <= self.INT64_MAX

	# 数据库记录转字典（SQL 后端按列位置），misc 为 json 文本时解码，
	# 解码失败时保留原始字符串，避免脏数据无声丢失
	def _record2obj (self, record):
		if record is None:
			return None
		user = {}
		for i, k in enumerate(self.FIELDS):
			v = record[i]
			if k == 'misc':
				user[k] = self._misc_load(v)
			elif k != 'pass':
				user[k] = v
		return user

	# 从记录里取 status
	def _record_status (self, record):
		if record is None:
			return 0
		return record[self._names['status']] or 0

	# misc 字段解码：json 文本 -> 对象，坏数据 -> 原样返回字符串
	def _misc_load (self, v):
		if not v:
			return None
		try:
			return json.loads(v)
		except (ValueError, TypeError):
			return v

	# misc 字段编码
	def _misc_dump (self, v):
		if v is None:
			return None
		return json.dumps(v, ensure_ascii = False)

	# 日期字段读出：数据库原生时间对象 -> 字符串（mysql/mongo 统一返回 str，
	# 与 sqlite 对齐）。非时间对象（如已是 str 或 None）原样返回。
	def _date_str (self, field, value):
		if isinstance(value, (datetime.datetime, datetime.date)):
			fmt = self.DATE_FIELDS.get(field, '%Y-%m-%d %H:%M:%S')
			return value.strftime(fmt)
		return value

	# 日期字段写入：字符串 -> datetime（mongo 存储前内部转换；mysql 直接把 str
	# 交给引擎解析，无需调用本方法）。None/非字符串原样返回；解析失败也原样
	# 返回，避免脏数据导致崩溃。
	def _date_obj (self, field, value):
		if value is None or not isinstance(value, (str, unicode)):
			return value
		fmt = self.DATE_FIELDS.get(field)
		fmts = (fmt, '%Y-%m-%d %H:%M:%S', '%Y-%m-%d') if fmt else \
			('%Y-%m-%d %H:%M:%S', '%Y-%m-%d')
		for f in fmts:
			try:
				return datetime.datetime.strptime(value, f)
			except (ValueError, TypeError):
				pass
		return value


#----------------------------------------------------------------------
# AccountLocal
#----------------------------------------------------------------------
class AccountLocal (AccountBase):

	def __init__ (self, filename, timeout = 5.0):
		AccountBase.__init__(self)
		self.__dbname = os.path.abspath(filename)
		self.__conn = None
		self.__lock = threading.RLock()
		self.__open(timeout)

	def __open (self, timeout):
		sql = '''
		CREATE TABLE IF NOT EXISTS "account" (
		    "uid" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL UNIQUE,
		    "urs" VARCHAR(88) NOT NULL UNIQUE,
		    "cid" BIGINT NOT NULL DEFAULT (0),
		    "name" VARCHAR(32) NOT NULL DEFAULT(''),			
		    "pass" VARCHAR(98) NOT NULL DEFAULT(''),
			"status" INTEGER NOT NULL DEFAULT (0) CHECK ("status" IN (0, 1)),
		    "gender" INTEGER NOT NULL DEFAULT (0) CHECK ("gender" IN (0, 1, 2)),
			"credit" BIGINT NOT NULL DEFAULT (0) CHECK ("credit" >= 0),
		    "gold" BIGINT NOT NULL DEFAULT (0) CHECK ("gold" >= 0),
		    "level" INTEGER NOT NULL DEFAULT (0),
			"exp" INTEGER NOT NULL DEFAULT (0),
			"birthday" DATE,
		    "icon" INTEGER NOT NULL DEFAULT (0),
		    "mail" VARCHAR(88),
		    "mobile" VARCHAR(32), 
			"sign" VARCHAR(32),
			"photo" VARCHAR(256),
			"intro" VARCHAR(256),
			"misc" TEXT,
			"src" VARCHAR(16),
			"ip" VARCHAR(70),
		    "RegDate" DATETIME NOT NULL,
		    "LastLoginDate" DATETIME,
			"LoginTimes" INTEGER NOT NULL DEFAULT (0) CHECK ("LoginTimes" >= 0),
			"CreditConsumed" BIGINT NOT NULL DEFAULT (0) CHECK ("CreditConsumed" >= 0),
			"GoldConsumed" BIGINT NOT NULL DEFAULT (0) CHECK ("GoldConsumed" >= 0)
		);
		CREATE INDEX IF NOT EXISTS "account_cid" ON account (cid);
		CREATE INDEX IF NOT EXISTS "account_name" ON account (name);
		'''

		# timeout 即 sqlite busy_timeout（秒），多线程/多进程防止 database is locked
		c = sqlite3.connect(self.__dbname, isolation_level = 'IMMEDIATE',
			timeout = timeout, check_same_thread = False)
		self.__conn = c

		sql = '\n'.join([ n.strip('\t') for n in sql.split('\n') ])
		sql = sql.strip('\n')

		with self.__lock:
			self.__conn.executescript(sql)
			self.__conn.commit()
		return True

	# 登录，输入用户名和密码，返回用户数据
	# passwd 为 None 且 force=False 时返回 None（拒绝无密码登录）
	# force=True 时跳过密码验证（强制登录），但仍受封禁限制
	def login (self, urs, passwd, ip = None, force = False):
		if not force and passwd is None:
			return None
		with self.__lock:
			c = self.__conn.cursor()
			try:
				if force:
					c.execute('select * from account where urs = ?;', (urs,))
				else:
					c.execute('select * from account where urs = ? and pass = ?;', (urs, passwd))
				record = c.fetchone()
			except sqlite3.Error:
				return None
			finally:
				c.close()
			if record is None:
				return None
			if self._record_status(record) != 0:
				return None
			if self.mode == 0:
				now = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
				try:
					self.__conn.execute('update account set '
						'LastLoginDate = ?, LoginTimes = LoginTimes + 1, ip = ? '
						'where urs = ?;', (now, ip, urs))
					self.__conn.commit()
				except sqlite3.Error:
					self.__conn.rollback()
					# 登录统计失败不影响认证结果
			# 重新查询，返回更新后的最新数据
			return self.query(urs = urs)

	# 查询用户信息：
	#   以 urs读取信息：urs != None, uid == None
	#   以 uid读取信息：urs == None, uid != None
	#   验证 urs/uid匹配：urs != None, uid != None
	# 成功返回用户记录，失败返回 None
	def query (self, urs = None, uid = None):
		if urs is None and uid is None:
			return None
		if uid is not None and not self._is_int64(uid):
			return None		# uid 按 int64 处理，超界/非法类型视为无此用户
		with self.__lock:
			c = self.__conn.cursor()
			try:
				if urs is not None and uid is None:
					c.execute('select * from account where urs = ?;', (urs,))
				elif urs is None and uid is not None:
					c.execute('select * from account where uid = ?;', (uid,))
				else:
					c.execute('select * from account where urs = ? and uid = ?;', (urs, uid))
				record = c.fetchone()
			except sqlite3.Error:
				return None
			finally:
				c.close()
		return self._record2obj(record)

	# 用户注册，返回记录
	def register (self, urs, passwd, name, gender = 0, src = None):
		with self.__lock:
			now = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
			sql = 'INSERT INTO account(urs, pass, name, gender, src, RegDate, status) '
			sql += 'VALUES(?, ?, ?, ?, ?, ?, 0);'
			try:
				self.__conn.execute(sql, (urs, passwd, name, gender, src, now))
				self.__conn.commit()
			except sqlite3.Error:
				self.__conn.rollback()
				return None
			return self.query(urs = urs)

	# 用户更新资料, changes是一个字典，格式和 query返回相同，允许设置字段有：
	# cid, name, gender, icon, mail, mobile, photo, misc, level, exp,
	# birthday, sign, intro, src（密码请使用 passwd()）
	# uid 可以是数字 uid 或者字符串 urs，无匹配返回 False
	def update (self, uid, changes):
		where = self._identify(uid)
		if where is None or not changes:
			return False
		column, value = where
		names, values = [], []
		for k in changes:
			if k not in self._updatable:
				continue
			v = changes[k]
			if k in self.INT64_FIELDS and not self._is_int64(v):
				return False	# cid 等 int64 字段非法值，整体拒绝
			if k == 'misc' and v is not None:
				v = self._misc_dump(v)
			names.append(k)
			values.append(v)
		if not names:
			return False
		sql = 'UPDATE account SET ' + ', '.join(['%s = ?' % n for n in names])
		sql += ' WHERE %s = ?;' % column
		values.append(value)
		with self.__lock:
			try:
				c = self.__conn.execute(sql, tuple(values))
				count = c.rowcount
				c.close()
				self.__conn.commit()
			except sqlite3.Error:
				self.__conn.rollback()
				return False
		return count > 0

	# 更新或者验证密码
	# old == None, passwd != None -> 重置密码
	# old != None, passwd == None -> 验证密码
	# old != None, passwd != None -> 修改密码
	# uid 可以是数字 uid 或者字符串 urs，账户不存在返回 False
	def passwd (self, uid, old, passwd = None):
		if old is None and passwd is None:
			return False
		where = self._identify(uid)
		if where is None:
			return False
		column, value = where
		with self.__lock:
			if old is not None:
				c = self.__conn.cursor()
				try:
					c.execute('SELECT 1 FROM account WHERE %s = ? and pass = ?;' % column,
						(value, old))
					record = c.fetchone()
				except sqlite3.Error:
					return False
				finally:
					c.close()
				if record is None:
					return False
			if passwd is not None and passwd != old:
				try:
					c = self.__conn.execute('UPDATE account SET pass = ? WHERE %s = ?;' % column,
						(passwd, value))
					count = c.rowcount
					c.close()
					self.__conn.commit()
				except sqlite3.Error:
					self.__conn.rollback()
					return False
				if count == 0:
					return False
			return True

	# 支付钱，kind为 'credit'或 'gold'，money是需要支付的钱数（单位：分，必须是大于 0 的整数）
	# 返回 (结果, 还有多少钱, 错误原因)
	# 结果=0支付成功，1用户不存在，2钱不够，3未知错误，4账户封禁，-1参数错误
	def payment (self, uid, kind, money):
		error = self._money_error(kind, money)
		if error is not None:
			return error
		kind = kind.lower()
		money = int(money)		# 单位：分（_money_error 已保证是整数）
		if not self._is_int64(uid):
			return (-1, 0, 'uid must be int64: %s' % (repr(uid),))
		if kind == 'credit':
			x1, x2 = 'credit', 'CreditConsumed'
		else:
			x1, x2 = 'gold', 'GoldConsumed'
		sql = ('UPDATE account SET %s = %s - ?, %s = %s + ? '
			'WHERE uid = ? and %s >= ? and IFNULL(status, 0) = 0;')
		sql = sql % (x1, x1, x2, x2, x1)
		with self.__lock:
			changes = self.__conn.total_changes
			try:
				self.__conn.execute(sql, (money, money, uid, money))
				self.__conn.commit()
			except sqlite3.Error:
				self.__conn.rollback()
			changed = self.__conn.total_changes - changes
		data = self.query(None, uid)
		if data is None:
			return (1, 0, 'bad uid %s' % (repr(uid),))
		if changed == 0:
			if (data.get('status') or 0) != 0:
				return (4, data[x1], 'account banned')
			if data[x1] < money:
				return (2, data[x1], 'not enough %s' % x1)
			return (3, data[x1], 'unknow payment error')
		return (0, data[x1], 'ok')

	# 存钱，kind为 'credit'或 'gold'，money是需要增加的钱数（单位：分，必须是大于 0 的整数）
	def deposit (self, uid, kind, money):
		error = self._money_error(kind, money)
		if error is not None:
			return error
		kind = kind.lower()
		money = int(money)		# 单位：分（_money_error 已保证是整数）
		if not self._is_int64(uid):
			return (-1, 0, 'uid must be int64: %s' % (repr(uid),))
		sql = ('UPDATE account SET %s = %s + ? '
			'WHERE uid = ? and IFNULL(status, 0) = 0;')
		sql = sql % (kind, kind)
		with self.__lock:
			changes = self.__conn.total_changes
			try:
				self.__conn.execute(sql, (money, uid))
				self.__conn.commit()
			except sqlite3.Error:
				self.__conn.rollback()
			changed = self.__conn.total_changes - changes
		data = self.query(None, uid)
		if data is None:
			return (1, 0, 'bad uid %s' % (repr(uid),))
		if changed == 0:
			if (data.get('status') or 0) != 0:
				return (4, data[kind], 'account banned')
			return (2, data[kind], 'unknow deposit error')
		return (0, data[kind], 'ok')

	# 删除账号，uid 可以是数字 uid 或字符串 urs，成功返回 True
	def delete (self, uid):
		where = self._identify(uid)
		if where is None:
			return False
		column, value = where
		with self.__lock:
			try:
				c = self.__conn.execute('DELETE FROM account WHERE %s = ?;' % column, (value,))
				count = c.rowcount
				c.close()
				self.__conn.commit()
			except sqlite3.Error:
				self.__conn.rollback()
				return False
		return count > 0

	# 用户总数，出错返回 -1
	def count (self):
		with self.__lock:
			try:
				c = self.__conn.execute('SELECT COUNT(*) FROM account;')
				record = c.fetchone()
				c.close()
			except sqlite3.Error:
				return -1
		return record[0] if record else 0

	# 分页列出用户，按 uid 升序，返回字典列表（不含密码），出错返回 None
	def list_users (self, offset = 0, limit = 20):
		if isinstance(offset, bool) or not isinstance(offset, int) or \
			isinstance(limit, bool) or not isinstance(limit, int) or \
			offset < 0 or limit < 0:
			return None
		limit = min(limit, 1000)
		with self.__lock:
			c = self.__conn.cursor()
			try:
				c.execute('SELECT * FROM account ORDER BY uid LIMIT ? OFFSET ?;', (limit, offset))
				records = c.fetchall()
			except sqlite3.Error:
				return None
			finally:
				c.close()
		return [ self._record2obj(n) for n in records ]

	# 封禁账户 (status=1)，封禁后无法登录/支付/充值
	def ban (self, uid):
		return self.__set_status(uid, 1)

	# 解除封禁 (status=0)
	def unban (self, uid):
		return self.__set_status(uid, 0)

	def __set_status (self, uid, status):
		where = self._identify(uid)
		if where is None:
			return False
		column, value = where
		with self.__lock:
			try:
				c = self.__conn.execute('UPDATE account SET status = ? WHERE %s = ?;' % column,
					(status, value))
				count = c.rowcount
				c.close()
				self.__conn.commit()
			except sqlite3.Error:
				self.__conn.rollback()
				return False
		return count > 0

	# 向数据库插入随机记录，用于测试
	def population (self, count = 100):
		now = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
		sql = 'INSERT INTO account(urs, name, pass, gender, RegDate) VALUES(?, ?, ?, ?, ?);'
		succeed = 0
		with self.__lock:
			for i in xrange(count):
				urs = '10%d@qq.com' % (i + 1)
				name = 'name%d' % (i + 1)
				try:
					self.__conn.execute(sql, (urs, name, '****', i % 3, now))
					succeed += 1
				except sqlite3.IntegrityError:
					pass
			self.__conn.commit()
		return succeed

	# 关闭数据库连接
	def close (self):
		with self.__lock:
			if self.__conn:
				self.__conn.close()
			self.__conn = None

	# 关闭数据库连接
	def __del__ (self):
		try:
			self.close()
		except Exception:
			pass


#----------------------------------------------------------------------
# initialize MySQLdb
#----------------------------------------------------------------------
def mysql_init():
	global MySQLdb, _MySQLdb_is_pymysql
	if MySQLdb is not None:
		return True
	try:
		import MySQLdb as _mysql
		MySQLdb = _mysql
		_MySQLdb_is_pymysql = False
	except ImportError:
		# 没装 mysqlclient 时退回 PyMySQL 的 MySQLdb 兼容层
		try:
			import pymysql
			pymysql.install_as_MySQLdb()
			import MySQLdb as _mysql
			MySQLdb = _mysql
			_MySQLdb_is_pymysql = True
		except ImportError:
			return False
	return True


# 线程安全装饰器：AccountMySQL 共用一个连接，pymysql/mysqlclient 的单连接
# 并非线程安全（并发 execute/commit 会破坏协议状态）。用可重入锁把每个访问
# 连接的方法整体串行化，语义与 AccountLocal 的 self.__lock 对齐。锁存放在
# self._lock（单下划线，避免名字改写导致装饰器取不到）。
def _locked(fn):
	def wrapper(self, *args, **kwargs):
		with self._lock:
			return fn(self, *args, **kwargs)
	wrapper.__name__ = fn.__name__
	wrapper.__doc__ = fn.__doc__
	return wrapper


#----------------------------------------------------------------------
# AccountMySQL
#----------------------------------------------------------------------
class AccountMySQL (AccountBase):

	def __init__ (self, **argv):
		AccountBase.__init__(self)
		self._lock = threading.RLock()
		self.__argv = {}
		self.__uri = {}
		for k, v in argv.items():
			self.__argv[k] = v
			if k not in ('init', 'db', 'verbose'):
				self.__uri[k] = v
		self.__uri['connect_timeout'] = argv.get('connect_timeout', 10)
		self.__conn = None
		self.__base = None
		self.__verbose = argv.get('verbose', False)
		if 'db' not in argv:
			raise KeyError('not find db name')
		self.__open()

	# 连接参数归一化：pymysql 兼容层把 passwd/db 视为弃用参数（会抛
	# DeprecationWarning），需改用 password/database；原生 mysqlclient 则沿用
	# passwd/db。按当前驱动（_MySQLdb_is_pymysql 标志）转换关键字，保证两种
	# 驱动下都无告警且行为一致。
	@staticmethod
	def _connect_kwargs (uri):
		if not _MySQLdb_is_pymysql:
			return uri
		out = {}
		for k, v in uri.items():
			if k == 'passwd':
				out['password'] = v
			elif k == 'db':
				out['database'] = v
			else:
				out[k] = v
		return out

	def __open (self):
		mysql_init()
		if MySQLdb is None:
			raise ImportError('No module named MySQLdb')
		# FOUND_ROWS: 让 UPDATE 的 rowcount 返回匹配行数，与 sqlite 语义对齐
		try:
			from MySQLdb.constants import CLIENT
			client_flag = CLIENT.FOUND_ROWS
		except ImportError:
			client_flag = 2
		uri = {}
		for k, v in self.__uri.items():
			uri[k] = v
		uri['charset'] = 'utf8'
		uri['client_flag'] = client_flag
		self.__base = uri
		self.__db = self.__argv.get('db', 'account')
		if self.__argv.get('init', False):
			self.__conn = MySQLdb.connect(**self._connect_kwargs(uri))
			return self.init()
		uri = dict(uri)
		uri['db'] = self.__db
		self.__conn = MySQLdb.connect(**self._connect_kwargs(uri))
		return True

	# 输出日志
	def out (self, text):
		if self.__verbose:
			print(text)
		return True

	# 取游标前先 ping，断线自动按建连参数重连（包括当前 db）
	def _cursor (self):
		if self.__conn is None:
			raise MySQLdb.InterfaceError('connection is closed')
		self.__conn.ping(True)
		return self.__conn.cursor()

	# 初始化数据库与表格，结束后带 db 重连
	def init (self):
		database = self.__db
		self.out('create database: %s' % database)
		c = self.__conn.cursor()
		try:
			c.execute('SET sql_notes = 0;')
			c.execute('CREATE DATABASE IF NOT EXISTS %s;' % database)
			c.execute('USE %s;' % database)
			c.execute(self.__table_sql(database))
			self.__conn.commit()
		finally:
			c.close()
		# 重新带 db 连接，保证 ping 重连后不会丢掉当前库
		self.__conn.close()
		uri = dict(self.__base)
		uri['db'] = database
		self.__conn = MySQLdb.connect(**self._connect_kwargs(uri))
		return True

	# 建表语句，urs/pass 用 utf8_bin（与 sqlite 的大小写敏感对齐），
	# 金额用 BIGINT 存整数分、uid/cid 用 BIGINT（与 sqlite/mongo 的 64 位对齐）；
	# 数值/状态列一律 NOT NULL DEFAULT 0（cid 是外部指定的外部 uid，0=未绑定）
	def __table_sql (self, database):
		sql = '''
			CREATE TABLE IF NOT EXISTS `%s`.`account` (
		    `uid` BIGINT PRIMARY KEY NOT NULL AUTO_INCREMENT,
		    `urs` VARCHAR(88) CHARACTER SET utf8 COLLATE utf8_bin NOT NULL UNIQUE KEY,
		    `cid` BIGINT NOT NULL DEFAULT 0,
		    `name` VARCHAR(32) NOT NULL DEFAULT '',			
		    `pass` VARCHAR(98) CHARACTER SET utf8 COLLATE utf8_bin NOT NULL DEFAULT '',
			`status` INT NOT NULL DEFAULT 0 CHECK (`status` IN (0, 1)),
		    `gender` SMALLINT NOT NULL DEFAULT 0 CHECK (`gender` IN (0, 1, 2)),
			`credit` BIGINT NOT NULL DEFAULT 0 CHECK (`credit` >= 0),
		    `gold` BIGINT NOT NULL DEFAULT 0 CHECK (`gold` >= 0),
		    `level` INT NOT NULL DEFAULT 0,
			`exp` INT NOT NULL DEFAULT 0,
			`birthday` DATE,
		    `icon` INT NOT NULL DEFAULT 0,
		    `mail` VARCHAR(88),
		    `mobile` VARCHAR(32), 
			`sign` VARCHAR(32),			
			`photo` VARCHAR(256),
			`intro` VARCHAR(256),
			`misc` TEXT,
			`src` VARCHAR(16),
			`ip` VARCHAR(70),
		    `RegDate` DATETIME NOT NULL,
		    `LastLoginDate` DATETIME,
			`LoginTimes` INT NOT NULL DEFAULT 0 CHECK (`LoginTimes` >= 0),
			`CreditConsumed` BIGINT NOT NULL DEFAULT 0 CHECK (`CreditConsumed` >= 0),
			`GoldConsumed` BIGINT NOT NULL DEFAULT 0 CHECK (`GoldConsumed` >= 0),
			KEY(`cid`),
			KEY(`name`)
			)
		'''
		sql = '\n'.join([ n.strip('\t') for n in sql.split('\n') ])
		sql = sql.strip('\n')
		sql += ' ENGINE=InnoDB DEFAULT CHARSET=utf8;'
		return sql % database

	# 金额列已改为 BIGINT（整数分），读出即 int；这里只对老库残留的
	# Decimal 兜底取整（不做 ×100 换算，旧的 DECIMAL(元) 库须先迁移）
	def _record2obj (self, record):
		user = AccountBase._record2obj(self, record)
		if user is not None:
			for k in self.MONEY_FIELDS:
				if isinstance(user.get(k), decimal.Decimal):
					user[k] = int(user[k])
			for k in self.DATE_FIELDS:
				if k in user:
					user[k] = self._date_str(k, user[k])
		return user

	# 关闭数据库连接
	def close (self):
		if self.__conn:
			self.__conn.close()
		self.__conn = None

	# 关闭数据库连接
	def __del__ (self):
		try:
			self.close()
		except Exception:
			pass

	# 登录，输入用户名和密码，返回用户数据
	# passwd 为 None 且 force=False 时返回 None（拒绝无密码登录）
	# force=True 时跳过密码验证（强制登录），但仍受封禁限制
	def login (self, urs, passwd, ip = None, force = False):
		if not force and passwd is None:
			return None
		try:
			c = self._cursor()
			try:
				if force:
					c.execute('select * from account where urs = %s;', (urs,))
				else:
					c.execute('select * from account where urs = %s and pass = %s;', (urs, passwd))
				record = c.fetchone()
			finally:
				c.close()
		except MySQLdb.Error:
			return None
		if record is None:
			return None
		if self._record_status(record) != 0:
			return None
		if self.mode == 0:
			now = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
			try:
				c = self._cursor()
				try:
					c.execute('update account set LastLoginDate = %s, '
						'LoginTimes = LoginTimes + 1, ip = %s where urs = %s;',
						(now, ip, urs))
				finally:
					c.close()
				self.__conn.commit()
			except MySQLdb.Error:
				try:
					self.__conn.rollback()
				except MySQLdb.Error:
					pass
				# 登录统计失败不影响认证结果
		# 重新查询，返回更新后的最新数据
		return self.query(urs = urs)

	# 查询用户信息：
	#   以 urs读取信息：urs != None, uid == None
	#   以 uid读取信息：urs == None, uid != None
	#   验证 urs/uid匹配：urs != None, uid != None
	# 成功返回用户记录，失败返回 None
	def query (self, urs = None, uid = None):
		if urs is None and uid is None:
			return None
		if uid is not None and not self._is_int64(uid):
			return None		# uid 按 int64 处理，超界/非法类型视为无此用户
		record = None
		try:
			c = self._cursor()
			try:
				if urs is not None and uid is None:
					c.execute('select * from account where urs = %s;', (urs,))
				elif urs is None and uid is not None:
					c.execute('select * from account where uid = %s;', (uid,))
				else:
					c.execute('select * from account where urs = %s and uid = %s;', (urs, uid))
				record = c.fetchone()
			finally:
				c.close()
		except MySQLdb.Error:
			return None
		return self._record2obj(record)

	# 用户注册，返回记录
	def register (self, urs, passwd, name, gender = 0, src = None):
		now = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
		sql = 'INSERT INTO account(urs, pass, name, gender, src, RegDate, status) '
		sql += 'VALUES(%s, %s, %s, %s, %s, %s, 0);'
		try:
			c = self._cursor()
			try:
				c.execute(sql, (urs, passwd, name, gender, src, now))
			finally:
				c.close()
			self.__conn.commit()
		except MySQLdb.Error:
			try:
				self.__conn.rollback()
			except MySQLdb.Error:
				pass
			return None
		return self.query(urs = urs)

	# 用户更新资料, changes是一个字典，格式和 query返回相同，允许设置字段有：
	# cid, name, gender, icon, mail, mobile, photo, misc, level, exp,
	# birthday, sign, intro, src（密码请使用 passwd()）
	# uid 可以是数字 uid 或者字符串 urs，无匹配返回 False
	def update (self, uid, changes):
		where = self._identify(uid)
		if where is None or not changes:
			return False
		column, value = where
		names, values = [], []
		for k in changes:
			if k not in self._updatable:
				continue
			v = changes[k]
			if k in self.INT64_FIELDS and not self._is_int64(v):
				return False	# cid 等 int64 字段非法值，整体拒绝
			if k == 'misc' and v is not None:
				v = self._misc_dump(v)
			names.append(k)
			values.append(v)
		if not names:
			return False
		sql = 'UPDATE account SET ' + ', '.join(['%s = %%s' % n for n in names])
		sql += ' WHERE %s = %%s;' % column
		values.append(value)
		try:
			c = self._cursor()
			try:
				c.execute(sql, tuple(values))
				count = c.rowcount
			finally:
				c.close()
			self.__conn.commit()
		except MySQLdb.Error:
			try:
				self.__conn.rollback()
			except MySQLdb.Error:
				pass
			return False
		return count > 0

	# 更新或者验证密码
	# old == None, passwd != None -> 重置密码
	# old != None, passwd == None -> 验证密码
	# old != None, passwd != None -> 修改密码
	# uid 可以是数字 uid 或者字符串 urs，账户不存在返回 False
	def passwd (self, uid, old, passwd = None):
		if old is None and passwd is None:
			return False
		where = self._identify(uid)
		if where is None:
			return False
		column, value = where
		if old is not None:
			try:
				c = self._cursor()
				try:
					c.execute('SELECT 1 FROM account WHERE %s = %%s and pass = %%s;' % column,
						(value, old))
					record = c.fetchone()
				finally:
					c.close()
			except MySQLdb.Error:
				return False
			if record is None:
				return False
		if passwd is not None and passwd != old:
			try:
				c = self._cursor()
				try:
					c.execute('UPDATE account SET pass = %%s WHERE %s = %%s;' % column,
						(passwd, value))
					count = c.rowcount
				finally:
					c.close()
				self.__conn.commit()
			except MySQLdb.Error:
				try:
					self.__conn.rollback()
				except MySQLdb.Error:
					pass
				return False
			if count == 0:
				return False
		return True

	# 支付钱，kind为 'credit'或 'gold'，money是需要支付的钱数（单位：分，必须是大于 0 的整数）
	# 返回 (结果, 还有多少钱, 错误原因)
	# 结果=0支付成功，1用户不存在，2钱不够，3未知错误，4账户封禁，-1参数错误
	def payment (self, uid, kind, money):
		error = self._money_error(kind, money)
		if error is not None:
			return error
		kind = kind.lower()
		money = int(money)		# 单位：分（_money_error 已保证是整数）
		if not self._is_int64(uid):
			return (-1, 0, 'uid must be int64: %s' % (repr(uid),))
		if kind == 'credit':
			x1, x2 = 'credit', 'CreditConsumed'
		else:
			x1, x2 = 'gold', 'GoldConsumed'
		sql = ('UPDATE account SET %s = %s - %%s, %s = %s + %%s '
			'WHERE uid = %%s and %s >= %%s and IFNULL(status, 0) = 0;')
		sql = sql % (x1, x1, x2, x2, x1)
		changed = 0
		try:
			c = self._cursor()
			try:
				c.execute(sql, (money, money, uid, money))
				changed = c.rowcount
			finally:
				c.close()
			self.__conn.commit()
		except MySQLdb.Error:
			try:
				self.__conn.rollback()
			except MySQLdb.Error:
				pass
			changed = 0
		data = self.query(None, uid)
		if data is None:
			return (1, 0, 'bad uid %s' % (repr(uid),))
		if changed == 0:
			if (data.get('status') or 0) != 0:
				return (4, data[x1], 'account banned')
			if data[x1] < money:
				return (2, data[x1], 'not enough %s' % x1)
			return (3, data[x1], 'unknow payment error')
		return (0, data[x1], 'ok')

	# 存钱，kind为 'credit'或 'gold'，money是需要增加的钱数（单位：分，必须是大于 0 的整数）
	def deposit (self, uid, kind, money):
		error = self._money_error(kind, money)
		if error is not None:
			return error
		kind = kind.lower()
		money = int(money)		# 单位：分（_money_error 已保证是整数）
		if not self._is_int64(uid):
			return (-1, 0, 'uid must be int64: %s' % (repr(uid),))
		sql = ('UPDATE account SET %s = %s + %%s '
			'WHERE uid = %%s and IFNULL(status, 0) = 0;')
		sql = sql % (kind, kind)
		changed = 0
		try:
			c = self._cursor()
			try:
				c.execute(sql, (money, uid))
				changed = c.rowcount
			finally:
				c.close()
			self.__conn.commit()
		except MySQLdb.Error:
			try:
				self.__conn.rollback()
			except MySQLdb.Error:
				pass
			changed = 0
		data = self.query(None, uid)
		if data is None:
			return (1, 0, 'bad uid %s' % (repr(uid),))
		if changed == 0:
			if (data.get('status') or 0) != 0:
				return (4, data[kind], 'account banned')
			return (2, data[kind], 'unknow deposit error')
		return (0, data[kind], 'ok')

	# 删除账号，uid 可以是数字 uid 或字符串 urs，成功返回 True
	def delete (self, uid):
		where = self._identify(uid)
		if where is None:
			return False
		column, value = where
		try:
			c = self._cursor()
			try:
				c.execute('DELETE FROM account WHERE %s = %%s;' % column, (value,))
				count = c.rowcount
			finally:
				c.close()
			self.__conn.commit()
		except MySQLdb.Error:
			try:
				self.__conn.rollback()
			except MySQLdb.Error:
				pass
			return False
		return count > 0

	# 用户总数，出错返回 -1
	def count (self):
		try:
			c = self._cursor()
			try:
				c.execute('SELECT COUNT(*) FROM account;')
				record = c.fetchone()
			finally:
				c.close()
		except MySQLdb.Error:
			return -1
		return record[0] if record else 0

	# 分页列出用户，按 uid 升序，返回字典列表（不含密码），出错返回 None
	def list_users (self, offset = 0, limit = 20):
		if isinstance(offset, bool) or not isinstance(offset, int) or \
			isinstance(limit, bool) or not isinstance(limit, int) or \
			offset < 0 or limit < 0:
			return None
		limit = min(limit, 1000)
		sql = 'SELECT * FROM account ORDER BY uid LIMIT %d OFFSET %d;' % (limit, offset)
		try:
			c = self._cursor()
			try:
				c.execute(sql)
				records = c.fetchall()
			finally:
				c.close()
		except MySQLdb.Error:
			return None
		return [ self._record2obj(n) for n in records ]

	# 封禁账户 (status=1)，封禁后无法登录/支付/充值
	def ban (self, uid):
		return self.__set_status(uid, 1)

	# 解除封禁 (status=0)
	def unban (self, uid):
		return self.__set_status(uid, 0)

	def __set_status (self, uid, status):
		where = self._identify(uid)
		if where is None:
			return False
		column, value = where
		try:
			c = self._cursor()
			try:
				c.execute('UPDATE account SET status = %%s WHERE %s = %%s;' % column,
					(status, value))
				count = c.rowcount
			finally:
				c.close()
			self.__conn.commit()
		except MySQLdb.Error:
			try:
				self.__conn.rollback()
			except MySQLdb.Error:
				pass
			return False
		return count > 0

	# 向数据库插入随机记录，用于测试
	def population (self, count = 100):
		now = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
		succeed = 0
		sql = 'INSERT INTO account(urs, name, pass, gender, RegDate) VALUES(%s, %s, %s, %s, %s);'
		try:
			c = self._cursor()
			try:
				for i in xrange(count):
					urs = '10%d@qq.com' % (i + 1)
					name = 'name%d' % (i + 1)
					try:
						c.execute(sql, (urs, name, '****', i % 3, now))
						succeed += 1
					except MySQLdb.Error:
						pass
			finally:
				c.close()
			self.__conn.commit()
		except MySQLdb.Error:
			pass
		return succeed


# 给 AccountMySQL 所有访问连接的方法统一套上 _locked：单连接非线程安全，
# 需整体串行化（与 AccountLocal 的 self.__lock 语义对齐）。这里集中包裹，
# 避免在十几个方法上逐个写装饰器。_cursor 在这些方法的锁内被调用，无需单独
# 包裹；ban/unban 已包裹，其委托的 __set_status 也在锁内执行。
for _name in ('init', 'close', 'login', 'query', 'register', 'update', 'passwd',
		'payment', 'deposit', 'delete', 'count', 'list_users', 'ban',
		'unban', 'population'):
	setattr(AccountMySQL, _name, _locked(getattr(AccountMySQL, _name)))
del _name


#----------------------------------------------------------------------
# initialize mongodb client
#----------------------------------------------------------------------
def pymongo_init():
	global pymongo, bson
	if pymongo is not None:
		return True
	try:
		import pymongo as _pymongo
		import bson as _bson
		pymongo = _pymongo
		bson = _bson
	except ImportError:
		return False
	return True


#----------------------------------------------------------------------
# AccountMongo
#----------------------------------------------------------------------
class AccountMongo (AccountBase):

	def __init__ (self, url, init = False):
		# 先初始化成员，保证 close()/__del__ 永远可用
		self.__client = None
		self.__db = None
		self.__account = None
		self.__seqs = None
		AccountBase.__init__(self)
		self.__config = self.__url_parse(url)
		self.__url = url
		self.__open()
		self.__account = self.__db.account
		self.__seqs = self.__db['user.seqs']
		# 唯一索引是数据完整性的一部分：uid/urs 的唯一约束不能依赖调用方
		# 记得传 init=True，这里无条件创建（create_index 幂等，已存在则跳过）。
		# init 参数保留仅为兼容旧调用方。
		self.init()

	# 解析 mongo url: mongodb://user:pass@abc.com/database?key=val
	def __url_parse (self, url):
		url = url.strip('\r\n\t ')
		chk = 'mongodb://'
		if url[:len(chk)] != chk:
			raise ValueError('bad protocol: %s' % url)
		config = {}
		config['url'] = url
		url = url[len(chk):]
		p1 = url.find('/')
		if p1 >= 0:
			dbname = url[p1 + 1:]
			p1 = dbname.find('?')
			if p1 >= 0:
				dbname = dbname[:p1]
			if not dbname:
				dbname = 'test'
		else:
			dbname = 'test'
		config['db'] = dbname
		return config

	# 连接数据库
	def __open (self):
		pymongo_init()
		if pymongo is None:
			raise ImportError('No module named pymongo')
		self.__client = pymongo.MongoClient(self.__config['url'])
		self.__db = self.__client[self.__config['db']]
		return self.__db

	# 关闭数据库和客户端连接
	def close (self):
		self.__db = None
		self.__account = None
		self.__seqs = None
		if self.__client is not None:
			try:
				self.__client.close()
			except Exception:
				pass
			self.__client = None
		return True

	# 关闭数据库和客户端连接
	def __del__ (self):
		try:
			self.close()
		except Exception:
			pass

	# 初始化索引（幂等）：uid/urs 唯一约束 + cid/name 查询索引，
	# 与 sqlite/mysql 的索引口径一致（不建 src 索引）；连接时自动调用
	def init (self):
		account = self.__account
		account.create_index([('uid', 1)], unique = True)
		account.create_index([('urs', 1)], unique = True)
		account.create_index([('cid', 1)])
		account.create_index([('name', 1)])
		return True

	# 字段补充
	def __obj_complete (self, obj):
		newobj = {}
		for k in self._names:
			if k != 'pass':
				v = obj.get(k, None)
				if k in self.DATE_FIELDS:
					v = self._date_str(k, v)	# datetime -> str，与 sqlite 对齐
				newobj[k] = v
		if '_id' in obj:
			newobj['_id'] = obj['_id']
		# uid 与 ZERO_FIELDS 在 SQL 端都是 NOT NULL DEFAULT 0：mongo 没有
		# schema，缺字段/存了 null 时在这里统一补 0，保证三端读出值一致
		if newobj['uid'] is None:
			newobj['uid'] = 0
		for k in self.ZERO_FIELDS:
			if newobj.get(k) is None:
				newobj[k] = 0
		return newobj

	# 自增量（用 Int64 增量，计数器字段也保持 64 位，与 uid 口径一致）
	def __id_auto_increment (self, name):
		seqs = self.__seqs
		cc = seqs.find_one_and_update(
			{'_id': name},
			{'$inc': {'next': bson.Int64(1)}},
			{'next': True},
			return_document = pymongo.ReturnDocument.AFTER,
			upsert = True)
		return cc.get('next', 1)

	# 写入前把字典里的 uid/cid 统一转成 bson.Int64：pymongo 默认把 int32
	# 范围内的整数编码成 Int32，显式转 Int64 才与 mysql BIGINT / sqlite
	# INTEGER（64 位）的存储类型对齐
	def __int64_fix (self, obj):
		if bson is None:
			pymongo_init()	# 兜底：正常路径 __open() 已加载 bson
		for k in self.INT64_FIELDS:
			v = obj.get(k, None)
			if isinstance(v, (int, long)) and not isinstance(v, bool):
				obj[k] = bson.Int64(v)
		return obj

	# 登录，输入用户名和密码，返回用户数据
	# passwd 为 None 且 force=False 时返回 None（拒绝无密码登录）
	# force=True 时跳过密码验证（强制登录），但仍受封禁限制
	def login (self, urs, passwd, ip = None, force = False):
		if not force and passwd is None:
			return None
		account = self.__account
		try:
			if force:
				cc = account.find_one({'urs': urs})
			else:
				cc = account.find_one({'urs': urs, 'pass': passwd})
		except pymongo.errors.PyMongoError:
			return None
		if cc is None:
			return None
		if (cc.get('status') or 0) != 0:
			return None
		if self.mode == 0:
			try:
				account.update_one({'_id': cc['_id']},
					{'$set': {'ip': ip, 'LastLoginDate': datetime.datetime.now()},
					 '$inc': {'LoginTimes': 1}})
			except pymongo.errors.PyMongoError:
				pass
		# 重新查询，返回更新后的最新数据
		return self.query(urs = urs)

	# 查询用户信息：
	#   以 urs读取信息：urs != None, uid == None
	#   以 uid读取信息：urs == None, uid != None
	#   验证 urs/uid匹配：urs != None, uid != None
	# 成功返回用户记录，失败返回 None
	def query (self, urs = None, uid = None):
		if urs is None and uid is None:
			return None
		if uid is not None and not self._is_int64(uid):
			return None		# uid 按 int64 处理，超界/非法类型视为无此用户
		account = self.__account
		try:
			if urs is not None and uid is None:
				cc = account.find_one({'urs': urs})
			elif urs is None and uid is not None:
				cc = account.find_one({'uid': uid})
			else:
				cc = account.find_one({'uid': uid, 'urs': urs})
		except pymongo.errors.PyMongoError:
			return None
		if cc is None:
			return None
		cc = self.__obj_complete(cc)
		if '_id' in cc:
			del cc['_id']
		return cc

	# 注册用户，返回记录
	def register (self, urs, passwd, name, gender = 0, src = None):
		account = self.__account
		try:
			cc = account.find_one({'urs': urs}, {'_id': True})
		except pymongo.errors.PyMongoError:
			return None
		if cc is not None:
			return None
		cc = self.__obj_complete({})
		cc['uid'] = self.__id_auto_increment('account')
		cc['urs'] = urs
		cc['name'] = name
		cc['pass'] = passwd
		cc['gender'] = gender
		cc['src'] = src
		cc['LoginTimes'] = 0
		cc['credit'] = 0
		cc['gold'] = 0
		cc['level'] = 0
		cc['exp'] = 0
		cc['CreditConsumed'] = 0
		cc['GoldConsumed'] = 0
		cc['status'] = 0
		cc['RegDate'] = datetime.datetime.now()
		self.__int64_fix(cc)		# uid/cid 以 BSON Int64 存储
		try:
			account.insert_one(cc)
		except (pymongo.errors.DuplicateKeyError, pymongo.errors.PyMongoError):
			return None
		return self.query(urs = urs)

	# 用户更新资料, changes是一个字典，格式和 query返回相同，允许设置字段有：
	# cid, name, gender, icon, mail, mobile, photo, misc, level, exp,
	# birthday, sign, intro, src（密码请使用 passwd()）
	# uid 可以是数字 uid 或者字符串 urs，无匹配返回 False
	def update (self, uid, changes):
		where = self._identify(uid)
		if where is None or not changes:
			return False
		column, value = where
		setting = {}
		for name in self._updatable:
			if name in changes:
				v = changes[name]
				if name in self.DATE_FIELDS:
					v = self._date_obj(name, v)	# str -> datetime，存为 BSON 日期
				elif name in self.INT64_FIELDS:
					# cid 等 int64 字段：先校验值域，再以 BSON Int64 存储
					# （pymongo 默认把 int32 范围内的整数编码成 Int32）
					if not self._is_int64(v):
						return False
					v = bson.Int64(v)
				setting[name] = v
		if not setting:
			return False
		try:
			result = self.__account.update_one({column: value}, {'$set': setting})
		except pymongo.errors.PyMongoError:
			return False
		return result.matched_count > 0

	# 更新或者验证密码
	# old == None, passwd != None -> 重置密码
	# old != None, passwd == None -> 验证密码
	# old != None, passwd != None -> 修改密码
	# uid 可以是数字 uid 或者字符串 urs，账户不存在返回 False
	def passwd (self, uid, old, passwd = None):
		if old is None and passwd is None:
			return False
		where = self._identify(uid)
		if where is None:
			return False
		column, value = where
		account = self.__account
		if old is not None:
			try:
				cc = account.find_one({column: value, 'pass': old})
			except pymongo.errors.PyMongoError:
				return False
			if cc is None:
				return False
		if passwd is not None and passwd != old:
			try:
				result = account.update_one({column: value}, {'$set': {'pass': passwd}})
			except pymongo.errors.PyMongoError:
				return False
			if result.matched_count == 0:
				return False
		return True

	# 支付钱，kind为 'credit'或 'gold'，money是需要支付的钱数（单位：分，必须是大于 0 的整数）
	# 返回 (结果, 还有多少钱, 错误原因)
	# 结果=0支付成功，1用户不存在，2钱不够，3未知错误，4账户封禁，-1参数错误
	def payment (self, uid, kind, money):
		error = self._money_error(kind, money)
		if error is not None:
			return error
		kind = kind.lower()
		money = int(money)		# 单位：分（_money_error 已保证是整数）
		if not self._is_int64(uid):
			return (-1, 0, 'uid must be int64: %s' % (repr(uid),))
		inc = {}
		if kind == 'credit':
			inc['credit'] = -money
			inc['CreditConsumed'] = money
		else:
			inc['gold'] = -money
			inc['GoldConsumed'] = money
		# $in 匹配 status=0/None/字段缺失，与 SQL 的 IFNULL(status,0)=0 对齐
		query = {'uid': uid, 'status': {'$in': [0, None]}, kind: {'$gte': money}}
		hh = None
		try:
			hh = self.__account.find_one_and_update(query, {'$inc': inc})
		except pymongo.errors.PyMongoError:
			hh = None
		data = self.query(None, uid)
		if data is None:
			return (1, 0, 'bad uid %s' % (repr(uid),))
		if hh is None:
			if (data.get('status') or 0) != 0:
				return (4, data[kind], 'account banned')
			if (data[kind] or 0) < money:
				return (2, data[kind] or 0, 'not enough %s' % kind)
			return (3, data[kind] or 0, 'unknow payment error')
		return (0, data[kind], 'ok')

	# 存钱，kind为 'credit'或 'gold'，money是需要增加的钱数（单位：分，必须是大于 0 的整数）
	def deposit (self, uid, kind, money):
		error = self._money_error(kind, money)
		if error is not None:
			return error
		kind = kind.lower()
		money = int(money)		# 单位：分（_money_error 已保证是整数）
		if not self._is_int64(uid):
			return (-1, 0, 'uid must be int64: %s' % (repr(uid),))
		query = {'uid': uid, 'status': {'$in': [0, None]}}
		hh = None
		try:
			hh = self.__account.find_one_and_update(query, {'$inc': {kind: money}})
		except pymongo.errors.PyMongoError:
			hh = None
		data = self.query(None, uid)
		if data is None:
			return (1, 0, 'bad uid %s' % (repr(uid),))
		if hh is None:
			if (data.get('status') or 0) != 0:
				return (4, data[kind], 'account banned')
			return (2, data[kind] or 0, 'unknow deposit error')
		return (0, data[kind], 'ok')

	# 删除账号，uid 可以是数字 uid 或字符串 urs，成功返回 True
	def delete (self, uid):
		where = self._identify(uid)
		if where is None:
			return False
		column, value = where
		try:
			result = self.__account.delete_one({column: value})
		except pymongo.errors.PyMongoError:
			return False
		return result.deleted_count > 0

	# 用户总数，出错返回 -1
	def count (self):
		try:
			return self.__account.count_documents({})
		except pymongo.errors.PyMongoError:
			return -1

	# 分页列出用户，按 uid 升序，返回字典列表（不含密码），出错返回 None
	def list_users (self, offset = 0, limit = 20):
		if isinstance(offset, bool) or not isinstance(offset, int) or \
			isinstance(limit, bool) or not isinstance(limit, int) or \
			offset < 0 or limit < 0:
			return None
		limit = min(limit, 1000)
		users = []
		try:
			cursor = self.__account.find().sort('uid', 1).skip(offset).limit(limit)
			for record in cursor:
				cc = self.__obj_complete(record)
				if '_id' in cc:
					del cc['_id']
				users.append(cc)
		except pymongo.errors.PyMongoError:
			return None
		return users

	# 封禁账户 (status=1)，封禁后无法登录/支付/充值
	def ban (self, uid):
		return self.__set_status(uid, 1)

	# 解除封禁 (status=0)
	def unban (self, uid):
		return self.__set_status(uid, 0)

	def __set_status (self, uid, status):
		where = self._identify(uid)
		if where is None:
			return False
		column, value = where
		try:
			result = self.__account.update_one({column: value}, {'$set': {'status': status}})
		except pymongo.errors.PyMongoError:
			return False
		return result.matched_count > 0

	# 向数据库插入随机记录，用于测试
	def population (self, count = 100):
		succeed = 0
		for i in xrange(count):
			urs = '10%d@qq.com' % i
			name = 'name%d' % i
			gender = i % 3
			if self.register(urs, '****', name, gender, 'auto'):
				succeed += 1
		return succeed


#----------------------------------------------------------------------
# populate_fake_data - 用 Faker 生成随机假账号，写入任意后端
#----------------------------------------------------------------------
def populate_fake_data (db, count, seed = None, verbose = False, locale = 'zh_CN',
	base_time = None):
	'''用 Faker 生成 count 条随机账号，写入 db（AccountLocal/MySQL/Mongo 通用）。

	数据分布（贴近真实用户形态）：
	  - RegDate    : 注册日期均匀分布在最近 10 年，小时按权重重采样（凌晨少、
	                 晚间高峰）
	  - LoginTimes : 长尾分布且与账号年龄关联（日均不超过 3 次，封顶 3000）；
	                 约 8% 用户注册后从未登录（LastLoginDate/ip 同为 NULL）
	  - LastLoginDate: 60% 偏向近期（立方回退），40% 在生命周期内均匀（流失用户）
	  - 金额       : 约 15% 用户有 credit；其中约 85% < 1000，12% 在
	                 1000..10000，3% 在 10000..50000（全部 <= 50000）。有 credit
	                 的用户约 30% 额外再给一份 gold。有金额的用户大多带关联消费史
	                 （CreditConsumed/GoldConsumed），另有约 5% 余额为 0 但消费史
	                 非 0（钱花完了）
	  - level/exp  : level 指数衰减（低等级为主，封顶 120），exp 由 level 推导，
	                 两者自洽
	  - birthday   : 由注册时间反推，保证注册时年满 16 岁，年龄集中在 18-35；
	                 约 15% 用户未填写（NULL）
	  - status     : 约 1.5% 账号被封禁（status=1），可覆盖封禁分支
	  - 资料稀疏   : mail/mobile/sign/photo/intro 按各自概率为 NULL，避免人人
	                 资料齐全；mail 填写时约 40% 与 urs 一致；photo 用站内相对
	                 路径而非外部占位图
	  - name/gender: gender 按权重生成（未知 10%/男 48%/女 42%），名字与性别对应
	  - urs        : QQ 号 / 拼音昵称(+数字) 风格混合，set 去重 + 撞库重试，
	                 无顺序号和随机标签痕迹
	  - src/cid    : src 加权（android>ios>web>invite>wap）；cid 是外部指定的
	                 外部 uid，约 1/4 账号给随机外部号，其余 0（未绑定）
	  - ip         : 公网 IPv4 为主，约 8% IPv6

	实现：账号创建走公共 API register()（顺带拿到自增 uid、跨后端一致），其余
	字段（资料/金额/时间/ip）用一次底层 UPDATE 合并写入——批量生成对网络往返
	敏感，这样比逐字段调用 update()/deposit() 快很多。RegDate/LastLoginDate/
	LoginTimes/ip 本就不在 update() 白名单里。三端日期按本模块约定：对外 str，
	内部各自存储（sqlite 存 str、mysql 存 DATETIME、mongo 存 BSON 日期）。

	参数：
	  db      : 已初始化（表已建好）的后端实例
	  count   : 生成条数
	  seed    : 随机种子，传整数则结果可复现
	  verbose : True 时打印进度
	  locale  : Faker 语言，默认 zh_CN（中文名/手机号）
	  base_time : 基准时间（datetime），默认 datetime.now()；与 seed 一起传
	              固定值可让时间字段也严格可复现
	返回：实际成功写入条数
	'''
	try:
		from faker import Faker
	except ImportError:
		raise ImportError('populate_fake_data need faker package: pip install faker')
	import random
	rng = random.Random(seed)
	fake = Faker(locale)
	if seed is not None:
		fake.seed_instance(seed)

	is_local = isinstance(db, AccountLocal)
	is_mysql = isinstance(db, AccountMySQL)
	is_mongo = isinstance(db, AccountMongo)
	if not (is_local or is_mysql or is_mongo):
		raise TypeError('unsupported backend: %s' % type(db).__name__)

	now = base_time if base_time is not None else datetime.datetime.now()
	ten_years = (365 * 10 + 2) * 86400.0	# 最近十年的秒数（含闰日）

	# 按权重随机挑一个下标
	def _pick (weights):
		r = rng.random() * sum(weights)
		total = 0
		for i, w in enumerate(weights):
			total += w
			if r < total:
				return i
		return len(weights) - 1

	# 金额分档（单位：元，写入前用 _cents 换算成整数分）
	def _money ():
		r = rng.random()
		if r < 0.85:
			return round(rng.uniform(1, 1000), 2)
		if r < 0.97:
			return round(rng.uniform(1000, 10000), 2)
		return round(rng.uniform(10000, 50000), 2)

	# 元 -> 整数分：金额列是 BIGINT 整数分，应用层 /100 还原成元
	def _cents (yuan):
		return int(round(yuan * 100))

	# 升到 level 所需累计经验（exp 由此推导，保证 level/exp 自洽）
	def _exp_base (level):
		return 10 * level * level

	# 注册时年龄：16-17/18-25/26-35/36-50/51-64 按权重，主力 18-35
	def _reg_age ():
		i = _pick((5, 35, 35, 20, 5))
		return rng.randint((16, 18, 26, 36, 51)[i], (17, 25, 35, 50, 64)[i])

	# 注册小时权重（0-23 点）：凌晨低谷，20-21 点高峰
	HOUR_WEIGHTS = (1, 1, 1, 1, 1, 2, 2, 3, 4, 5, 5, 5, 6, 6, 5, 5, 5, 5,
		7, 8, 9, 9, 8, 5)

	# 截断超长字符串。str/unicode 不调 str()：py2 下 str(unicode 中文)
	# 会抛 UnicodeEncodeError
	def _clip (s, n):
		if s is None:
			return None
		if not isinstance(s, (str, unicode)):
			s = str(s)
		return s if len(s) <= n else s[:n]

	# 公网 IPv4：Faker 的 ipv4() 会产出私网/保留段，过滤掉
	def _public_ipv4 ():
		for _ in range(32):
			ip = fake.ipv4()
			try:
				a, b = [int(x) for x in ip.split('.')[:2]]
			except ValueError:
				continue
			if a in (0, 10, 127) or a >= 224:
				continue
			if a == 100 and 64 <= b <= 127:
				continue
			if a == 169 and b == 254:
				continue
			if a == 172 and 16 <= b <= 31:
				continue
			if a == 192 and b == 168:
				continue
			return ip
		return '203.0.113.%d' % rng.randint(2, 254)	# 兜底：文档保留段

	# 登录 ip：公网 IPv4 为主，约 8% IPv6（ip 列宽 70 就是给 IPv6 留的）
	def _ip ():
		if rng.random() < 0.08:
			return fake.ipv6()
		return _public_ipv4()

	# 常见邮箱域名（zh_CN 场景）
	DOMAINS = ('qq.com', '163.com', '126.com', 'gmail.com', 'sina.com',
		'sohu.com', 'foxmail.com', '139.com', 'outlook.com', 'hotmail.com')

	# urs：QQ 号 / 拼音昵称(+数字) 风格混合，贴近真实注册账号形态
	def _gen_urs ():
		r = rng.random()
		if r < 0.35:
			return '%d@qq.com' % rng.randint(10000000, 3499999999)
		name = fake.user_name()
		if r < 0.75:
			name = '%s%d' % (name, rng.randint(1, 9999))
		return '%s@%s' % (_clip(name, 60), rng.choice(DOMAINS))

	# 注册渠道：加权（android 为主），cid 与渠道关联
	SRCS = (('android', 40), ('ios', 25), ('web', 20), ('invite', 8), ('wap', 7))

	def _gen_src ():
		i = _pick([w for _, w in SRCS])
		return (SRCS[i][0], i)

	# 一次底层 UPDATE 写入全部剩余字段（资料/金额/时间/ip），省掉 update()/
	# deposit() 的多次往返；批量生成对网络延迟敏感，register 已走 API 建号。
	# fields 的键都是固定列名（非用户输入），值一律用参数绑定，无注入风险。
	def _set_fields (uid, fields):
		if is_mongo:
			db._AccountMongo__int64_fix(fields)	# cid 以 BSON Int64 存储
			db._AccountMongo__account.update_one({'uid': uid}, {'$set': fields})
			return
		keys = list(fields.keys())
		if is_local:
			sql = 'UPDATE account SET ' + ', '.join(['%s = ?' % k for k in keys])
			sql += ' WHERE uid = ?;'
			conn = db._AccountLocal__conn
			conn.execute(sql, tuple(fields.values()) + (uid,))
			conn.commit()
		else:
			sql = 'UPDATE account SET ' + ', '.join(['%s = %%s' % k for k in keys])
			sql += ' WHERE uid = %s;'
			conn = db._AccountMySQL__conn
			c = conn.cursor()
			c.execute(sql, tuple(fields.values()) + (uid,))
			conn.commit()
			c.close()

	succeed = 0
	attempts = 0
	seen = set()
	max_attempts = count * 3 + 100	# urs 生成/撞库重试上限
	report = max(1, count // 20)
	while succeed < count and attempts < max_attempts:
		attempts += 1
		urs = _gen_urs()
		if urs in seen:
			continue
		seen.add(urs)
		# gender 按权重（0=未知/1=男/2=女），名字与性别对应；locale 没有
		# 分性别接口时退回 fake.name()
		gender = _pick((10, 48, 42))
		if gender == 1 and hasattr(fake, 'name_male'):
			name = fake.name_male()
		elif gender == 2 and hasattr(fake, 'name_female'):
			name = fake.name_female()
		else:
			name = fake.name()
		src, srci = _gen_src()
		rec = db.register(urs, fake.password(length = 12),
			_clip(name, 32), gender, src)
		if not rec:
			continue	# urs 与库内已有数据撞库，换一个重试
		uid = rec['uid']
		# 注册时间：日期在最近十年内均匀，小时按权重重采样；若抽到今天且
		# 小时在未来，则退回最近 24 小时内随机
		reg_dt = now - datetime.timedelta(seconds = rng.uniform(0, ten_years))
		reg_dt = reg_dt.replace(microsecond = 0, hour = 0, minute = 0, second = 0)
		reg_dt += datetime.timedelta(hours = _pick(HOUR_WEIGHTS),
			minutes = rng.randint(0, 59), seconds = rng.randint(0, 59))
		if reg_dt > now:
			reg_dt = now - datetime.timedelta(seconds = rng.uniform(0, 86400))
			reg_dt = reg_dt.replace(microsecond = 0)
		span = max(1.0, (now - reg_dt).total_seconds())
		# 登录统计：约 8% 注册后从未登录；其余登录次数长尾分布并按账号年龄
		# 封顶（日均不超过 3 次）；最后登录 60% 偏向近期、40% 生命周期内均匀
		never = rng.random() < 0.08
		if never:
			times, last_dt = 0, None
		else:
			cap = min(3000, max(1, int(span / 86400)) * 3 + 1)
			times = min(cap, 1 + int(rng.expovariate(1.0 / 100)))
			if rng.random() < 0.4:
				back = span * rng.random()		# 流失用户：生命周期内随机
			else:
				back = span * rng.random() ** 3	# 活跃用户：偏向近期
			last_dt = now - datetime.timedelta(seconds = back)
			last_dt = last_dt.replace(microsecond = 0)
		# 生日：由注册时间反推（保证注册时年满 16 岁），约 15% 未填写
		birth = None
		if rng.random() >= 0.15:
			days = _reg_age() * 365.25 + rng.uniform(0, 365)
			birth = (reg_dt - datetime.timedelta(days = days)).date()
		# 等级指数衰减（低等级为主），exp 由 level 推导，两者自洽
		level = min(120, int(rng.expovariate(1.0 / 12)))
		exp = _exp_base(level) + rng.randint(0,
			max(1, _exp_base(level + 1) - _exp_base(level) - 1))
		# 金额：约 15% 有 credit（其中约 30% 再给 gold），大多带关联消费史；
		# 另有约 5% 余额为 0 但消费史非 0（充的钱花完了）
		credit = gold = credit_spent = gold_spent = 0.0
		r = rng.random()
		if r < 0.15:
			credit = _money()
			if rng.random() < 0.7:
				credit_spent = round(credit * rng.uniform(0.2, 3.0), 2)
			if rng.random() < 0.30:
				gold = _money()
				if rng.random() < 0.7:
					gold_spent = round(gold * rng.uniform(0.2, 3.0), 2)
		elif r < 0.20:
			credit_spent = _money()
		# vip 与消费关联：有余额或消费史的用户一半是 vip，其余仅 2%；
		# score 与 level 关联
		spender = (credit + gold + credit_spent + gold_spent) > 0
		misc = {'tag': fake.word(),
			'vip': rng.random() < (0.5 if spender else 0.02),
			'score': min(1000, level * 8 + rng.randint(0, 120))}
		# mail：10% 未填；填了的 40% 直接用 urs（真实场景常见）
		if rng.random() < 0.10:
			mail = None
		elif rng.random() < 0.40:
			mail = urs
		else:
			mail = _clip(fake.email(), 88)
		mobile = None if rng.random() < 0.20 else _clip(fake.phone_number(), 32)
		sign = None if rng.random() < 0.50 else _clip(fake.sentence(nb_words = 4), 32)
		# photo：站内相对路径（外部占位图 URL 太假），40% 未上传头像
		photo = None if rng.random() < 0.40 else \
			'/avatar/%04d/%08d_%d.jpg' % (uid % 10000, uid, rng.randint(1, 3))
		# intro：60% 未填，其余多为短句、少数长文
		if rng.random() < 0.60:
			intro = None
		elif rng.random() < 0.70:
			intro = _clip(fake.sentence(nb_words = rng.randint(3, 10)), 256)
		else:
			intro = _clip(fake.text(max_nb_chars = rng.randint(60, 200)), 256)
		# 约 1.5% 封禁账号，让 login/payment/deposit 的封禁分支可测
		status = 1 if rng.random() < 0.015 else 0
		cid = rng.randint(100000000, 999999999) if rng.random() < 0.25 else 0	# 外部 uid，0=未绑定
		# 日期/misc 按后端准备取值：sqlite 全用 str；mysql 日期用原生对象、misc
		# 用 json 文本；mongo 日期用 datetime、misc 用 dict（存 BSON 文档）；
		# 未填写的字段保持 None（存为 NULL）
		if is_mongo:
			reg_v, last_v = reg_dt, last_dt
			birth_v = datetime.datetime(birth.year, birth.month, birth.day) \
				if birth is not None else None
			misc_v = misc
		else:
			misc_v = db._misc_dump(misc)
			birth_v = birth.strftime('%Y-%m-%d') if birth is not None else None
			if is_local:
				reg_v = reg_dt.strftime('%Y-%m-%d %H:%M:%S')
				last_v = last_dt.strftime('%Y-%m-%d %H:%M:%S') \
					if last_dt is not None else None
			else:
				reg_v, last_v = reg_dt, last_dt
		_set_fields(uid, {
			'cid': cid, 'icon': rng.randint(0, 64),
			'level': level, 'exp': exp,
			'birthday': birth_v, 'mail': mail, 'mobile': mobile,
			'sign': sign, 'photo': photo, 'intro': intro,
			'misc': misc_v, 'status': status,
			'credit': _cents(credit), 'gold': _cents(gold),
			'CreditConsumed': _cents(credit_spent),
			'GoldConsumed': _cents(gold_spent),
			'RegDate': reg_v, 'LastLoginDate': last_v,
			'LoginTimes': times, 'ip': None if never else _ip(),
		})
		succeed += 1
		if verbose and succeed % report == 0:
			print('  populate_fake_data: %d/%d' % (succeed, count))
	return succeed


#----------------------------------------------------------------------
# testing
#----------------------------------------------------------------------
if __name__ == '__main__':
	my = {'host':'xnode3.ddns.net', 'user':'skywind', 'passwd':'678900', 'db':'skywind_t9'}
	def test1():
		if os.path.exists('accountz.db'):
			os.remove('accountz.db')
		db = AccountLocal('accountz.db')
		print(db.register('skywind@tuohn.com', '1234', 'linwei', 1, 'xx'))
		print(db.population(100))
		print(db.login('skywind@tuohn.com', '1234'))
		print(db.login('skywind@tuohn.com', '1'))
		print(db.login('skywind@tuohn.com', None))
		print(db.login('skywind@tuohn.com', None, force = True))
		uid = db.query(urs = 'skywind@tuohn.com')['uid']
		print('uid=%d'%uid)
		db.update(uid, {'level':100})
		print(db.update(uid, {'pass':'hacked'}))
		print(db.query(urs = 'skywind@tuohn.com'))
		db.deposit(uid, 'credit', 30)
		print(db.payment(uid, 'credit', 100))
		print(db.payment(uid, 'credit', -5))
		print(db.payment(uid, 'credit', 0))
		print(db.count())
		print(len(db.list_users(0, 3)))
		db.ban(uid)
		print(db.login('skywind@tuohn.com', '1234'))
		print(db.payment(uid, 'credit', 1))
		db.unban(uid)
		print(db.login('skywind@tuohn.com', '1234'))
		print('')
		db.passwd(uid, None, '5678')
		print(db.passwd(uid, '1234', None))
		print(db.passwd(uid, '5678', None))
		print(db.passwd(uid, '5678', 'abcd'))
		print(db.passwd(uid, 'abcd', None))
		print(db.passwd(uid, None, '1234'))
		print(db.delete(uid))
		print(db.query(urs = 'skywind@tuohn.com'))
		db.close()
		return 0
	def test2():
		t = time.time()
		db = AccountMySQL(init = True, **my)
		print(time.time() - t)
		print(db.register('skywind@tuohn.com', '1234', 'linwei', 1, 'xx'))
		print(db.register('skywind@tuohn.com', '1234', 'linwei', 1, 'xx'))
		# print(db.population(100))
		print(db.query(urs = 'skywind@tuohn.com'))
		print('')
		uid = db.query(urs = 'skywind@tuohn.com')['uid']
		print('uid=%d'%uid)
		# print(db.query(uid = uid))
		db.update(uid, {'level':100, 'misc':None})
		print(db.login('skywind@tuohn.com', '1234'))
		print(db.login('skywind@tuohn.com', '1'))
		db.deposit(uid, 'credit', 40)
		print(db.payment(uid, 'credit', 100))
		print('')
		db.passwd(uid, None, '5678')
		print(db.passwd(uid, '1234', None))
		print(db.passwd(uid, '5678', None))
		print(db.passwd(uid, '5678', 'abcd'))
		print(db.passwd(uid, 'abcd', None))
		print(db.passwd(uid, None, '1234'))
		return 0
	def test3():
		url = 'mongodb://xnode3.ddns.net/skywind'
		t = time.time()
		db = AccountMongo(url, True)
		print(time.time() - t)
		print(db.register('skywind@tuohn.com', '1234', 'linwei', 1, 'xx'))
		print(db.register('skywind@tuohn.com', '1234', 'linwei', 1, 'xx'))
		print(db.login('skywind@tuohn.com', '1234'))
		print(db.login('skywind@tuohn.com', '1'))
		print('')
		uid = db.query(urs = 'skywind@tuohn.com')['uid']
		print('uid=%d'%uid)
		db.update(uid, {'level':100, 'misc':'haha'})
		print(db.query(urs = 'skywind@tuohn.com'))
		print('')
		print('---------- money --------')
		db.deposit(uid, 'credit', 40)
		print(db.payment(uid, 'credit', 100))
		print('^^^^^^^^^^^^^^^^^^^^^^^^^')
		print('')
		# db.passwd(uid, None, '5678')
		# print(db.passwd(uid, '1234', None))
		# print(db.passwd(uid, '5678', None))
		# print(db.passwd(uid, '5678', 'abcd'))
		# print(db.passwd(uid, 'abcd', None))
		# print(db.passwd(uid, None, '1234'))
		# print('population: %d'%db.population())
		return 0
	test1()
