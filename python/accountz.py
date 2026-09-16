#! /usr/bin/env python
# -*- coding: utf-8 -*-
#  vim: set ts=4 sw=4 tw=0 noet :
#======================================================================
#
# accountz.py - 账号存储：sqlite / mysql / mongo 三个后端
#
# Created by skywind on 2017/03/16
# Last change: 2026/09/16 16:25:00
#
# 设计说明：
# 
# 1. 密码按传入值原样存储，哈希/加盐由外层决定，本模块不介入算法
# 2. payment/deposit 的 money 必须是大于 0 的有限数字，按 2 位小数处理
# 3. status: 0=正常, 1=封禁（封禁后禁止登录/支付/充值）
# 4. mode: 0/登录时更新统计(LastLoginDate/LoginTimes/ip)，非 0 只验证
# 5. 三个后端行为对齐：字段表、错误码、大小写敏感比较、应用侧时间
# 6. update() 不能修改密码（白名单不含 pass），改密码请用 passwd()
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
pymongo = None


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

	# 检查金额参数，无错误返回 None，有错误返回 (-1, 0, 原因) 元组
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
		if money <= 0:
			return (-1, 0, 'money must be positive: %s' % (money,))
		return None

	# 识别账号标识：int -> ('uid', 值)，str -> ('urs', 值)，无效 -> None
	# 注意 bool 是 int 的子类，True 会被当作 uid=1，这里显式拒绝
	def _identify (self, uid):
		if isinstance(uid, bool):
			return None
		if isinstance(uid, (int, long)):
			return ('uid', uid)
		if isinstance(uid, (str, unicode)):
			return ('urs', uid)
		return None

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
		    "cid" INTEGER DEFAULT (0),
		    "name" VARCHAR(32) NOT NULL DEFAULT(''),			
		    "pass" VARCHAR(64) NOT NULL DEFAULT(''),
			"status" INTEGER DEFAULT (0),
		    "gender" INTEGER DEFAULT (0),
			"credit" REAL DEFAULT (0),
		    "gold" REAL DEFAULT (0),
		    "level" INTEGER DEFAULT (0),
			"exp" INTEGER DEFAULT (0),
			"birthday" DATE,
		    "icon" INTEGER DEFAULT (0),
		    "mail" VARCHAR(88),
		    "mobile" VARCHAR(32), 
			"sign" VARCHAR(32),
			"photo" VARCHAR(256),
			"intro" VARCHAR(256),
			"misc" TEXT,
			"src" VARCHAR(16),
			"ip" VARCHAR(70),
		    "RegDate" DATETIME,
		    "LastLoginDate" DATETIME,
			"LoginTimes" INTEGER DEFAULT (0),
			"CreditConsumed" REAL DEFAULT (0),
			"GoldConsumed" REAL DEFAULT (0)
		);
		CREATE INDEX IF NOT EXISTS "account_3" ON account (cid);
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

	# 支付钱，kind为 'credit'或 'gold'，money是需要支付的钱数（必须大于0）
	# 返回 (结果, 还有多少钱, 错误原因)
	# 结果=0支付成功，1用户不存在，2钱不够，3未知错误，4账户封禁，-1参数错误
	def payment (self, uid, kind, money):
		error = self._money_error(kind, money)
		if error is not None:
			return error
		kind = kind.lower()
		money = round(money, 2)
		if isinstance(uid, bool) or not isinstance(uid, (int, long)):
			return (-1, 0, 'uid must be int: %s' % (repr(uid),))
		if kind == 'credit':
			x1, x2 = 'credit', 'CreditConsumed'
		else:
			x1, x2 = 'gold', 'GoldConsumed'
		sql = ('UPDATE account SET %s = round(%s - ?, 2), %s = round(%s + ?, 2) '
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

	# 存钱，kind为 'credit'或 'gold'，money是需要增加的钱数（必须大于0）
	def deposit (self, uid, kind, money):
		error = self._money_error(kind, money)
		if error is not None:
			return error
		kind = kind.lower()
		money = round(money, 2)
		if isinstance(uid, bool) or not isinstance(uid, (int, long)):
			return (-1, 0, 'uid must be int: %s' % (repr(uid),))
		sql = ('UPDATE account SET %s = round(%s + ?, 2) '
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
	global MySQLdb
	if MySQLdb is not None:
		return True
	try:
		import MySQLdb as _mysql
		MySQLdb = _mysql
	except ImportError:
		# 没装 mysqlclient 时退回 PyMySQL 的 MySQLdb 兼容层
		try:
			import pymysql
			pymysql.install_as_MySQLdb()
			import MySQLdb as _mysql
			MySQLdb = _mysql
		except ImportError:
			return False
	return True


#----------------------------------------------------------------------
# AccountMySQL
#----------------------------------------------------------------------
class AccountMySQL (AccountBase):

	def __init__ (self, **argv):
		AccountBase.__init__(self)
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
			self.__conn = MySQLdb.connect(**uri)
			return self.init()
		uri = dict(uri)
		uri['db'] = self.__db
		self.__conn = MySQLdb.connect(**uri)
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
		self.__conn = MySQLdb.connect(**uri)
		return True

	# 建表语句，urs/pass 用 utf8_bin（与 sqlite 的大小写敏感对齐），
	# 金额用 DECIMAL 精确存储
	def __table_sql (self, database):
		sql = '''
			CREATE TABLE IF NOT EXISTS `%s`.`account` (
		    `uid` INT PRIMARY KEY NOT NULL AUTO_INCREMENT,
		    `urs` VARCHAR(88) CHARACTER SET utf8 COLLATE utf8_bin NOT NULL UNIQUE KEY,
		    `cid` INT DEFAULT 0,
		    `name` VARCHAR(32) NOT NULL DEFAULT '',			
		    `pass` VARCHAR(64) CHARACTER SET utf8 COLLATE utf8_bin NOT NULL DEFAULT '',
			`status` INT DEFAULT 0,
		    `gender` SMALLINT DEFAULT 0,
			`credit` DECIMAL(16,2) DEFAULT 0,
		    `gold` DECIMAL(16,2) DEFAULT 0,
		    `level` INT DEFAULT 0,
			`exp` INT DEFAULT 0,
			`birthday` DATE,
		    `icon` INT DEFAULT 0,
		    `mail` VARCHAR(88),
		    `mobile` VARCHAR(32), 
			`sign` VARCHAR(32),			
			`photo` VARCHAR(256),
			`intro` VARCHAR(256),
			`misc` TEXT,
			`src` VARCHAR(16),
			`ip` VARCHAR(70),
		    `RegDate` DATETIME,
		    `LastLoginDate` DATETIME,
			`LoginTimes` INT DEFAULT 0,
			`CreditConsumed` DECIMAL(16,2) DEFAULT 0,
			`GoldConsumed` DECIMAL(16,2) DEFAULT 0,
			KEY(`cid`),
			KEY(`name`),
			KEY(`src`)
			)
		'''
		sql = '\n'.join([ n.strip('\t') for n in sql.split('\n') ])
		sql = sql.strip('\n')
		sql += ' ENGINE=InnoDB DEFAULT CHARSET=utf8;'
		return sql % database

	# DECIMAL 读出来是 Decimal 类型，这里转成 float，与其他后端类型一致
	def _record2obj (self, record):
		user = AccountBase._record2obj(self, record)
		if user is not None:
			for k in self.MONEY_FIELDS:
				if isinstance(user.get(k), decimal.Decimal):
					user[k] = float(user[k])
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

	# 支付钱，kind为 'credit'或 'gold'，money是需要支付的钱数（必须大于0）
	# 返回 (结果, 还有多少钱, 错误原因)
	# 结果=0支付成功，1用户不存在，2钱不够，3未知错误，4账户封禁，-1参数错误
	def payment (self, uid, kind, money):
		error = self._money_error(kind, money)
		if error is not None:
			return error
		kind = kind.lower()
		money = round(money, 2)
		if isinstance(uid, bool) or not isinstance(uid, (int, long)):
			return (-1, 0, 'uid must be int: %s' % (repr(uid),))
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

	# 存钱，kind为 'credit'或 'gold'，money是需要增加的钱数（必须大于0）
	def deposit (self, uid, kind, money):
		error = self._money_error(kind, money)
		if error is not None:
			return error
		kind = kind.lower()
		money = round(money, 2)
		if isinstance(uid, bool) or not isinstance(uid, (int, long)):
			return (-1, 0, 'uid must be int: %s' % (repr(uid),))
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


#----------------------------------------------------------------------
# initialize mongodb client
#----------------------------------------------------------------------
def pymongo_init():
	global pymongo
	if pymongo is not None:
		return True
	try:
		import pymongo as _pymongo
		pymongo = _pymongo
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
		if init:
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

	# 初始化索引
	def init (self):
		account = self.__account
		account.create_index([('uid', 1)], unique = True)
		account.create_index([('urs', 1)], unique = True)
		account.create_index([('name', 1)])
		return True

	# 字段补充
	def __obj_complete (self, obj):
		newobj = {}
		for k in self._names:
			if k != 'pass':
				newobj[k] = obj.get(k, None)
		if '_id' in obj:
			newobj['_id'] = obj['_id']
		if newobj['uid'] is None:
			newobj['uid'] = 0
		if newobj['status'] is None:
			newobj['status'] = 0
		return newobj

	# 自增量
	def __id_auto_increment (self, name):
		seqs = self.__seqs
		cc = seqs.find_one_and_update(
			{'_id': name},
			{'$inc': {'next': 1}},
			{'next': True},
			return_document = pymongo.ReturnDocument.AFTER,
			upsert = True)
		return cc.get('next', 1)

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
		cc['credit'] = 0.0
		cc['gold'] = 0.0
		cc['level'] = 0
		cc['exp'] = 0
		cc['CreditConsumed'] = 0.0
		cc['GoldConsumed'] = 0.0
		cc['status'] = 0
		cc['RegDate'] = datetime.datetime.now()
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
				setting[name] = changes[name]
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

	# 支付钱，kind为 'credit'或 'gold'，money是需要支付的钱数（必须大于0）
	# 返回 (结果, 还有多少钱, 错误原因)
	# 结果=0支付成功，1用户不存在，2钱不够，3未知错误，4账户封禁，-1参数错误
	def payment (self, uid, kind, money):
		error = self._money_error(kind, money)
		if error is not None:
			return error
		kind = kind.lower()
		money = round(money, 2)
		if isinstance(uid, bool) or not isinstance(uid, (int, long)):
			return (-1, 0, 'uid must be int: %s' % (repr(uid),))
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

	# 存钱，kind为 'credit'或 'gold'，money是需要增加的钱数（必须大于0）
	def deposit (self, uid, kind, money):
		error = self._money_error(kind, money)
		if error is not None:
			return error
		kind = kind.lower()
		money = round(money, 2)
		if isinstance(uid, bool) or not isinstance(uid, (int, long)):
			return (-1, 0, 'uid must be int: %s' % (repr(uid),))
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
