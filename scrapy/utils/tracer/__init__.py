import atexit

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
        self.traces.add(id)

    def cleanup(self):
        f = open('./traces.txt', 'w')
        f.write(str(self.traces))
        f.close()

