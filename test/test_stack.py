# coding: utf-8

import sys
import traceback


def sumework():
    try:
        print a
    except Exception:
        print "error"
        traceback.print_exc(file=sys.stdout)
    finally:
        print "the end"


def sumework2():
    try:
        print a
    except Exception:
        print "error"
        exc_type, exc_value, exc_traceback = sys.exc_info()
        print traceback.extract_tb(exc_traceback)
        print traceback.extract_stack()

        print traceback.format_tb(exc_traceback)
        print traceback.format_stack()
        print "the end"

if __name__ == '__main__':
    # sumework()
    sumework2()
