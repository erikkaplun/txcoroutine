Coroutine flow control
======================

Description
-----------

Generators wrapped with ``@txcoroutine.coroutine`` are otherwise identical to those wrapped with
``@twisted.internet.defer.inlineCallbacks``, however, the object returned by it is an instance of
``txcoroutine.Coroutine`` which is a subclass of ``twisted.internet.defer.Deferred``.

``Coroutine`` objects provide an API otherwise identical to that of ``Deferred`` objects, however, calling ``pause``,
``unpause`` or ``cancel`` on ``Coroutine`` objects transparently applies the same action on all nested ``Deferred``
objects that are currently waited on recursively.

Simple example
--------------

Single coroutine that calls a ``Deferred``-returning function. The ``Deferred`` is automatically cancelled when the
coroutine is stopped.

::

    from __future__ import print_function

    from twisted.internet import reactor
    from twisted.internet.defer import Deferred

    def get_message():
        d = Deferred(canceller=lambda _: (
            print("cancelled getting a message"),
            heavylifting.cancel(),
        ))
        print("getting a message...")
        heavylifting = reactor.callLater(1.0, d.callback, 'dummy-message')
        return d

    @coroutine
    def some_process():
        try:
            while True:
                msg = yield get_message()
                print("processing message: %s" % (msg,))
        finally:  # could use `except GeneratorExit` but `finally` is more illustrative
            print("coroutine stopped, cleaning up")

    def main():
        proc = some_process()
        reactor.callLater(3, proc.cancel)  # stop the coroutine 3 seconds later.

    reactor.callWhenRunning(main)
    reactor.run()

**Output:**

::

    getting a message...
    processing message: dummy-message
    getting a message...
    processing message: dummy-message
    ...
    cancelled getting a message
    coroutine stopped, cleaning up


Advanced example with multiple levels of coroutines and cascaded flow control
-----------------------------------------------------------------------------

::

    from __future__ import print_function

    from twisted.internet import reactor, task
    from twisted.internet.defer import Deferred

    @coroutine
    def level3_process():
        basetime = reactor.seconds()
        seconds_passed = lambda: int(round(reactor.seconds() - basetime))
        try:
            while True:
                print("iterating: %ss passed" % seconds_passed())
                yield sleep(1.0)
        finally:  # could use `except GeneratorExit` but `finally` is more illustrative
            print("level3_process stopped; cleaning up...")

    @coroutine
    def level2_process():
        try:
            yield level3_process()
        finally:
            print("level2_process stopped; cleaning up...")

    @coroutine
    def root_process():
        try:
            yield level2_process()
        finally:
            print("root_process stopped; cleaning up...")

    def main():
        proc = root_process()
        reactor.callLater(3, proc.pause)  # pause the coroutine 3 seconds later.
        reactor.callLater(6, proc.unpause)  # then pause 3 seconds later
        reactor.callLater(9, proc.cancel)  # then finally stop it 3 seconds later


    def sleep(seconds, reactor=reactor):
        """A simple helper for asynchronously sleeping a certain amount of time."""
        return task.deferLater(reactor, seconds, lambda: None)


    reactor.callWhenRunning(main)
    reactor.run()

**Output:**

::

    iterating: 0s passed
    iterating: 1s passed
    iterating: 2s passed
    <<NOTHING PRINTED FOR 4 SECONDS>>
    iterating: 6s passed
    iterating: 7s passed
    iterating: 8s passed
    level3_process stopped; cleaning up...
    level2_process stopped; cleaning up...
    root_process stopped; cleaning up...


Tail call optimisation
======================

**Example:**

::

    def fact(n, result=1):
        if n <= 1:
            returnValue(result)
        else:
            noreturn(fact(n - 1, n * result))
        yield  # make sure it's a generator

    n = coroutine(fact)(10000).result

Note, ``fact`` itself should not be decorated with ``coroutine``, otherwise the recursive call would simply create
another coroutine. This would still support infinite recursion but would be less efficient and consume slightly more
memory per each new level introduced because, internally, all the Deferreds would be alive and chained to each other.

This is mainly meant for recursively and infinitely swapping out behaviour in long running processes. For
non-coroutine/non-generator TCO, a simpler approach is also possible by delegating the function invocation directly
to the trampoline. However, this would be out of the scope of this package.

Description of operation
------------------------

The memory held by the caller is immediately released as it swaps itself out for another process, while the ``Deferred``
that was originally returned is still bound to the ongoing processing.

::

    @coroutine
    def process():
        big_obj = SomeBigObject()
        noreturn(process_state1())  # big_obj is released immediately
        yield

    def process_state1():
        another_big_obj = SomeBigObject()
        noreturn(process_state2())  # another_big_obj is released immediately
        yield

    def process_state2():
        yield do_something()
        returnValue(123)

    def some_other_coroutine():
        yield process()  # will block until state2 has returned 123

This cannot be achieved with plain ``@inlineCallbacks`` while satisfying both requirements.

Memory-efficient solution with ``@inlineCallbacks``:

::

    @inlineCallbacks
    def process():
         big_obj = SomeBigObject()
         process_state1()  # big_obj is released immediately but the `Deferred` returned by process is fired immediately
         yield

Solution with ``@inlineCallbacks`` keeping ``Deferred`` consistency but not releasing memory:

::

    @inlineCallbacks
    def process():
         big_obj = SomeBigObject()
         yield process_state1()  # big_obj is not released until process_state1 completes


Miscellaneous
-------------

See also http://racecondev.wordpress.com/2012/08/17/a-coroutine-decorator-for-twisted/
The blog post doesn't mention tail-call optimisation though.
