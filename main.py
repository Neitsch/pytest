import helperstuff
import inspect
import json
import re
import sys
from types import FunctionType, MethodType, LambdaType


def main():
    def method_wrapper_outer(fnc, module_title, class_name):
        def method_wrapper(*args, **kwargs):
            in_args = str(args)
            in_kwargs = str(kwargs)
            file_handle = open("testcase.py", "w+")
            res = fnc(*args, **kwargs)
            file_handle.write("""import unittest
from {} import {}


class Test{}(unittest.TestCase):
    def test_{}(self):
        output = {}.{}(*{}, **{})
        assert output == {}


if __name__ == '__main__':
    unittest.main()
""".format(module_title, class_name, class_name, fnc.__name__, class_name,
            fnc.__name__, in_args, in_kwargs, res))
            return res

        return method_wrapper

    def filter_methods(cls):
        return [x for x in cls.__dict__.keys() if callable(getattr(cls, x))]

    module_title = "helperstuff"
    class_name = "HelperClass"
    module_obj = sys.modules[module_title]
    module_members = dict(inspect.getmembers(module_obj))
    for k, class_obj in module_members.items():
        if not inspect.isclass(class_obj):
            continue
        method_names = filter_methods(class_obj)
        for method_name in method_names:
            func = getattr(class_obj, method_name)
            setattr(class_obj, method_name,
                    method_wrapper_outer(func, module_title, class_name))
    helperstuff.HelperClass.my_func([55])


if __name__ == '__main__':
    main()
