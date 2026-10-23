"""
jsc.py -- a tiny compiler from a small JavaScript subset to the A4 bytecode
=============================================================================
Front end for vm_ic_model.py: tokenizer -> recursive-descent parser that
emits bytecode directly (single pass, jump targets back-patched).

Supported (enough to write real, Node-runnable test programs):
  let / const / var  x = expr;         x = expr;  x += / -= / *= expr;  x++;  x--;
  if (...) ... else ...                while (...) ...      for (init; cond; update) ...
  console.log(expr);                   { blocks }           // and /* */ comments
  integers, + - * / %, unary - and !, < > <= >= == != === !==
  object literals  { x: 1, y: { z: 2 } }   and property reads  p.x  p.y.z
  arrays of constants  let a = [ {...}, {...} ];   a[i]   a.length

Not supported (compile error, or differs from JS -- keep test programs inside the subset):
  strings, functions, true/false, property/array writes, break/continue.
  '/' is integer division and '%' floors like Python, so use non-negative,
  evenly dividing operands if you compare against Node. Comparisons yield 1/0,
  not true/false, so print numbers, not raw comparisons.

The VM's ISA only has LT, so >, <=, >=, ==, != and % are lowered to
LT/ADD/SUB/MUL/DIV sequences using compiler-generated temporary locals.
Object and array literals are built at compile time into the VM's object
table (LOADOBJ indexes it) -- fine because the subset has no mutation.
"""

import re

import vm_ic_model as m


class CompileError(Exception):
    pass


TOKEN_RE = re.compile(r"""
    (?P<ws>\s+|//[^\n]*|/\*.*?\*/)
  | (?P<num>\d+)
  | (?P<id>[A-Za-z_$][A-Za-z0-9_$]*)
  | (?P<op>===|!==|==|!=|<=|>=|\+\+|--|\+=|-=|\*=|[{}()\[\];,.:=+\-*/%<>!])
""", re.S | re.X)

DECL = ("let", "const", "var")
CMP = ("<", ">", "<=", ">=", "==", "!=", "===", "!==")


def tokenize(src):
    toks, pos, line = [], 0, 1
    while pos < len(src):
        mt = TOKEN_RE.match(src, pos)
        if not mt:
            raise CompileError(f"line {line}: unexpected character {src[pos]!r}")
        if mt.lastgroup != "ws":
            toks.append((mt.lastgroup, mt.group(), line))
        line += mt.group().count("\n")
        pos = mt.end()
    toks.append(("eof", "", line))
    return toks


class Compiler:
    def __init__(self, src):
        self.src_lines = src.splitlines()
        self.toks = tokenize(src)
        self.i = 0
        self.code = []
        self.slots = {}      # variable name (or $tN temp) -> local slot
        self.arrays = {}     # array name -> (base index in objects, length)
        self.objects = []    # the VM's object table
        self.n_temps = 0
        self.sites = {}      # GETFIELD pc -> (source line, property name)

    # ---------- token helpers ----------
    def peek(self):
        return self.toks[self.i]

    def at(self, text):
        return self.peek()[1] == text

    def next(self):
        t = self.toks[self.i]
        self.i += 1
        return t

    def accept(self, text):
        if self.at(text):
            self.i += 1
            return True
        return False

    def expect(self, text):
        t = self.next()
        if t[1] != text:
            raise CompileError(f"line {t[2]}: expected {text!r}, got {t[1] or 'end of file'!r}")
        return t

    def ident(self):
        t = self.next()
        if t[0] != "id":
            raise CompileError(f"line {t[2]}: expected a name, got {t[1] or 'end of file'!r}")
        return t[1]

    # ---------- emit helpers ----------
    def emit(self, op, arg=None):
        self.code.append([op, arg])
        return len(self.code) - 1

    def patch(self, pc):
        self.code[pc][1] = len(self.code)

    def slot(self, name, line, declare=False):
        if name in self.arrays:
            raise CompileError(f"line {line}: array '{name}' can only be used as {name}[i] or {name}.length")
        if name not in self.slots:
            if not declare:
                raise CompileError(f"line {line}: '{name}' is not defined")
            self.slots[name] = len(self.slots)
        return self.slots[name]

    def temp(self):
        name = f"$t{self.n_temps}"
        self.n_temps += 1
        self.slots[name] = len(self.slots)
        return self.slots[name]

    # ---------- statements ----------
    def compile(self):
        while self.peek()[0] != "eof":
            self.statement()
        self.emit("HALT")
        return [tuple(c) for c in self.code]

    def statement(self):
        kind, text, line = self.peek()
        if self.accept("{"):
            while not self.accept("}"):
                if self.peek()[0] == "eof":
                    raise CompileError(f"line {line}: unclosed '{{'")
                self.statement()
        elif text in DECL:
            self.next()
            self.declaration()
            self.accept(";")
        elif self.accept("while"):
            self.expect("(")
            head = len(self.code)
            self.expr()
            self.expect(")")
            jz = self.emit("JZ")
            self.statement()
            self.emit("JMP", head)
            self.patch(jz)
        elif self.accept("for"):
            self.for_loop()
        elif self.accept("if"):
            self.expect("(")
            self.expr()
            self.expect(")")
            jz = self.emit("JZ")
            self.statement()
            if self.accept("else"):
                jmp = self.emit("JMP")
                self.patch(jz)
                self.statement()
                self.patch(jmp)
            else:
                self.patch(jz)
        elif text == "console":
            self.next()
            self.expect(".")
            self.expect("log")
            self.expect("(")
            self.expr()
            self.expect(")")
            self.emit("PRINT")
            self.emit("POP")
            self.accept(";")
        elif kind == "id":
            self.assignment()
            self.accept(";")
        else:
            raise CompileError(f"line {line}: unexpected {text or 'end of file'!r}")

    def declaration(self):
        line = self.peek()[2]
        name = self.ident()
        self.expect("=")
        if self.at("["):
            self.arrays[name] = self.array_literal()
            return
        s = self.slot(name, line, declare=True)
        self.expr()
        self.emit("STORE", s)

    def assignment(self):
        line = self.peek()[2]
        name = self.ident()
        s = self.slot(name, line)
        t = self.next()
        if t[1] in ("++", "--"):
            self.emit("LOAD", s)
            self.emit("PUSH", 1)
            self.emit("ADD" if t[1] == "++" else "SUB")
        elif t[1] == "=":
            self.expr()
        elif t[1] in ("+=", "-=", "*="):
            self.emit("LOAD", s)
            self.expr()
            self.emit({"+=": "ADD", "-=": "SUB", "*=": "MUL"}[t[1]])
        else:
            raise CompileError(f"line {t[2]}: expected an assignment after '{name}'")
        self.emit("STORE", s)

    def for_loop(self):
        self.expect("(")
        if self.peek()[1] in DECL:
            self.next()
            self.declaration()
        elif not self.at(";"):
            self.assignment()
        self.expect(";")
        head = len(self.code)
        self.expr()
        self.expect(";")
        jz = self.emit("JZ")
        # the update runs after the body, so skip its tokens now and compile them later
        upd_start, depth = self.i, 0
        while not (self.at(")") and depth == 0):
            if self.peek()[0] == "eof":
                raise CompileError(f"line {self.peek()[2]}: unclosed 'for ('")
            depth += {"(": 1, ")": -1}.get(self.next()[1], 0)
        upd_end = self.i
        self.expect(")")
        self.statement()
        if upd_end > upd_start:
            resume, self.i = self.i, upd_start
            self.assignment()
            if self.i != upd_end:
                raise CompileError(f"line {self.peek()[2]}: unsupported for-loop update")
            self.i = resume
        self.emit("JMP", head)
        self.patch(jz)

    # ---------- expressions ----------
    def expr(self):
        self.additive()
        if self.peek()[1] in CMP:
            op = self.next()[1]
            self.additive()
            self.compare(op)

    def compare(self, op):
        if op == "<":
            self.emit("LT")
            return
        b, a = self.temp(), self.temp()
        self.emit("STORE", b)
        self.emit("STORE", a)

        def lt(x, y):
            self.emit("LOAD", x)
            self.emit("LOAD", y)
            self.emit("LT")

        if op == ">":
            lt(b, a)
        elif op in (">=", "<="):          # not (a < b)  /  not (b < a)
            self.emit("PUSH", 1)
            lt(a, b) if op == ">=" else lt(b, a)
            self.emit("SUB")
        else:                              # equal  <=>  neither a < b nor b < a
            eq = op in ("==", "===")
            if eq:
                self.emit("PUSH", 1)
            lt(a, b)
            lt(b, a)
            self.emit("ADD")
            if eq:
                self.emit("SUB")

    def additive(self):
        self.term()
        while self.peek()[1] in ("+", "-"):
            op = self.next()[1]
            self.term()
            self.emit("ADD" if op == "+" else "SUB")

    def term(self):
        self.unary()
        while self.peek()[1] in ("*", "/", "%"):
            op = self.next()[1]
            self.unary()
            if op == "*":
                self.emit("MUL")
            elif op == "/":
                self.emit("DIV")
            else:                          # a % b  ==  a - (a / b) * b
                b, a = self.temp(), self.temp()
                self.emit("STORE", b)
                self.emit("STORE", a)
                for op_, arg in [("LOAD", a), ("LOAD", a), ("LOAD", b), ("DIV", None),
                                 ("LOAD", b), ("MUL", None), ("SUB", None)]:
                    self.emit(op_, arg)

    def unary(self):
        if self.accept("-"):
            self.emit("PUSH", 0)
            self.unary()
            self.emit("SUB")
        elif self.accept("!"):
            self.unary()
            self.emit("PUSH", 0)
            self.compare("==")
        else:
            self.postfix()

    def postfix(self):
        kind, text, line = self.peek()
        if kind == "id" and text in self.arrays:
            self.next()
            base, length = self.arrays[text]
            if self.accept("."):
                if self.ident() != "length":
                    raise CompileError(f"line {line}: arrays only support .length and [i]")
                self.emit("PUSH", length)
                return
            self.expect("[")
            self.emit("PUSH", base)
            self.expr()
            self.expect("]")
            self.emit("ADD")
            self.emit("LOADOBJ")
        else:
            self.primary()
        while self.at("."):
            line = self.next()[2]
            prop = self.ident()
            self.sites[self.emit("GETFIELD", prop)] = (line, prop)

    def primary(self):
        kind, text, line = self.next()
        if kind == "num":
            self.emit("PUSH", int(text))
        elif kind == "id":
            self.emit("LOAD", self.slot(text, line))
        elif text == "(":
            self.expr()
            self.expect(")")
        elif text == "{":
            self.objects.append(self.object_body())
            self.emit("PUSH", len(self.objects) - 1)
            self.emit("LOADOBJ")
        else:
            raise CompileError(f"line {line}: unexpected {text or 'end of file'!r} in expression")

    # ---------- compile-time literals ----------
    def const_value(self):
        neg = self.accept("-")
        kind, text, line = self.next()
        if kind == "num":
            return -int(text) if neg else int(text)
        if text == "{" and not neg:
            return self.object_body()
        raise CompileError(f"line {line}: literal values must be integers or object literals")

    def object_body(self):          # called just after '{'
        fields = {}
        while not self.accept("}"):
            key = self.ident()
            self.expect(":")
            fields[key] = self.const_value()
            if not self.accept(","):
                self.expect("}")
                break
        return m.make_object(fields)

    def array_literal(self):
        self.expect("[")
        elems = []
        while not self.accept("]"):
            elems.append(self.const_value())
            if not self.accept(","):
                self.expect("]")
                break
        base = len(self.objects)
        self.objects.extend(elems)
        return base, len(elems)


def compile_js(src):
    """Returns (bytecode, compiler); the compiler holds slots, objects and GETFIELD sites."""
    c = Compiler(src)
    code = c.compile()
    return code, c
