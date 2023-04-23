import functools
import re
import fire
import traceback
import os
from inspect import getmembers
import importlib

class Environment:
    def __init__(self, parent=None):
        self.parent = parent
        self.bindings = {}

    def extend(self, names, values):
        new_env = Environment(parent=self)
        for name, value in zip(names, values):
            new_env.define(name, value)
        return new_env

    def define(self, name, value, override=True):
        if override:
            self.bindings[name] = value
        else:
            if name not in self.bindings:
                self.bindings[name] = value

    def set(self, name, value):
        if name in self.bindings:
            self.bindings[name] = value
        elif self.parent is not None:
            self.parent.set(name, value)
        else:
            raise NameError(name)

    def get(self, name):
        if name in self.bindings:
            return self.bindings[name]
        elif self.parent is not None:
            return self.parent.get(name)
        else:
            raise NameError(name)
        
    def import_module(self, module_name, prefix=None, no_prefix=False):
        if not prefix:
            prefix = module_name
            print(f'import {module_name}')
        else:
            print(f'import {module_name} as {prefix}')
        module = importlib.import_module(module_name)
        self.define(prefix, module, override=False)
        
        for f in getmembers(module):
            if not no_prefix:
                self.define(prefix+'-'+f[0], f[1], override=False)
            else:
                self.define(f[0], f[1], override=False)


class LispInterpreter:
    def __init__(self, use_default_ios=True, use_python_builtins=True):
        self.global_env = Environment()
        self.add_globals()
        if use_default_ios:
            self.add_default_ios()
        if use_python_builtins:
            self.add_python_builtins()

    def add_globals(self):
        self.global_env.define('car', lambda x: x[0])
        self.global_env.define('cdr', lambda x: x[1:])
        self.global_env.define('cons', lambda x, y: [x] + y)
        self.global_env.define('eq?', lambda x, y: x == y)
        self.global_env.define('length', lambda x: len(x))
        self.global_env.define('+', lambda *args: sum(args))
        self.global_env.define('-', lambda *args: args[0] - sum(args[1:]))
        self.global_env.define('*', lambda *args: functools.reduce(lambda x, y: x * y, args))
        self.global_env.define('/', lambda *args: args[0] / functools.reduce(lambda x, y: x * y, args[1:]))
        self.global_env.define('import', self.global_env.import_module)
    
    def add_default_ios(self):
        def display(*args, end='\n'):
            print(*args, end=end)

        def newline():
            print()

        def clear():
            os.system('clear')
        self.global_env.define('display', display)
        self.global_env.define('newline', newline)
        self.global_env.define('read', input)
        self.global_env.define('clear', clear)

    def add_python_builtins(self):
        self.global_env.import_module('builtins', no_prefix=True)
        self.global_env.define('int', lambda *args: int(float(args[0])))

        # Datastructures manipulation
        def is_in(element, iterable):
            return element in iterable

        class CallableDict(dict):
            def __call__(self, key):
                return self[key]
        self.global_env.define('dict', CallableDict)
        self.global_env.define('in', is_in)

    def eval(self, expression, env=None):
        if env is None:
            env = self.global_env

        if isinstance(expression, int) or isinstance(expression, float):
            return expression
        elif isinstance(expression, str):
            return env.get(expression)
        elif not isinstance(expression, list):
            raise TypeError('Invalid expression')

        operator = expression[0]
        operands = expression[1:]

        if operator == 'quote':
            return operands[0]
        elif operator == 'if':
            test, true_expr, false_expr = operands[0], operands[1], operands[2]
            return self.eval(true_expr, env) if self.eval(test, env) else self.eval(false_expr, env)
        elif operator == 'lambda':
            parameters, body = operands[0], operands[1]
            return lambda *args: self.eval(body, Environment(parent=env).extend(parameters, args))
        elif operator == 'define':
            if isinstance(operands[0], list):
                # Function definition
                name, parameters, body = operands[0][0], operands[0][1:], operands[1]
                env.define(name, self.eval(['lambda', parameters, body], env))
            else:
                # Variable definition
                name, value = operands[0], self.eval(operands[1], env)
                env.define(name, value)
            return None
        elif operator == 'set!':
            name, value = operands[0], self.eval(operands[1], env)
            env.set(name, value)
            return None
        else:
            function = self.eval(operator, env)
            args = [self.eval(operand, env) for operand in operands]
            return function(*args)

    def repl(self):
        while True:
            try:
                input_string = input('> ')
                expression = LispParser.parse(input_string)
                if expression != None:
                    result = self.eval(expression)
                    print(result)
            except (SyntaxError, NameError, TypeError, KeyError) as error:
                print('Error:', error, traceback.format_exc())


class LispParser:
    @staticmethod
    def parse(input_string):
        tokens = LispParser.tokenize(input_string)
        return LispParser.parse_tokens(tokens)
    @staticmethod
    def tokenize(input_string):
        # Add spaces around parentheses
        input_string = re.sub(r'\(', ' ( ', input_string)
        input_string = re.sub(r'\)', ' ) ', input_string)
        input_string = input_string.replace("'", " ' ")  # add this line
        # Split into tokens
        return input_string.split()
    @staticmethod
    def parse_tokens(tokens):
        if not tokens:
            # return ''
            raise SyntaxError('Unexpected end of input')

        token = tokens.pop(0)
        if token == '(':
            expression = []
            while tokens[0] != ')':
                expression.append(LispParser.parse_tokens(tokens))
            tokens.pop(0)  # remove the ')'
            if expression[0] == 'lambda':
                return [expression[0], [LispParser.parse_tokens([arg]) for arg in expression[1]], expression[2]]
            else:
                return expression
        elif token == ')':
            raise SyntaxError('Unexpected )')
        elif token and token[0] == '"':
            while not token.endswith('"'):
                if not tokens:
                    raise SyntaxError('Unexpected end of input')
                token += ' ' + tokens.pop(0)
            return ['quote', token[1:-1]]
        elif token and token[0] == "'":
            return ['quote', LispParser.parse_tokens(tokens)]
        elif token and token[0] == ";":
            # consume the rest of the tokens until the end of the line
            while tokens and not tokens[0].startswith('\n'):
                tokens.pop(0)
            # return None to indicate that this is a comment
            return None
        else:
            try:
                return int(token)
            except ValueError:
                try:
                    return float(token)
                except ValueError:
                    return token


def main(file_path=None, keep_repl=False, use_default_ios=True, use_python_builtins=True):
    interpreter = LispInterpreter(use_default_ios, use_python_builtins)
    """Runs TinyPyLisp Repl.

    Args:
        file_path (FilePath, optional): Path to source code. Defaults to None.
        keep_repl (bool, optional): Keeps repl after executing source code. Defaults to False.
        use_default_ios (bool, optional): Implemented a few default io functions. Defaults to True.
        use_python_builtins (bool, optional): Load python builtin functions. Defaults to True.
    """
    if not file_path:
        interpreter.repl()
    else:
        f = open(file_path, 'r')
        source_code = f.readlines()
        for input_string in source_code:
            if len(input_string.strip()):
                try:
                    expression = LispParser.parse(input_string)
                    if expression == None:
                        continue
                    result = interpreter.eval(expression)
                    if result != None:
                        print(result)
                except (SyntaxError, NameError, TypeError, KeyError) as error:
                    print('Error:', error)
                    # break
        if keep_repl:
            interpreter.repl()

fire.Fire(main)