import atexit
from collections import namedtuple
from mock import patch
import sys

CALL_DATA = namedtuple("CallData", ["args", "kwargs", "output", "function"])


def track_class():
    def serialize_value(val):
        if val is None:
            return "None"
        if type(val) == dict:
            return {k: serialize_value(v) for k, v in val.items()}
        if type(val) == list:
            return "[" + ", ".join([serialize_value(v) for v in val]) + "]"
        if type(val) == tuple:
            return "(" + ", ".join([serialize_value(v) for v in val]) + ")"
        if type(val) in (int, float, bool):
            return str(val)
        if type(val) == str:
            return "'{}'".format(val)
        if hasattr(val, '__class__'):
            #raise Exception("HALP ME!")
            return "MagicMock()"

    def copy_and_placehold_data(val):
        if val is None:
            return None
        if type(val) == dict:
            return {k: copy_and_placehold_data(v) for k, v in val.items()}
        if type(val) == list:
            return [copy_and_placehold_data(v) for v in val]
        if type(val) == tuple:
            return tuple([copy_and_placehold_data(v) for v in val])
        if type(val) in (int, float, bool):
            return val
        if type(val) == str:
            return str(val)
        if hasattr(val, '__class__'):
            m = patch.object(val.__class__)
            print(dir(val))
            m = Mock(wraps=val)
            return m

    def method_wrapper_outer(fnc, list_of_calls):
        def method_wrapper(*args, **kwargs):
            result = fnc(*copy_and_placehold_data(args),
                         **copy_and_placehold_data(kwargs))
            call_data = CALL_DATA(
                args=serialize_value(args),
                kwargs=serialize_value(kwargs),
                output=serialize_value(result),
                function=fnc)
            list_of_calls.append(call_data)
            return result

        return method_wrapper

    def filter_methods(cls):
        return [x for x in cls.__dict__.keys() if callable(getattr(cls, x))]

    def decorator(class_obj):
        list_of_calls = []
        file_path = sys.modules[class_obj.__module__].__file__

        @atexit.register
        def write_testcases():
            with open("test_me.py", "w+") as file_handle:
                file_handle.write("""from mock import MagicMock
from {module_import_path} import {class_name}

class Test(object):
""".format(
                    module_import_path=file_path[:-3],
                    class_name=class_obj.__name__,
                ))
                counter = 0
                for call_data in list_of_calls:
                    file_handle.write(
                        """   def test_{function_name}_{counter}(self):
        assert {output} == {function_call}(*{args}, **{kwargs})
""".format(function_call=call_data.function.__qualname__,
                    function_name=call_data.function.__name__,
                    counter=counter,
                    output=call_data.output,
                    args=call_data.args,
                    kwargs=call_data.kwargs))
                    counter += 1

        method_names = filter_methods(class_obj)
        for method_name in method_names:
            func = getattr(class_obj, method_name)
            setattr(class_obj, method_name,
                    method_wrapper_outer(func, list_of_calls))
        return class_obj

    return decorator
