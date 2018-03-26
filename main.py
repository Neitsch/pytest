import helperstuff
import inspect
import json
import re
import os
import sys
from types import FunctionType, MethodType, LambdaType


def main():
    def method_wrapper_outer(fnc, module_title, class_name, test_path):
        def method_wrapper(*args, **kwargs):
            in_args = str(args)
            in_kwargs = str(kwargs)
            test_path_parent = os.path.abspath(
                os.path.join(test_path, os.pardir))
            if not os.path.exists(test_path_parent):
                os.makedirs(test_path_parent)
            file_handle = open(test_path, "w+")
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

    for module_title, module_obj in sys.modules.items():
        if not inspect.ismodule(module_obj) or not hasattr(
                module_obj, "__file__") or not module_obj.__file__.startswith(
                    os.getcwd()):
            continue
        test_path = os.path.join(
            "",  #"test",
            os.path.relpath(module_obj.__file__, os.getcwd()))
        test_path = os.path.join(
            os.path.abspath(os.path.join(test_path, os.pardir)),
            "test_" + os.path.split(test_path)[1])
        module_members = dict(inspect.getmembers(module_obj))
        for class_name, class_obj in module_members.items():
            if not inspect.isclass(class_obj):
                continue
            method_names = filter_methods(class_obj)
            for method_name in method_names:
                func = getattr(class_obj, method_name)
                setattr(class_obj, method_name,
                        method_wrapper_outer(func, module_title, class_name,
                                             test_path))
    helperstuff.HelperClass.my_func([55])


if __name__ == '__main__':
    main()
