import bdb
import sys
import io

class StepLimitExceeded(Exception):
    pass

class InputGenerator:
    def __init__(self, data):
        self.tokens = iter(data.split())
    def __call__(self, prompt=""):
        try:
            return next(self.tokens)
        except StopIteration:
            raise EOFError("EOF when reading a line")

ALLOWED_MODULES = {'math', 'random', 'collections', 'heapq', 'bisect', 'itertools', 'functools'}

def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name in ALLOWED_MODULES:
        return __import__(name, globals, locals, fromlist, level)
    raise ImportError(f"Importing '{name}' is not allowed.")

class TraceLogger(bdb.Bdb):
    def __init__(self):
        super().__init__()
        self.snapshots = []
        self.stdout_buffer = io.StringIO()
        self.MAX_STEPS = 1000
    
    def safe_repr(self, val):
        try:
            s = repr(val)
            return s[:200] + "..." if len(s) > 500 else s
        except:
            return "<error>"

    def capture_snapshot(self, frame, event_type, arg=None):
        if len(self.snapshots) >= self.MAX_STEPS:
            raise StepLimitExceeded()

        if frame.f_code.co_filename != '<string>':
            return

        locals_dict = {k: self.safe_repr(v) for k, v in frame.f_locals.items() 
                       if not k.startswith('__')}
        
        if event_type == 'return':
            locals_dict['__return__'] = self.safe_repr(arg)

        self.snapshots.append({
            "line": frame.f_lineno,
            "event": event_type,
            "func": frame.f_code.co_name,
            "locals": locals_dict,
            "stdout": self.stdout_buffer.getvalue(),
            "error": None 
        })

    def user_line(self, frame):
        self.capture_snapshot(frame, 'line')

    def user_return(self, frame, return_value):
        self.capture_snapshot(frame, 'return', return_value)

def run_and_trace(code_string, custom_input=""):
    logger = TraceLogger()

    custom_input_func = InputGenerator(custom_input)
    
    safe_builtins = {
        "__import__": safe_import,
        "print": lambda *args, **kwargs: print(*args, file=logger.stdout_buffer, **kwargs),
        "input": custom_input_func,
        "int": int, "float": float, "str": str, "bool": bool,
        "list": list, "dict": dict, "set": set, "tuple": tuple,
        "range": range, "len": len, "enumerate": enumerate, 
        "map": map, "filter": filter, "zip": zip, "sorted": sorted,
        "abs": abs, "min": min, "max": max, "sum": sum, 
        "True": True, "False": False, "None": None,
        "Exception": Exception, "ValueError": ValueError, "TypeError": TypeError
    }
    
    sandbox = {"__builtins__": safe_builtins}
    
    orig_stdout = sys.stdout
    
    try:
        code_obj = compile(code_string, '<string>', 'exec')
        logger.run(code_obj, sandbox, sandbox)
    except StepLimitExceeded:
        logger.snapshots.append({"line": -1, "error": "Step limit exceeded (1000+ steps)."})
    except Exception as e:
        logger.snapshots.append({
            "line": getattr(e, 'lineno', -1),
            "error": f"Runtime Error: {str(e)}",
            "locals": {},
            "stdout": logger.stdout_buffer.getvalue()
        })
    finally:
        sys.stdout = orig_stdout
    
    return logger.snapshots