"""
    jupylet/clock.py
    
    Copyright (c) 2020, Nir Aides - nir@winpdb.org

    Redistribution and use in source and binary forms, with or without
    modification, are permitted provided that the following conditions are met:

    1. Redistributions of source code must retain the above copyright notice, this
       list of conditions and the following disclaimer.
    2. Redistributions in binary form must reproduce the above copyright notice,
       this list of conditions and the following disclaimer in the documentation
       and/or other materials provided with the distribution.

    THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
    ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
    WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
    DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
    ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
    (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
    LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
    ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
    (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
    SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""


import functools
import asyncio
import inspect
import logging
import random
import math
import time
import sys

import moderngl_window as mglw

from .utils import trimmed_traceback


logger = logging.getLogger(__name__)


class Timer(mglw.timers.clock.Timer):
    
    @property
    def time(self) -> float:

        if self._start_time is None:
            return 0

        return super(Timer, self).time


class FakeTime(object):
    
    def __init__(self):
        self._time = 0
        
    def time(self):
        return self._time        

    def sleep(self, dt):
        self._time += dt


def setup_fake_time():
    
    mglw.timers.clock.time = FakeTime()
    return mglw.timers.clock.time


def setup_real_time():
    mglw.timers.clock.time = time


class Scheduler(object):
    
    def __init__(self, timer):
        
        self._timer = timer
        self._sched = {}
        
    def schedule_once(self, foo, delay, *args, **kwargs):
        logger.info('Enter Scheduler.schedule_once(foo=%r, delay=%r, *args=%r, **kwargs=%r).', foo, delay, args, kwargs) 

        self.unschedule(foo)
        self._sched[self._timer.time + delay, foo] = ('once', self._timer.time, None, args, kwargs)
        
    def schedule_interval(self, foo, interval, *args, **kwargs):
        logger.info('Enter Scheduler.schedule_interval(foo=%r, interval=%r, *args=%r, **kwargs=%r).', foo, interval, args, kwargs) 
        
        self.unschedule(foo)
        self._sched[self._timer.time + interval, foo] = ('interval', self._timer.time, interval, args, kwargs)  
        
    def schedule_interval_soft(self, foo, interval, *args, **kwargs):     
        logger.info('Enter Scheduler.schedule_interval_soft(foo=%r, interval=%r, *args=%r, **kwargs=%r).', foo, interval, args, kwargs) 

        self.unschedule(foo)
        self._sched[self._timer.time + interval, foo] = ('soft', self._timer.time, interval, args, kwargs)
        
    def unschedule(self, foo):
        # Python functions should not be compared for equality, not for identity:
        # https://stackoverflow.com/questions/18216597/how-should-functions-be-tested-for-equality-or-identity
        self._sched = {k: v for k, v in self._sched.items() if k[1] != foo}
        
    def call(self):
        
        tim0 = self._timer.time
        reap = {k: v for k, v in self._sched.items() if k[0] <= tim0}
        self._sched = {k: v for k, v in self._sched.items() if k[0] > tim0}
        
        for k, v in reap.items():
            
            t, foo = k
            _type, t0, i, args, kwargs  = v
            
            t1 = self._timer.time

            try:
                foo(t1, t1 - t0, *args, **kwargs)
            except:
                logger.error(trimmed_traceback())
                _type = 'once'
            
            if _type == 'once':
                continue
                
            v = _type, t1, i, args, kwargs
            t = t + i * math.ceil((t1 - t) / i)
            
            if _type == 'interval':
                self._sched[t, foo] = v
                
            if _type == 'soft':
                self._sched[t + random.gauss(0, i / 32), foo] = v

        return max(0, self.time2next())
    
    def time2next(self):
        if self._sched:
            return min(k[0] for k in self._sched) - self._timer.time
        return 0.5
        

class ClockLeg(object):

    def __init__(self, timer=None, **kwargs):

        super(ClockLeg, self).__init__()

        self.scheduler = Scheduler(timer)
        self.schedules = {}
        
    # TODO: handle errors so application does not exit on user errors.
    def sonic_live_loop2(self, times=0, sync=True, *args, **kwargs):
        return self.schedule_once(0, times, sync, *args, **kwargs)
    
    def sonic_live_loop(self, times=0, sync=False, *args, **kwargs):
        return self.schedule_once(0, times, sync, *args, **kwargs)
    
    def run_me(self, delay=0, *args, **kwargs):
        return self.schedule_once(delay, 1, False, *args, **kwargs)
    
    def run_me_every(self, interval, *args, **kwargs):
        return self.schedule_interval(interval, *args, **kwargs)
    
    def schedule_once(self, delay=0, times=1, sync=False, *args, **kwargs):
        """Schedule decorated function to be called once after ``delay`` seconds.
        
        This function uses the default clock. ``delay`` can be a float. The
        arguments passed to ``func`` are ``dt`` (time since last function call),
        followed by any ``*args`` and ``**kwargs`` given here.
        
        :Parameters:
            `delay` : float
                The number of seconds to wait before the timer lapses.
        """
        def schedule0(foo):
            
            async def fuu(ct, dt):

                sc = self.schedules[foo.__name__]

                try:
                    while True:
                        
                        spec = sc['spec']
                        kwargs = sc['kwargs']
                        args = sc['args']
                        f00 = sc['foo']

                        args0 = (ct, dt) + args
                        args0 = args0[:len(spec.args)]

                        await f00(*args0, **kwargs)
                        
                        dt = time.time() - ct
                        ct = ct + dt

                        sc['times'] -= 1
                        if sc['times'] == 0:
                            break

                except asyncio.exceptions.CancelledError:
                    pass
                except:
                    logger.error(trimmed_traceback())

            @functools.wraps(foo)
            def bar(ct, dt, *args, **kwargs):
                
                sc = self.schedules[foo.__name__]

                if inspect.isgeneratorfunction(foo):
                    
                    goo = sc.get('gen')
                    if goo is None:
                        goo = foo(ct, dt, *args, **kwargs)
                        sc['gen'] = goo
                        delay = next(goo)

                    else:
                        delay = goo.send((ct, dt))
                    
                    if delay is not None:
                        self.scheduler.schedule_once(bar, delay, times, *args, **kwargs)
                        
                elif inspect.iscoroutinefunction(foo):

                    sc['spec'] = inspect.getfullargspec(foo)
                    sc['times'] = times
                    sc['kwargs'] = kwargs
                    sc['args'] = args
                    sc['foo'] = foo

                    task = asyncio.create_task(fuu(ct, dt))
                    sc['task'] = task
                    
                else:
                    foo(ct, dt, *args, **kwargs)
                
            if sync and inspect.iscoroutinefunction(foo):
                sc = self.schedules.get(foo.__name__, {}) 
                if 'task' in sc:

                    sc['spec'] = inspect.getfullargspec(foo)
                    sc['times'] = times                    
                    sc['kwargs'] = kwargs
                    sc['args'] = args
                    sc['foo'] = foo

                    return foo

            self.unschedule(foo)
            self.schedules.setdefault(foo.__name__, {})['func'] = bar
            self.scheduler.schedule_once(bar, delay, *args, **kwargs)

            return foo

        if inspect.isroutine(delay): # @app.run_me - without ()
            foo , delay = delay, 0
            return schedule0(foo)

        if inspect.isroutine(times): # @app.sonic_live_loop - without ()
            foo , times = times, 0
            return schedule0(foo)

        return schedule0

    def schedule_interval(self, interval, *args, **kwargs):
        """Schedule decorated function on the default clock every interval seconds.
        
        The arguments passed to ``func`` are ``dt`` (time since last function
        call), followed by any ``*args`` and ``**kwargs`` given here.
        
        :Parameters:
            `interval` : float
                The number of seconds to wait between each call.
        """
        logger.info('Enter ClockLeg.schedule_interval(interval=%r, *args=%r, **kwargs=%r).', interval, args, kwargs) 

        def schedule0(foo):

            if inspect.iscoroutinefunction(foo):
                raise TypeError('Coroutine functions can only be scheduled with schedule_once() and its aliases.')
                
            if inspect.isgeneratorfunction(foo):
                raise TypeError('Generator functions can only be scheduled with schedule_once() and its aliases.')
                
            self.unschedule(foo)
            self.schedules.setdefault(foo.__name__, {})['func'] = foo
            self.scheduler.schedule_interval(foo, interval, *args, **kwargs)

            return foo

        return schedule0

    def schedule_interval_soft(self, interval, *args, **kwargs):
        """Schedule a function to be called every ``interval`` seconds.
        
        This method is similar to `schedule_interval`, except that the
        clock will move the interval out of phase with other scheduled
        functions so as to distribute CPU more load evenly over time.
        """
        def schedule0(foo):

            if inspect.iscoroutinefunction(foo):
                raise TypeError('Coroutine functions can only be scheduled with schedule_once() and its aliases.')
                
            if inspect.isgeneratorfunction(foo):
                raise TypeError('Generator functions can only be scheduled with schedule_once() and its aliases.')
                
            self.unschedule(foo)
            self.schedules.setdefault(foo.__name__, {})['func'] = foo
            self.scheduler.schedule_interval_soft(foo, interval, *args, **kwargs)

            return foo

        return schedule0

    def unschedule(self, foo=None, **kwargs):
        """Remove function from the default clock's schedule.
        
        No error is raised if the ``func`` was never scheduled.
        
        :Parameters:
            `foo` : callable
                The function to remove from the schedule. If no function is given
                unschedule the caller.
        """
        if foo is None:
            fname = inspect.stack()[kwargs.get('levels_up', 1)][3] 
        elif type(foo) is str:
            fname = foo
        else:
            fname = foo.__name__
            
        d = self.schedules.pop(fname, {})
        
        if 'func' in d:
            self.scheduler.unschedule(d.get('func'))
        
        if 'task' in d:
            d['task'].cancel()
        
