import gc
import sys
import weakref
from contextlib import contextmanager

from twisted.internet.defer import Deferred, returnValue, fail, succeed, CancelledError

from twisted_coroutine import noreturn, coroutine
# from unnamedframework.util.testing import assert_raises, deferred_result, assert_not_raises


def test_pause_unpause():
    after_yield_reached = [False]
    ctrl_d = Deferred()

    @coroutine
    def fn():
        yield ctrl_d
        after_yield_reached[0] = True

    d = fn()
    assert not after_yield_reached[0]

    d.pause()
    ctrl_d.callback(None)
    assert not after_yield_reached[0]

    d.unpause()
    assert after_yield_reached[0]


def test_cancel():
    after_yield_reached = [False]
    ctrl_d = Deferred()

    @coroutine
    def fn():
        yield ctrl_d
        after_yield_reached[0] = True

    d = fn()
    assert not after_yield_reached[0]

    d.addErrback(lambda f: f.trap(CancelledError))
    d.cancel()
    ctrl_d.callback(None)
    assert not after_yield_reached[0]


def test_cancel_stops_the_generator():
    generator_exit_caught = [False]
    ctrl_d = Deferred()

    @coroutine
    def fn():
        try:
            yield ctrl_d
        except GeneratorExit:
            generator_exit_caught[0] = True

    d = fn()
    d.addErrback(lambda f: f.trap(CancelledError))
    d.cancel()
    assert generator_exit_caught[0]


def test_main():
    d_ctrl_1, d_ctrl_2 = Deferred(), Deferred()

    wref = [None]
    never_called = [True]

    @coroutine
    def test_coroutine():
        dummy = Dummy()
        wref[0] = weakref.ref(dummy)

        yield d_ctrl_1  # pause for state inspection

        noreturn(other_coroutine())
        never_called[0] = False

    other_coroutine_called = [False]

    def other_coroutine():
        other_coroutine_called[0] = True
        yield d_ctrl_2  # pause for state inspection

    final_d = test_coroutine()

    gc.collect()  # don't rely on automatic collection
    assert wref[0]()  # just to reinforce the test logic

    d_ctrl_1.callback(None)  # resume test_coroutine
    assert other_coroutine_called[0], "the other coroutine should be executed"
    gc.collect()  # don't rely on automatic collection
    assert not wref[0](), "objects in the caller should become garbage"
    assert not final_d.called

    d_ctrl_2.callback(None)  # resume other_coroutine
    assert final_d.called, "the whole procedure should have been completed"
    assert never_called[0], "flow should never return to the noreturn-calling coroutine"


def test_deep_recursion():
    def fact(n, result=1):
        if n <= 1:
            returnValue(result)
        else:
            noreturn(fact(n - 1, n * result))
        yield

    assert deferred_result(coroutine(fact)(1)) == 1
    assert deferred_result(coroutine(fact)(10)) == safe_fact(10)

    with recursion_limit(100):
        try:
            # +10 is actually too high here as we probably already have some stuff on the stack, but just to be sure
            assert deferred_result(coroutine(fact)(110)) == safe_fact(110)
        except RuntimeError:
            assert False

    # ...and now let's prove that the same (tail call optimizable) algorithm without noreturn will eat up the stack

    def normal_fact(n, result=1):
        if n <= 1:
            returnValue(result)
        else:
            return normal_fact(n - 1, n * result)

    with recursion_limit(100):
        try:
            normal_fact(110)
        except RuntimeError:
            pass
        else:
            assert False, "normal_fact(110)"


def test_with_previous_yield_result_not_none():
    class MockException(Exception):
        pass

    fn_called = [False]

    @coroutine
    def fn():
        fn_called[0] = True
        try:
            yield fail(MockException())
        except MockException:
            pass

        noreturn(fn2())

    def fn2():
        yield succeed(None)

    try:
        fn()
    except MockException:
        assert False
    assert fn_called[0]


def test_noreturn_of_other_inlineCallbacks_wrapped_callable():
    after_noreturn_reached = [False]

    @coroutine
    def fn():
        yield
        noreturn(fn2())
        after_noreturn_reached[0] = True

    fn2_called = [False]

    @coroutine
    def fn2():
        fn2_called[0] = True
        yield
        returnValue('someretval')

    retval = deferred_result(fn())
    assert fn2_called[0]
    assert not after_noreturn_reached[0]
    assert retval == 'someretval'


def test_noreturn_with_regular_function():
    after_noreturn_reached = [False]

    @coroutine
    def fn():
        yield
        noreturn(fn2())
        after_noreturn_reached[0] = True

    def fn2():
        return 'someretval'

    retval = deferred_result(fn())
    assert not after_noreturn_reached[0]
    assert retval == 'someretval'


@contextmanager
def recursion_limit(n):
    old = sys.getrecursionlimit()
    sys.setrecursionlimit(n)
    try:
        yield
    finally:
        sys.setrecursionlimit(old)


# because object() cannot be weakly referenced
class Dummy:
    pass


def safe_fact(n):
    return reduce(lambda a, b: a * b, xrange(1, n + 1))


def deferred_result(d):
    ret = [None]
    exc = [None]
    if isinstance(d, Deferred):
        assert d.called
        d.addCallback(lambda result: ret.__setitem__(0, result))
        d.addErrback(lambda f: exc.__setitem__(0, f))
        if exc[0]:
            exc[0].raiseException()
        return ret[0]
    else:
        return d
