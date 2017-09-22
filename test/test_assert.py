# coding: utf-8

test = 0
data = "assertion error"

try:
    # assert True, data
    assert False, data  # 第一引数がFalseなら例外を発生させる
except AssertionError:
    print data
finally:
    print "the end"
