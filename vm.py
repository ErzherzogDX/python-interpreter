"""
Simplified VM code which works for some cases.
You need extend/rewrite code to pass all cases.
"""

import builtins
import dis
import operator
import types
import typing as tp


class Frame:
    """
    Frame header in cpython with description
        https://github.com/python/cpython/blob/3.12/Include/internal/pycore_frame.h

    Text description of frame parameters
        https://docs.python.org/3/library/inspect.html?highlight=frame#types-and-members
    """

    def __init__(self,
                 frame_code: types.CodeType,
                 frame_builtins: dict[str, tp.Any],
                 frame_globals: dict[str, tp.Any],
                 frame_locals: dict[str, tp.Any]) -> None:
        self.code = frame_code
        self.builtins = frame_builtins
        self.globals = frame_globals
        self.locals = frame_locals
        self.data_stack: tp.Any = []
        self.return_value: tp.Any = None
        self.ix = 0
        self.com_to_ix: dict[int, int] = {}
        self.current_instruction: tp.Any = None
        self.last_exception: tp.Any = None
        self.current_exception: tp.Any = None
        self.exception_stack: list[str] = []

    bin_ops_list = [operator.add, operator.and_, operator.floordiv, operator.lshift, operator.matmul,
                    operator.mul, operator.mod, operator.or_, operator.pow, operator.rshift,
                    operator.sub, operator.truediv, operator.xor, operator.iadd, operator.iand,
                    operator.ifloordiv, operator.ilshift, operator.imatmul, operator.imul, operator.imod,
                    operator.ior, operator.ipow, operator.irshift, operator.isub, operator.itruediv, operator.ixor]

    compare_op_list = {
        '==': operator.eq,
        '!=': operator.ne,
        '<': operator.lt,
        '<=': operator.le,
        '>': operator.gt,
        '>=': operator.ge
    }

    def top(self) -> tp.Any:
        return self.data_stack[-1]

    def pop(self) -> tp.Any:
        if len(self.data_stack) == 0:
            return None
        return self.data_stack.pop()

    def push(self, *values: tp.Any) -> None:
        self.data_stack.extend(values)

    def popn(self, n: int) -> tp.Any:
        """
        Pop a number of values from the value stack.
        A list of n values is returned, the deepest value first.
        """
        if n > 0:
            returned = self.data_stack[-n:]
            self.data_stack[-n:] = []
            return returned
        else:
            return []

    def jump(self, n: int) -> None:
        self.ix = self.com_to_ix[n]

    def run(self) -> tp.Any:
        lst = list(dis.get_instructions(self.code))
        self.com_to_ix = {instr.offset: idx for idx, instr in enumerate(lst)}

        while self.ix < len(lst):
            instruction = lst[self.ix]
            self.current_instruction = instruction
            in_name = instruction.opname.lower() + "_op"
            prev_ix = self.ix

            try:
                if hasattr(self, in_name):
                    getattr(self, in_name)(instruction.argval)
                else:
                    raise NotImplementedError(f"Opcode {instruction.opname} not implemented")
            except Exception as e:
                self.current_exception = (type(e), e, e.__traceback__)
                self.last_exception = e
                raise
            if in_name == "return_const_op":
                break
            if prev_ix == self.ix:
                self.ix += 1
        return self.return_value

    def resume_op(self, arg: int) -> tp.Any:
        pass

    def push_null_op(self, _: tp.Any) -> tp.Any:
        self.push(None)

    def precall_op(self, arg: int) -> tp.Any:
        pass

    def call_op(self, arg: int) -> None:
        """
        Operation description:
            https://docs.python.org/release/3.12.5/library/dis.html#opcode-CALL
        """
        arguments = self.popn(arg)
        f = self.pop()
        self.pop()
        self.push(f(*arguments))

    def load_name_op(self, arg: str) -> None:
        """
        Partial realization

        Operation description:
            https://docs.python.org/release/3.12.5/library/dis.html#opcode-LOAD_NAME
        """
        if arg in self.locals:
            val = self.locals[arg]
        elif arg in self.globals:
            val = self.globals[arg]
        elif arg in self.builtins:
            val = self.builtins[arg]
        else:
            raise NameError(f"name '{arg}' is not defined")
        self.push(val)

    def load_global_op(self, arg: str) -> None:
        """
        Operation description:
            https://docs.python.org/release/3.12.5/library/dis.html#opcode-LOAD_GLOBAL
        """
        # TODO: parse all scopes
        if arg in self.globals:
            val = self.globals[arg]
        elif arg in self.builtins:
            val = self.builtins[arg]
        else:
            raise NameError(f"name '{arg}' is not defined")

        self.push(val)

    def store_global_op(self, arg: str) -> None:
        self.globals[arg] = self.pop()

    def load_const_op(self, arg: tp.Any) -> None:
        """
        Operation description:
            https://docs.python.org/release/3.12.5/library/dis.html#opcode-LOAD_CONST
        """
        self.push(arg)

    def return_value_op(self, _: tp.Any) -> None:
        """
        Operation description:
            https://docs.python.org/release/3.12.5/library/dis.html#opcode-RETURN_VALUE
        """
        self.return_value = self.pop()

    def return_const_op(self, arg: tp.Any) -> None:
        self.return_value = arg

    def pop_top_op(self, _: tp.Any) -> None:
        """
        Operation description:
            https://docs.python.org/release/3.12.5/library/dis.html#opcode-POP_TOP
        """
        self.pop()

    def make_function_op(self, _: tp.Any) -> None:
        """
        Operation description:
            https://docs.python.org/release/3.8.5/library/dis.html#opcode-MAKE_FUNCTION
        """
        CO_VARARGS = 4
        CO_VARKEYWORDS = 8

        ERR_TOO_MANY_POS_ARGS = 'Too many positional arguments'
        ERR_TOO_MANY_KW_ARGS = 'Too many keyword arguments'
        ERR_MULT_VALUES_FOR_ARG = 'Multiple values for arguments'
        ERR_POSONLY_PASSED_AS_KW = 'Positional-only argument passed as keyword argument'

        code = self.pop()

        def f(*args: tp.Any, **kwargs: tp.Any) -> tp.Any:
            co = code
            varnames = co.co_varnames
            argcount = co.co_argcount
            kwonlyargcount = co.co_kwonlyargcount
            flags = co.co_flags
            posonlyargcount = getattr(co, 'co_posonlyargcount', 0)

            posonlyargnames = varnames[0:posonlyargcount]
            posorkwargnames = varnames[posonlyargcount:argcount]
            positional_param_names = varnames[0:argcount]
            kwonlyargnames = varnames[argcount:argcount + kwonlyargcount]

            idx = argcount + kwonlyargcount
            has_varargs = bool(flags & CO_VARARGS)
            varargsname: tp.Optional[str]
            if has_varargs:
                varargsname = varnames[idx]
                idx += 1
            else:
                varargsname = None

            has_varkwargs = bool(flags & CO_VARKEYWORDS)
            varkwargsname: tp.Optional[str]
            if has_varkwargs:
                varkwargsname = varnames[idx]
                idx += 1
            else:
                varkwargsname = None

            bound_args: tp.Dict[str, tp.Any] = {}
            num_positional_params = len(positional_param_names)

            if len(args) > num_positional_params and not has_varargs:
                raise TypeError(ERR_TOO_MANY_POS_ARGS)

            for i, arg in enumerate(args):
                if i < num_positional_params:
                    param_name = positional_param_names[i]
                    bound_args[param_name] = arg
                else:
                    break

            extra_positional_args = args[num_positional_params:]
            if extra_positional_args:
                if has_varargs and varargsname is not None:
                    bound_args[varargsname] = extra_positional_args
                else:
                    raise TypeError(ERR_TOO_MANY_POS_ARGS)
            else:
                if has_varargs and varargsname is not None and varargsname not in bound_args:
                    bound_args[varargsname] = ()

            if has_varkwargs and varkwargsname is not None and varkwargsname not in bound_args:
                bound_args[varkwargsname] = {}

            for key, value in kwargs.items():
                if key in bound_args and (key in posorkwargnames or key in kwonlyargnames):
                    raise TypeError(ERR_MULT_VALUES_FOR_ARG)
                elif key in kwonlyargnames or key in posorkwargnames:
                    bound_args[key] = value
                elif has_varkwargs and varkwargsname is not None:
                    bound_args[varkwargsname][key] = value
                elif key in posonlyargnames:
                    raise TypeError(ERR_POSONLY_PASSED_AS_KW)
                else:
                    raise TypeError(ERR_TOO_MANY_KW_ARGS)

            f_locals = dict(self.locals)
            f_locals.update(bound_args)

            frame = Frame(code, self.builtins, self.globals, f_locals)
            return frame.run()

        self.push(f)

    def store_name_op(self, arg: str) -> None:
        """
        Operation description:
            https://docs.python.org/release/3.12.5/library/dis.html#opcode-STORE_NAME
        """
        const = self.pop()
        self.locals[arg] = const

    def binary_op_op(self, operation: tp.Any) -> None:
        x, y = self.popn(2)
        self.push(self.bin_ops_list[operation](x, y))

    def get_iter_op(self, _: tp.Any) -> None:
        self.push(iter(self.pop()))

    def for_iter_op(self, jump: int) -> None:
        it = self.top()
        try:
            v = next(it)
            self.push(v)
        except StopIteration:
            self.jump(jump)

    def jump_backward_op(self, delta: int) -> None:
        cur_offset_target = self.com_to_ix[delta]
        self.ix = cur_offset_target

    def end_for_op(self, arg: tp.Any) -> None:
        self.pop_top_op(arg)

    def unpack_sequence_op(self, _: tp.Any) -> None:
        seq = self.pop()
        for x in reversed(seq):
            self.push(x)

    def compare_op_op(self, operation: str) -> None:
        x, y = self.popn(2)
        self.push(self.compare_op_list[operation](x, y))

    def pop_jump_if_false_op(self, jump: int) -> None:
        val = self.pop()
        if not val:
            self.jump(jump)

    def pop_jump_if_true_op(self, jump: int) -> None:
        if self.pop():
            self.ix = self.com_to_ix[jump]

    def binary_slice_op(self, _: tp.Any) -> None:
        end = self.pop()
        start = self.pop()
        container = self.pop()
        self.data_stack.append(container[start:end])

    def build_slice_op(self, cnt: int) -> None:
        if cnt == 2:
            x, y = self.popn(2)
            self.push(slice(x, y))
        elif cnt == 3:
            x, y, z = self.popn(3)
            self.push(slice(x, y, z))

    def binary_subscr_op(self, _: tp.Any) -> None:
        key = self.pop()
        container = self.pop()
        self.data_stack.append(container[key])

    def build_list_op(self, count: int) -> None:
        elts = self.popn(count)
        self.push(elts)

    def store_slice_op(self, _: tp.Any) -> None:
        end = self.pop()
        start = self.pop()
        container = self.pop()
        value = self.pop()
        container[start:end] = value

    def delete_subscr_op(self, _: tp.Any) -> None:
        obj, subscr = self.popn(2)
        del obj[subscr]

    def list_extend_op(self, i: int) -> None:
        seq = self.pop()
        list.extend(self.data_stack[-i], seq)

    def build_const_key_map_op(self, cnt: int) -> None:
        keys = self.pop()
        values = self.popn(cnt)
        self.push(dict(zip(keys, values)))

    def build_set_op(self, count: int) -> None:
        elts = self.popn(count)
        self.push(set(elts))

    def set_update_op(self, _: tp.Any) -> None:
        mp = self.pop()
        current_set = self.top()
        current_set.update(mp)

    def format_value_op(self, _: tp.Any) -> None:
        fx = self.current_instruction.arg
        value = self.pop()
        if fx & 0x03 == 0x03:
            formatted = ascii(value)
        elif fx & 0x03 == 0x01:
            formatted = str(value)
        elif fx & 0x03 == 0x02:
            formatted = repr(value)
        else:
            formatted = value
        self.push(formatted)

    def build_string_op(self, cnt: int) -> None:
        strings = self.popn(cnt)
        result = ''.join(strings)
        self.push(result)

    def store_subscr_op(self, _: tp.Any) -> None:
        key = self.pop()
        container = self.pop()
        value = self.pop()
        container[key] = value

    def load_fast_and_clear_op(self, num: str) -> None:
        if num in self.locals:
            self.push(self.locals[num])
        else:
            self.push(None)
        self.locals[num] = None

    def swap_op(self, i: int) -> None:
        self.data_stack[-i], self.data_stack[-1] = self.data_stack[-1], self.data_stack[-i]

    def store_fast_op(self, name: str) -> None:
        self.locals[name] = self.pop()

    def load_fast_op(self, name: str) -> None:
        val = self.locals[name]
        self.push(val)

    def list_append_op(self, i: int) -> None:
        item = self.pop()
        list.append(self.data_stack[-i], item)

    def reraise_op(self, _: tp.Any) -> None:
        exc = self.pop()
        raise exc

    def load_assertion_error_op(self, _: tp.Any) -> None:
        self.push(AssertionError)

    def build_map_op(self, cnt: int) -> None:
        items = self.popn(cnt * 2)
        result = {}
        for i in range(0, len(items), 2):
            key = items[i]
            value = items[i + 1]
            result[key] = value
        self.push(result)

    def build_tuple_op(self, count: int) -> None:
        self.push(tuple(self.popn(count)))

    def map_add_op(self, i: int) -> None:
        val, key = self.popn(2)
        dict.__setitem__(self.data_stack[-i], val, key)

    def set_add_op(self, i: int) -> None:
        item = self.pop()
        set.add(self.data_stack[-i], item)

    def copy_op(self, i: int) -> None:
        assert i > 0
        self.data_stack.append(self.data_stack[-i])

    def call_intrinsic_1_op(self, i: int) -> None:
        if i == 5:
            self.push(+self.pop())
        elif i == 6:
            self.push(tuple(self.pop()))
        else:
            pass

    def is_op_op(self, invert: bool) -> None:
        right = self.pop()
        left = self.pop()
        result = (left is right)
        if invert:
            result = not result
        self.push(result)

    def contains_op_op(self, invert: bool) -> None:
        right = self.pop()
        left = self.pop()
        result = (left in right)
        if invert:
            result = not result
        self.push(result)

    def unary_negative_op(self, _: tp.Any) -> None:
        self.data_stack[-1] = -self.data_stack[-1]

    def unary_not_op(self, _: tp.Any) -> None:
        self.data_stack[-1] = not self.data_stack[-1]

    def load_attr_op(self, attr: str) -> None:
        obj = self.pop()
        val = getattr(obj, attr)
        self.push(val)

    def unary_invert_op(self, _: tp.Any) -> None:
        self.data_stack[-1] = ~self.data_stack[-1]

    def pop_jump_if_none_op(self, delta: int) -> None:
        if self.data_stack[-1] is None:
            self.jump(delta)
            self.pop()

    def jump_forward_op(self, delta: int) -> None:
        self.jump(delta)

    def store_attr_op(self, name: str) -> None:
        val, obj = self.popn(2)
        setattr(obj, name, val)

    def nop_op(self, arg: tp.Any) -> None:
        pass

    def delete_attr_op(self, name: str) -> None:
        obj = self.pop()
        delattr(obj, name)

    def delete_name_op(self, name: str) -> None:
        if name in self.locals:
            del self.locals[name]

    def delete_fast_op(self, name: str) -> None:
        del self.locals[name]

    def check_exc_match_op(self, _: tp.Any) -> None:
        exc_type = self.pop()
        exc = self.pop()
        result = self.exception_matches(exc, exc_type)
        self.push(result)

    def exception_matches(self, exc: Exception, exc_type: Exception) -> bool:
        if isinstance(exc_type, tuple):
            return any(self.exception_matches(exc, et) for et in exc_type)
        return False

    def load_fast_check_op(self, var_num: int) -> None:
        var_name = self.code.co_varnames[var_num]
        if var_name in self.locals:
            value = self.locals[var_name]
            self.push(value)
        else:
            raise UnboundLocalError(f"local variable '{var_name}' referenced before assignment")

    def load_build_class_op(self, _: tp.Any) -> None:
        self.push(__build_class__)

    def import_name_op(self, name: str) -> None:
        fromlist, level = self.popn(2)
        if not isinstance(fromlist, tuple):
            fromlist = tuple(fromlist) if fromlist else ()
        if not isinstance(level, int):
            level = 0
        try:
            module = __import__(name, self.globals, self.locals, fromlist, level)
        except ImportError as e:
            raise ImportError(f"Could not import module '{name}': {e}")
        self.push(module)

    def import_from_op(self, name: str) -> None:
        module = self.top()
        try:
            attr = getattr(module, name)
        except AttributeError as e:
            raise ImportError(f"Cannot import name '{name}' from '{module.__name__}' ({module.__file__})") from e
        self.push(attr)

    def import_star_op(self, _: tp.Any) -> None:
        module = self.pop()
        if hasattr(module, '__all__'):
            names = module.__all__
        else:
            names = [name for name in dir(module) if not name.startswith('_')]
        for name in names:
            self.locals[name] = getattr(module, name)

    def push_exc_info_op(self, _: tp.Any) -> None:
        exc_info = self.current_exception
        self.exception_stack.append(exc_info)

    def pop_except_op(self, _: tp.Any) -> None:
        if self.exception_stack:
            self.current_exception = self.exception_stack.pop()
        else:
            self.current_exception = None

    def raise_varargs_op(self, argc: int) -> None:
        if argc == 0:
            if self.last_exception is not None:
                raise self.last_exception
        elif argc == 1:
            exc = self.pop()
            if isinstance(exc, type) and issubclass(exc, BaseException):
                exc = exc()
            raise exc
        elif argc == 2:
            cause = self.pop()
            exc = self.pop()
            if isinstance(exc, type) and issubclass(exc, BaseException):
                exc = exc()
                cause = cause()
            raise exc from cause


class VirtualMachine:
    def run(self, code_obj: types.CodeType) -> None:
        """
        :param code_obj: code for interpreting
        """
        globals_context: dict[str, tp.Any] = {}
        frame = Frame(code_obj, builtins.globals()['__builtins__'], globals_context, globals_context)
        return frame.run()
