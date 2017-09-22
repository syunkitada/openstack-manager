# coding: utf-8

import unittest


class BankAccountTest(unittest.TestCase):

    def _getTarget(self):
        from nose_target import BankAccount
        return BankAccount

    def _makeOne(self, *args, **kwargs):
        return self._getTarget()(*args, **kwargs)

    def test_construct(self):
        target = self._makeOne()
        self.assertEqual(target._balance, 0)

    def test_deposit(self):
        target = self._makeOne()
        target.deposit(100)
        self.assertEqual(target._balance, 100)

    def test_withdraw(self):
        target = self._makeOne()
        target._balance = 100
        target.withdraw(20)
        self.assertEqual(target._balance, 80)

    def test_get_balance(self):
        target = self._makeOne()
        from nose_target import NotEnoughFoundsException
        try:
            target.set_balance(-1)
            self.fail()
        except NotEnoughFoundsException:
            pass
