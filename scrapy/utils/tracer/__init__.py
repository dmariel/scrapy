import atexit
import inspect

class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]
        
class Tracer(metaclass=Singleton):
    def __init__(self):
        self.traces = set()
        atexit.register(self.cleanup)

    def visited(self, id):
        caller = inspect.stack()[1][3]
        id_formatted = "{:02d}".format(id)
        self.traces.add(f"{caller}:  #{id_formatted}")

    def cleanup(self):
        sorted_calls = list(sorted(self.traces))
        f = open('./traces.txt', 'w')
        f.write("\n".join(sorted_calls))
        f.close()

