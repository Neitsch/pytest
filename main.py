import helperstuff
import inspect
import os
import sys

KNOWN_CONSTRUCTORS = {}


def handle_value(val, imports):
    if val is None:
        return "None"
    if type(val) == dict:
        return {k: handle_value(v, imports) for k, v in val.items()}
    if type(val) == list:
        return "[" + ", ".join([handle_value(v, imports) for v in val]) + "]"
    if type(val) == tuple:
        return "[" + ", ".join([handle_value(v, imports) for v in val]) + "]"
    if type(val) in (int, float, bool):
        return str(val)
    if type(val) == str:
        return "'{}'".format(val)
    if hasattr(val, '__class__'):
        imports.append("import {}".format(val.__class__.__module__))
        if id(val) in KNOWN_CONSTRUCTORS.keys():
            arg_data = KNOWN_CONSTRUCTORS[id(val)]
            return "{}.{}(*{}, **{})".format(
                val.__class__.__module__, val.__class__.__name__,
                arg_data["args"], arg_data["kwargs"])
        else:
            return "{}.{}()".format(val.__class__.__module__,
                                    val.__class__.__name__)


def main():
    def method_wrapper_outer(fnc, module_title, class_name, test_path):
        def method_wrapper(*args, **kwargs):
            imports = []
            in_kwargs = handle_value(kwargs, imports)
            if fnc.__name__ == "__init__":
                in_args = handle_value(args[1:], imports)
                KNOWN_CONSTRUCTORS[id(args[0])] = {
                    "args": in_args,
                    "kwargs": in_kwargs,
                }
            else:
                in_args = handle_value(args, imports)
            test_path_parent = os.path.abspath(
                os.path.join(test_path, os.pardir))
            if not os.path.exists(test_path_parent):
                os.makedirs(test_path_parent)
            file_handle = open(test_path, "w+")
            return_value = fnc(*args, **kwargs)
            res = handle_value(return_value, imports)
            file_handle.write("""import unittest
from {} import {}
{}


class Test{}(unittest.TestCase):
    def test_{}(self):
        output = {}.{}(*{}, **{})
        assert output == {}


if __name__ == '__main__':
    unittest.main()
""".format(module_title, class_name, "\n".join(imports), class_name,
            fnc.__name__, class_name, fnc.__name__, in_args, in_kwargs, res))
            return return_value

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
    helperstuff.HelperClass(8).my_func([55])


if __name__ == '__main__':
    main()
