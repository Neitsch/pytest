from collections import namedtuple, Counter, defaultdict
import sys
import os
import autopep8
from io import StringIO
from functools import reduce

CALL_DATA = namedtuple(
    "CallData", ["args", "kwargs", "output", "function", "dependencies"])
GETATTR_DATA = namedtuple("GetAttrData", ["name", "output"])
SETATTR_DATA = namedtuple("SetAttrData", ["name", "input"])
SPECIAL_ATTR_DATA = namedtuple("SpecialAttrData",
                               ["name", "args", "kwargs", "output"])
PRIMITIVES = (int, float, bool)
ALL_PRIMITIVES = (int, float, bool, str)

TYPES = [list, dict, tuple, int, float, bool, complex, str]

def fuzz_val(val):
    fuzz_vals = []
    for val_type in TYPES:
        if(type(val) == val_type): continue
        fuzz_vals.append(val_type())
    return fuzz_vals

def metamorphic_change(val):
    if type(val) == bool:
        return [not val]
    elif type(val) in (int, float, complex):
        return [-1*val, 2*val]
    elif type(val) == list:
        return [[],list(reversed(val))]
    elif type(val) == str:
        return ["",val.lower(), val.upper()]
    else:
        return []

def serialize_value(val, dep_tracker, name_hint=None):
    if val is None:
        return "None"
    if type(val) == dict:
        return "{" + ", ".join([
            "{}: {}".format(
                serialize_value(k, dep_tracker,
                                "dict_{}_key".format(name_hint)),
                serialize_value(v, dep_tracker,
                                "dict_{}_value".format(name_hint)))
            for k, v in val.items()
        ]) + "}"
    if type(val) == list:
        return "[" + ", ".join([
            serialize_value(v, dep_tracker, "arr_{}".format(name_hint))
            for v in val
        ]) + "]"
    if type(val) == tuple:
        return "(" + ", ".join([
            serialize_value(v, dep_tracker, "tuple_{}".format(name_hint))
            for v in val
        ]) + ")"
    if type(val) in PRIMITIVES:
        return str(val)
    if type(val) == str:
        return "'{}'".format(val)
    if hasattr(val, '__class__'):
        mock_attrs = []
        mock_assert = None
        for a in object.__getattribute__(val, "_get_data"):
            if a.name != "__class__":
                mock_attrs.append("{}={}".format(a.name,
                                                 serialize_value(
                                                     a.output, dep_tracker,
                                                     a.name)))
        iter_attr = None
        for a in object.__getattribute__(val, "_special_data"):
            if a.name == "__call__":
                mock_attrs.append("return_value={}".format(
                    serialize_value(a.output, dep_tracker, "return_value")))
                mock_assert = (list(a.args), a.kwargs)
            if a.name == "__iter__":
                iter_attr = []
                for b in object.__getattribute__(a.output, "_special_data"):
                    if b.name == "__next__":
                        iter_attr.append(b.output)
        if iter_attr is not None:
            return "iter({})".format(
                serialize_value(iter_attr, dep_tracker, "iter"))
        mock_thing = dep_tracker.add("MagicMock({})".format(
            ", ".join(mock_attrs)), name_hint)
        if mock_assert is not None:
            all_primitives = (reduce(
                lambda acc, x: acc and (type(x) in ALL_PRIMITIVES), mock_assert[0],
                True
            ) and reduce(
                lambda acc, x: acc and (type(x[0]) in ALL_PRIMITIVES) and (type(x[1]) in ALL_PRIMITIVES),
                mock_assert[1].items(), True))
            if all_primitives:
                dep_tracker.assert_called(
                    mock_thing,
                    (serialize_value(mock_assert[0], dep_tracker,
                                     "assert_args_{}".format(name_hint)),
                     serialize_value(mock_assert[1], dep_tracker,
                                     "assert_kwargs_{}".format(name_hint))))
            else:
                dep_tracker.assert_called(mock_thing)
        return mock_thing


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
    if type(val) in PRIMITIVES:
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


class DependencyTracker(object):
    def __init__(self):
        self.dependencies = []
        self.num_occurence = Counter()
        self.prim = False
        self.asserts = defaultdict(list)
        self.called = Counter()

    def add(self, value, hint="id"):
        if self.prim:
            self.prim = False
            return value
        self.num_occurence[hint] += 1
        if self.num_occurence[hint] == 1:
            title = hint
        else:
            title = "{}_{}".format(hint, self.num_occurence[hint])
        self.dependencies.append("{} = {}".format(title, value))
        return title

    def get_lines(self):
        return self.dependencies

    def get_asserts(self):
        return [
            "{}.assert_has_calls([{}])".format(identifier, ", ".join([
                "call(*{}, **{})".format(args, kwargs)
                for (args, kwargs) in arguments
            ])) for identifier, arguments in self.asserts.items()
        ] + [
            "assert {}.call_count == {}".format(k, v)
            for k, v in self.called.items()
        ]
#        return self.asserts

    def assert_called(self, identifier, arguments=None):
        if arguments is not None:
            self.asserts[identifier].append(arguments)
        self.called[identifier] += 1


#        if arguments:
#            self.asserts.append("{}.assert_called_once_with(*{}, **{})".format(
#                identifier, arguments[0], arguments[1]))
#        else:
#            self.asserts.append("{}.assert_called_once()".format(identifier))


def track_class(thorough=False, trusted=True):
    def method_wrapper_outer(fnc, list_of_calls, write_testcases):
        if "@pytest_ar" in globals().keys():
            return fnc

        def method_wrapper(*args, **kwargs):
            track_on = [True]
            args = copy_and_placehold_data(args, track_on)
            kwargs = copy_and_placehold_data(kwargs, track_on)
            result = fnc(*copy_call_data(args), **copy_call_data(kwargs))
            dep_tracker = DependencyTracker()
            call_data = CALL_DATA(
                args=[
                    serialize_value(arg, dep_tracker, "arg") for arg in args
                ],
                kwargs={
                    serialize_value(k, dep_tracker, "kwarg_key"):
                    serialize_value(kwarg, dep_tracker, "kwarg_value")
                    for k, kwarg in kwargs
                },
                output=serialize_value(result, dep_tracker, "output"),
                dependencies=dep_tracker,
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
            seen_testcases = set()
            file_handle.write("""from mock import MagicMock, call
from {module_import_path} import {class_name}

class Test{class_name}(object):
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
                call_data_args = ", ".join(call_data.args)
                call_data_kwargs = (", " + ", ".join(\
                    ["{}={}".format(k, a) for k, a in call_data.kwargs]))\
                    if call_data.kwargs else ""

                testcase_key = (call_data.function.__qualname__,
                                call_data.function.__name__,
                                call_data_args,
                                class_obj.__name__,
                                call_data_kwargs
                                )

                if testcase_key in seen_testcases:
                    continue
                else:
                    seen_testcases.add(testcase_key)

                if(not trusted):
                    print("\nFor {function_name}:\noutput:\n{output}\ninput:\n{call_data_args}\n"
                            .format(function_name=call_data.function.__name__,
                                    output=call_data.output,
                                    call_data_args=call_data_args))

                    try:
                        resp = input("Is this correct? [y/n]: ").strip()
                        print(resp)
                        while(not(resp.lower() == 'y' or resp.lower() == 'n' or
                            resp.lower() == 'yes' or resp.lower() == 'no')):

                                resp = input("Invalid input, please enter y or n: ")
                        if(resp.lower() == 'n' or resp.lower() == 'no'):
                            print('Incorrect execution, moving to next call')
                            continue
                    except:
                        print('An error occured, moving to next call')
                        continue

                file_handle.write(
                    """   def test_{function_name}_{counter}(self):
    {dependencies}
    assert {output} == {function_call}({args}{kwargs})
    {asserts}
""".format(function_call=call_data.function.__qualname__,
                function_name=call_data.function.__name__,
                counter=counter,
                dependencies="\n    ".join(call_data.dependencies.get_lines()),
                output=call_data.output,
                args=call_data_args,
                class_name=class_obj.__name__,
                asserts="\n    ".join(call_data.dependencies.get_asserts()),
                kwargs=call_data_kwargs))
                counter += 1
            res = autopep8.fix_code(file_handle.getvalue(), {
                "aggressive": 10,
                "experimental": True
            })
            if thorough:
                #print(list_of_calls)
                for call_data in list_of_calls:
                    call_data_args_list = list(call_data.args)
                    for idx,arg_val in enumerate(call_data.args):
                        if(arg_val != 'arg'):
                            for fuzz_arg in fuzz_val(eval(arg_val)):
                                fuzz_arg = fuzz_arg if fuzz_arg != '' else "''"
                                call_data_args_list[idx] = str(fuzz_arg)
                                call_data_args = ", ".join(call_data_args_list)
                                call_data_kwargs = (", " + ", ".join(
                                    ["{}={}".format(k, a) for k, a in call_data.kwargs]))\
                                    if call_data.kwargs else ""

                                testcase_key = (call_data.function.__qualname__,
                                                call_data.function.__name__,
                                                call_data_args,
                                                class_obj.__name__,
                                                call_data_kwargs
                                                )

                                if testcase_key in seen_testcases:
                                    continue
                                else:
                                    seen_testcases.add(testcase_key)

                                file_handle.write(
                                    """   def test_{function_name}_thorough_fuzz_{counter}(self):
    {dependencies}
    try:
        {function_call}({args}{kwargs})
    except e:
        print(e)
    {asserts}
""".format(function_call=call_data.function.__qualname__,
                                function_name=call_data.function.__name__,
                                counter=counter,
                                dependencies="\n    ".join(call_data.dependencies.get_lines()),
                                output=call_data.output,
                                args=call_data_args,
                                class_name=class_obj.__name__,
                                asserts="\n    ".join(call_data.dependencies.get_asserts()),
                                kwargs=call_data_kwargs))
                                counter += 1
                            res = autopep8.fix_code(file_handle.getvalue(), {
                                "aggressive": 10,
                                "experimental": True
                            })

                            for metamorph_arg in metamorphic_change(eval(arg_val)):
                                metamorph_arg = metamorph_arg if metamorph_arg != '' else "''"
                                call_data_args_list[idx] = str(metamorph_arg)
                                call_data_args = ", ".join(call_data_args_list)
                                call_data_kwargs = (", " + ", ".join(\
                                    ["{}={}".format(k, a) for k, a in call_data.kwargs]))\
                                    if call_data.kwargs else ""

                                testcase_key = (call_data.function.__qualname__,
                                                call_data.function.__name__,
                                                call_data_args,
                                                class_obj.__name__,
                                                call_data_kwargs
                                                )

                                if testcase_key in seen_testcases:
                                    continue
                                else:
                                    seen_testcases.add(testcase_key)

                                file_handle.write(
                                    """   def test_{function_name}_thorough_metamorphic_{counter}(self):
    {dependencies}
    try:
        {function_call}({args}{kwargs})
    except e:
        print(e)
    {asserts}
""".format(function_call=call_data.function.__qualname__,
                                function_name=call_data.function.__name__,
                                counter=counter,
                                dependencies="\n    ".join(call_data.dependencies.get_lines()),
                                output=call_data.output,
                                args=", ".join(call_data_args_list),
                                class_name=class_obj.__name__,
                                asserts="\n    ".join(call_data.dependencies.get_asserts()),
                                kwargs=(", " + ", ".join(
                                ["{}={}".format(k, a) for k, a in call_data.kwargs]))
                                if call_data.kwargs else ""))
                                counter += 1
                            res = autopep8.fix_code(file_handle.getvalue(), {
                                "aggressive": 10,
                                "experimental": True
                            })

                    #print(", ".join(call_data.args))
                    #print(", ".join(call_data_args_list))

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
