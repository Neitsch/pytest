import atexit
from collections import namedtuple
import sys
import os
import autopep8
from io import StringIO

CALL_DATA = namedtuple("CallData", ["args", "kwargs", "output", "function"])
GETATTR_DATA = namedtuple("GetAttrData", ["name", "output"])
SETATTR_DATA = namedtuple("SetAttrData", ["name", "input"])
SPECIAL_ATTR_DATA = namedtuple("SpecialAttrData",
                               ["name", "args", "kwargs", "output"])


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
        mock_attrs = []
        for a in object.__getattribute__(val, "_get_data"):
            if a.name != "__class__":
                mock_attrs.append("{}={}".format(a.name,
                                                 serialize_value(a.output)))
        iter_attr = None
        for a in object.__getattribute__(val, "_special_data"):
            if a.name == "__call__":
                mock_attrs.append("return_value={}".format(
                    serialize_value(a.output)))
            if a.name == "__iter__":
                iter_attr = []
                for b in object.__getattribute__(a.output, "_special_data"):
                    if b.name == "__next__":
                        iter_attr.append(b.output)
        if iter_attr is not None:
            return "iter({})".format(serialize_value(iter_attr))
        return "MagicMock({})".format(", ".join(mock_attrs))


def copy_and_placehold_data(val, track_on):
    if val is None:
        return None
    if type(val) == dict:
        return {
            k: copy_and_placehold_data(v, track_on)
            for k, v in val.items()
        }
    if type(val) == list:
        return [copy_and_placehold_data(v, track_on) for v in val]
    if type(val) == tuple:
        return tuple([copy_and_placehold_data(v, track_on) for v in val])
    if type(val) in (int, float, bool):
        return val
    if type(val) == str:
        return str(val)
    if hasattr(val, '__class__'):
        m = Proxy(val, track_on)
        return m


def copy_call_data(val):
    if val is None:
        return None
    if type(val) == dict:
        return {k: copy_call_data(v) for k, v in val.items()}
    if type(val) == list:
        return [copy_call_data(v) for v in val]
    if type(val) == tuple:
        return tuple([copy_call_data(v) for v in val])
    if type(val) in (int, float, bool):
        return val
    if type(val) == str:
        return str(val)
    if hasattr(val, '__class__'):
        return val


class Proxy(object):
    __slots__ = [
        "_obj", "_track_on", "__weakref__", "_set_data", "_get_data",
        "_special_data"
    ]

    def __init__(self, obj, track_on):
        object.__setattr__(self, "_obj", obj)
        object.__setattr__(self, "_track_on", track_on)
        object.__setattr__(self, "_set_data", [])
        object.__setattr__(self, "_get_data", [])
        object.__setattr__(self, "_special_data", [])

    #
    # proxying (special cases)
    #
    def __getattribute__(self, name):
        if not object.__getattribute__(self, "_track_on")[0]:
            return getattr(object.__getattribute__(self, "_obj"), name)
        object.__getattribute__(self, "_track_on")[0] = False
        output = getattr(object.__getattribute__(self, "_obj"), name)
        # if name == "__class__":
        #     return output
        return_value = copy_and_placehold_data(output,
                                               object.__getattribute__(
                                                   self, "_track_on"))
        return_value_copy = copy_call_data(return_value)
        object.__getattribute__(self, "_get_data").append(
            GETATTR_DATA(name, return_value_copy))
        object.__getattribute__(self, "_track_on")[0] = True
        return return_value

    def __delattr__(self, name):
        if not object.__getattribute__(self, "_track_on")[0]:
            delattr(object.__getattribute__(self, "_obj"), name)
        object.__getattribute__(self, "_track_on")[0] = False
        delattr(object.__getattribute__(self, "_obj"), name)
        object.__getattribute__(self, "_track_on")[0] = True

    def __setattr__(self, name, value):
        if not object.__getattribute__(self, "_track_on")[0]:
            return setattr(object.__getattribute__(self, "_obj"), name, value)
        object.__getattribute__(self, "_track_on")[0] = False
        set_value = copy_and_placehold_data(value,
                                            object.__getattribute__(
                                                self, "_track_on"))
        set_value_copy = copy_call_data(set_value)
        setattr(object.__getattribute__(self, "_obj"), name, set_value)
        object.__getattribute__(self, "_set_data").append(
            SETATTR_DATA(name, set_value_copy))
        object.__getattribute__(self, "_track_on")[0] = True

    def __nonzero__(self):
        if not object.__getattribute__(self, "_track_on")[0]:
            bool(object.__getattribute__(self, "_obj"))
        object.__getattribute__(self, "_track_on")[0] = False
        res = bool(object.__getattribute__(self, "_obj"))
        object.__getattribute__(self, "_track_on")[0] = True
        return res

    def __str__(self):
        if not object.__getattribute__(self, "_track_on")[0]:
            return str(object.__getattribute__(self, "_obj"))
        object.__getattribute__(self, "_track_on")[0] = False
        res = str(object.__getattribute__(self, "_obj"))
        object.__getattribute__(self, "_track_on")[0] = True
        return res

    def __repr__(self):
        if not object.__getattribute__(self, "_track_on")[0]:
            return repr(object.__getattribute__(self, "_obj"))
        object.__getattribute__(self, "_track_on")[0] = False
        res = repr(object.__getattribute__(self, "_obj"))
        object.__getattribute__(self, "_track_on")[0] = True
        return res

    #
    # factories
    #
    _special_names = [
        '__abs__',
        '__add__',
        '__and__',
        '__call__',
        '__cmp__',
        '__coerce__',
        '__contains__',
        '__delitem__',
        '__delslice__',
        '__div__',
        '__divmod__',
        '__eq__',
        '__float__',
        '__floordiv__',
        '__ge__',
        '__getitem__',
        '__getslice__',
        '__gt__',
        '__hash__',
        '__hex__',
        '__iadd__',
        '__iand__',
        '__idiv__',
        '__idivmod__',
        '__ifloordiv__',
        '__ilshift__',
        '__imod__',
        '__imul__',
        '__int__',
        '__invert__',
        '__ior__',
        '__ipow__',
        '__irshift__',
        '__isub__',
        '__iter__',
        '__itruediv__',
        '__ixor__',
        '__le__',
        '__len__',
        '__long__',
        '__lshift__',
        '__lt__',
        '__mod__',
        '__mul__',
        '__ne__',
        '__neg__',
        '__next__',
        '__oct__',
        '__or__',
        '__pos__',
        '__pow__',
        '__radd__',
        '__rand__',
        '__rdiv__',
        '__rdivmod__',
        '__reduce__',
        '__reduce_ex__',
        '__repr__',
        '__reversed__',
        '__rfloorfiv__',
        '__rlshift__',
        '__rmod__',
        '__rmul__',
        '__ror__',
        '__rpow__',
        '__rrshift__',
        '__rshift__',
        '__rsub__',
        '__rtruediv__',
        '__rxor__',
        '__setitem__',
        '__setslice__',
        '__sub__',
        '__truediv__',
        '__xor__',
        'next',
    ]

    @classmethod
    def _create_class_proxy(cls, theclass):
        """creates a proxy for the given class"""

        def make_method(name):
            def method(self, *args, **kw):
                if not object.__getattribute__(self, "_track_on")[0]:
                    return getattr(
                        object.__getattribute__(self, "_obj"), name)(*args,
                                                                     **kw)
                object.__getattribute__(self, "_track_on")[0] = False
                args_value = copy_and_placehold_data(args,
                                                     object.__getattribute__(
                                                         self, "_track_on"))
                args_value_copy = copy_call_data(args_value)
                kwargs_value = copy_and_placehold_data(kw,
                                                       object.__getattribute__(
                                                           self, "_track_on"))
                kwargs_value_copy = copy_call_data(kwargs_value)
                output = getattr(object.__getattribute__(self, "_obj"),
                                 name)(*args_value, **kwargs_value)
                output_value = copy_and_placehold_data(output,
                                                       object.__getattribute__(
                                                           self, "_track_on"))
                output_value_copy = copy_call_data(output_value)
                object.__getattribute__(self, "_special_data").append(
                    SPECIAL_ATTR_DATA(name, args_value_copy, kwargs_value_copy,
                                      output_value_copy))
                object.__getattribute__(self, "_track_on")[0] = True
                return output_value

            return method

        namespace = {}
        for name in cls._special_names:
            if hasattr(theclass, name):
                namespace[name] = make_method(name)
        return type("%s(%s)" % (cls.__name__, theclass.__name__), (cls, ),
                    namespace)

    def __new__(cls, obj, *args, **kwargs):
        """
        creates an proxy instance referencing `obj`. (obj, *args, **kwargs) are
        passed to this class' __init__, so deriving classes can define an
        __init__ method of their own.
        note: _class_proxy_cache is unique per deriving class (each deriving
        class must hold its own cache)
        """
        try:
            cache = cls.__dict__["_class_proxy_cache"]
        except KeyError:
            cls._class_proxy_cache = cache = {}
        try:
            theclass = cache[obj.__class__]
        except KeyError:
            cache[obj.__class__] = theclass = cls._create_class_proxy(
                obj.__class__)
        ins = object.__new__(theclass)
        theclass.__init__(ins, obj, *args, **kwargs)
        return ins


def track_class():
    def method_wrapper_outer(fnc, list_of_calls, write_testcases):
        if "@pytest_ar" in globals().keys():
            return fnc

        def method_wrapper(*args, **kwargs):
            track_on = [True]
            args = copy_and_placehold_data(args, track_on)
            kwargs = copy_and_placehold_data(kwargs, track_on)
            result = fnc(*copy_call_data(args), **copy_call_data(kwargs))
            call_data = CALL_DATA(
                args=[serialize_value(arg) for arg in args],
                kwargs=serialize_value(kwargs),
                output=serialize_value(result),
                function=fnc)
            list_of_calls.append(call_data)
            write_testcases()
            return result

        return method_wrapper

    def filter_methods(cls):
        return [x for x in cls.__dict__.keys() if callable(getattr(cls, x))]

    def decorator(class_obj):
        list_of_calls = []
        file_path = sys.modules[class_obj.__module__].__file__

        def write_testcases():
            if "@pytest_ar" in globals().keys():
                return
            file_handle = StringIO()
            file_handle.write("""from mock import MagicMock
from {module_import_path} import {class_name}

class Test(object):
""".format(
                module_import_path=os.path.relpath(file_path,
                                                   os.path.commonprefix([
                                                       file_path,
                                                       os.getcwd()
                                                   ]))[:-3].replace("/", "."),
                class_name=class_obj.__name__,
            ))
            counter = 0
            for call_data in list_of_calls:
                file_handle.write(
                    """   def test_{function_name}_{counter}(self):
    assert {output} == {function_call}({args}, **{kwargs})
""".format(function_call=call_data.function.__qualname__,
                function_name=call_data.function.__name__,
                counter=counter,
                output=call_data.output,
                args=", ".join(call_data.args),
                kwargs=call_data.kwargs))
                counter += 1
            res = autopep8.fix_code(file_handle.getvalue(), {
                "aggressive": 10,
                "experimental": True
            })
            with open("test_{}.py".format(class_obj.__name__),
                      "w") as real_file:
                real_file.write(res)

        method_names = filter_methods(class_obj)
        for method_name in method_names:
            func = getattr(class_obj, method_name)
            setattr(class_obj, method_name,
                    method_wrapper_outer(func, list_of_calls, write_testcases))
        return class_obj

    return decorator
