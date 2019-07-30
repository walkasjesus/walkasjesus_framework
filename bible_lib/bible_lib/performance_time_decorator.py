import time


def performance_time(func):
    """" Decorator to use above a method (like @performance_time) to time how long it took to execute. """
    def func_wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        print('Executed {0} {1:.3}s'.format(func.__name__, time.time() - start_time))
        return result

    return func_wrapper
