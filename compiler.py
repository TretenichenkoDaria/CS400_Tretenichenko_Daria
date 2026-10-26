import sys
from llvmlite import ir
import llvmlite.binding as llvm

i32 = ir.IntType(32)
i64 = ir.IntType(64)
i1 = ir.IntType(1)
i8 = ir.IntType(8)

class token:
    def __init__(self, k, t, l, c): self.kind, self.text, self.line, self.col = k, t, l, c

def lex(data: bytes):
    lines, tokens = [], []
    state, start, line, col, i = "start", 0, 1, 1, 0
    start_line, start_col = 1, 1
    kws = {
        "i32": "typename", "i64": "typename", "bool": "typename",
        "mut": "specifier", "exit": "keyword",
        "true": "boolean", "false": "boolean",
        "if": "keyword", "else": "keyword", "while": "keyword",
        "struct": "keyword", "fn": "keyword"
    }

    while i <= len(data):
        b = data[i] if i < len(data) else None
        if state == "start":
            if b is None:
                break
            if b in (32, 9): pass
            elif b == 35: state = "comment"
            elif 65 <= b <= 90 or 97 <= b <= 122 or b == 95: state, start = "ident", i
            elif 48 <= b <= 57: state, start = "number", i
            elif b == 34:
                state, start, start_line, start_col = "string", i, line, col
            elif b == 10:
                if tokens: lines.append(tokens)
                tokens, line, col = [], line + 1, 0
            elif b in (123, 125):
                tokens.append(token("brace", chr(b), line, col))
            elif b in (40, 41):
                tokens.append(token("paren", chr(b), line, col))
            elif b in (91, 93):
                tokens.append(token("bracket", chr(b), line, col))
            elif b == 44:
                tokens.append(token("comma", ",", line, col))
            elif b == 46:
                tokens.append(token("dot", ".", line, col))
            elif b == 45:
                state = "minus"
            elif b in (43, 42): tokens.append(token("operator", chr(b), line, col))
            elif b == 61: state = "eq1"
            elif b == 33: state = "neq1"
            elif b == 58: state = "assign"
            else:
                sys.stderr.write(f"compilation error: line {line}:{col}: bad byte '{chr(b)}'\n")
                sys.exit(1)
        elif state == "string":
            if b == 10 or b is None:
                sys.stderr.write(f"compilation error: line {start_line}:{start_col}: string literal not closed on its line\n")
                sys.exit(1)
            elif b == 34:
                s_val = data[start + 1:i].decode("utf-8", errors="replace")
                tokens.append(token("string", s_val, start_line, start_col))
                state = "start"
        elif state == "comment":
            if b is None or b == 10:
                state = "start"
                continue
        elif state == "minus":
            if b == 62:
                tokens.append(token("arrow", "->", line, col - 1)); state = "start"
            else:
                tokens.append(token("operator", "-", line, col - 1))
                state = "start"; continue
        elif state == "eq1":
            if b == 61:
                tokens.append(token("operator", "==", line, col - 1)); state = "start"
            else:
                sys.stderr.write(f"compilation error: line {line}:{col - 1}: expected '=='\n")
                sys.exit(1)
        elif state == "neq1":
            if b == 61:
                tokens.append(token("operator", "!=", line, col - 1)); state = "start"
            else:
                tokens.append(token("operator", "!", line, col - 1))
                state = "start"; continue
        elif state == "assign":
            if b == 61:
                tokens.append(token("operator", ":=", line, col - 1)); state = "start"
            else:
                sys.stderr.write(f"compilation error: line {line}:{col - 1}: expected '='\n")
                sys.exit(1)
        elif state == "ident":
            if b is None or not (65 <= b <= 90 or 97 <= b <= 122 or b == 95 or 48 <= b <= 57):
                w = data[start:i].decode("ascii")
                tokens.append(token(kws.get(w, "identifier"), w, line, col - (i - start)))
                state = "start"; continue
        elif state == "number":
            if b is not None and (65 <= b <= 90 or 97 <= b <= 122 or b == 95):
                sys.stderr.write(f"compilation error: line {line}:{col}: letter in number\n")
                sys.exit(1)
            if b is None or not (48 <= b <= 57):
                w = data[start:i].decode("ascii")
                tokens.append(token("constant", w, line, col - (i - start)))
                state = "start"; continue
        i += 1; col += 1
    if state == "string":
        sys.stderr.write(f"compilation error: line {start_line}:{start_col}: string literal not closed on its line\n")
        sys.exit(1)
    if tokens: lines.append(tokens)
    return lines


class programnode:
    def __init__(self, structs, funcs, stmts, e):
        self.structs, self.funcs, self.stmts, self.exit_node = structs, funcs, stmts, e
    def dump(self, ind=""):
        print(ind + "program")
        for s in self.structs: s.dump(ind + "  ")
        for f in self.funcs: f.dump(ind + "  ")
        for s in self.stmts: s.dump(ind + "  ")
        self.exit_node.dump(ind + "  ")

class structnode:
    def __init__(self, l, c, name, fields, member_funcs):
        self.line, self.col, self.name, self.fields, self.member_funcs = l, c, name, fields, member_funcs
    def dump(self, ind=""):
        print(ind + f"struct {self.name}")
        for f in self.fields: f.dump(ind + "  ")
        for mf in self.member_funcs: mf.dump(ind + "  ")

class fielddeclnode:
    def __init__(self, l, c, type_name, mut, name):
        self.line, self.col, self.type_name, self.mut, self.name = l, c, type_name, mut, name
    def dump(self, ind=""):
        print(ind + f"field {self.name} {self.type_name} {'mut' if self.mut else 'const'}")

class memberfnnode:
    def __init__(self, l, c, name, params, ret_type, body):
        self.line, self.col, self.name, self.params, self.ret_type, self.body = l, c, name, params, ret_type, body
    def dump(self, ind=""):
        print(ind + f"memberfn {self.name} -> {self.ret_type}")
        for p_type, p_name, _, _ in self.params:
            print(ind + f"  param {p_name} {p_type}")
        self.body.dump(ind + "  ")

class funcnode:
    def __init__(self, l, c, name, params, ret_type, body):
        self.line, self.col, self.name, self.params, self.ret_type, self.body = l, c, name, params, ret_type, body
    def dump(self, ind=""):
        p_str = ", ".join(f"{p[0]} {p[1]}" for p in self.params)
        print(ind + f"fn {self.name}({p_str}) -> {self.ret_type}")
        self.body.dump(ind + "  ")

class declnode:
    def __init__(self, l, c, t, n, m, inits): 
        self.line, self.col, self.type_name, self.name, self.mut, self.inits = l, c, t, n, m, inits
        self.type = None
    def dump(self, ind=""):
        print(ind + f"decl {self.name} {self.type_name} {'mut' if self.mut else 'const'}")
        for init in self.inits:
            init.dump(ind + "  ")

class assignnode:
    def __init__(self, l, c, target, v): 
        self.line, self.col, self.target, self.value = l, c, target, v
    def dump(self, ind=""):
        t_name = ".".join(self.target)
        print(ind + f"assign {t_name}"); self.value.dump(ind + "  ")

class ifnode:
    def __init__(self, l, c, cond, tb, eb): 
        self.line, self.col, self.cond, self.then_block, self.else_block = l, c, cond, tb, eb
    def dump(self, ind=""):
        print(ind + "if")
        self.cond.dump(ind + "  ")
        self.then_block.dump(ind + "  ")
        if self.else_block: self.else_block.dump(ind + "  ")

class whilenode:
    def __init__(self, l, c, cond, body): 
        self.line, self.col, self.cond, self.body = l, c, cond, body
    def dump(self, ind=""):
        print(ind + "while")
        self.cond.dump(ind + "  ")
        self.body.dump(ind + "  ")

class lambdanode:
    def __init__(self, l, c, name, captures, params, ret_type, body):
        self.line, self.col, self.name = l, c, name
        self.captures = captures
        self.params = params
        self.ret_type = ret_type
        self.body = body
        self.rewritten_struct = None
        self.rewritten_decl = None
        self.type = None

    def dump(self, ind=""):
        if hasattr(self, "rewritten_struct") and self.rewritten_struct is not None:
            print(ind + f"lambda {self.name} -> {self.ret_type}")
            self.rewritten_struct.dump(ind + "  ")
            self.rewritten_decl.dump(ind + "  ")
        else:
            print(ind + f"lambda {self.name} -> {self.ret_type}")
            for c_name, _, _ in self.captures:
                print(ind + f"  capture {c_name}")
            for p_type, p_name, _, _ in self.params:
                print(ind + f"  param {p_name} {p_type}")
            self.body.dump(ind + "  ")

class blocknode:
    def __init__(self, l, c, stmts, ex): 
        self.line, self.col, self.stmts, self.ex = l, c, stmts, ex
    def dump(self, ind=""):
        print(ind + "block")
        for s in self.stmts: s.dump(ind + "  ")
        if self.ex: self.ex.dump(ind + "  ")

class printnode:
    def __init__(self, l, c, arg):
        self.line, self.col, self.arg = l, c, arg
    def dump(self, ind=""):
        print(ind + "print")
        self.arg.dump(ind + "  ")

class stringnode:
    def __init__(self, l, c, val):
        self.line, self.col, self.value = l, c, val
        self.type = "string"
    def dump(self, ind=""):
        print(ind + f"string \"{self.value}\"")

class readnode:
    def __init__(self, l, c):
        self.line, self.col = l, c
        self.type = "i32"
    def dump(self, ind=""):
        print(ind + "read")

class notnode:
    def __init__(self, l, c, val): 
        self.line, self.col, self.val = l, c, val
    def dump(self, ind=""):
        print(ind + "not")
        self.val.dump(ind + "  ")

class exitnode:
    def __init__(self, l, c, v): self.line, self.col, self.value = l, c, v
    def dump(self, ind=""):
        print(ind + "exit"); self.value.dump(ind + "  ")

class binopnode:
    def __init__(self, l, c, o, left, right): 
        self.line, self.col, self.op, self.left, self.right = l, c, o, left, right
        self.type = None
    def dump(self, ind=""):
        print(ind + f"binop {self.op}"); self.left.dump(ind + "  "); self.right.dump(ind + "  ")

class varnode:
    def __init__(self, l, c, n): 
        self.line, self.col, self.name = l, c, n
        self.type, self.decl = None, None
    def dump(self, ind=""): print(ind + f"var {self.name}")

class fieldaccessnode:
    def __init__(self, l, c, chain):
        self.line, self.col, self.chain = l, c, chain
        self.type = None
        self.field_indices = []
    def dump(self, ind=""): print(ind + f"field {'.'.join(self.chain)}")

class callnode:
    def __init__(self, l, c, name, args):
        self.line, self.col, self.name, self.args = l, c, name, args
        self.type = None
    def dump(self, ind=""):
        print(ind + f"call {self.name}")
        for a in self.args: a.dump(ind + "  ")

class membercallnode:
    def __init__(self, l, c, target, name, args):
        self.line, self.col, self.target, self.name, self.args = l, c, target, name, args
        self.type = None
    def dump(self, ind=""):
        print(ind + f"membercall {self.name}")
        self.target.dump(ind + "  ")
        for a in self.args: a.dump(ind + "  ")

class callablecallnode(membercallnode):
    def __init__(self, l, c, target, args, callable_name=None):
        super().__init__(l, c, target, "call", args)
        self.callable_name = callable_name
        self.is_callable_call = True
    def dump(self, ind=""):
        name = self.callable_name
        if not name:
            if isinstance(self.target, varnode):
                name = self.target.name
            elif isinstance(self.target, fieldaccessnode):
                name = ".".join(self.target.chain)
            else:
                name = "call"
        print(ind + f"callablecall {name}")
        for a in self.args: a.dump(ind + "  ")

class constnode:
    def __init__(self, l, c, v): 
        self.line, self.col, self.value = l, c, v
        self.type = None
    def dump(self, ind=""): print(ind + f"const {self.value}")

class boolnode:
    def __init__(self, l, c, v): 
        self.line, self.col, self.value = l, c, v
        self.type = "bool"
    def dump(self, ind=""): print(ind + f"bool {self.value}")


class parser:
    def __init__(self, lines): 
        self.lines = [l for l in lines if l]
        self.lpos, self.tpos = 0, 0
        self.ll, self.lc = 0, 0
        
    def peek(self):
        if self.lpos < len(self.lines) and self.tpos < len(self.lines[self.lpos]):
            return self.lines[self.lpos][self.tpos]
        return None
        
    def eat(self):
        t = self.peek()
        if t:
            self.ll, self.lc = t.line, t.col
            self.tpos += 1
        return t
        
    def eol(self):
        return self.lpos >= len(self.lines) or self.tpos >= len(self.lines[self.lpos])
        
    def next_line(self):
        if self.tpos > 0:
            self.lpos += 1
            self.tpos = 0
            
    def check_eol(self):
        if not self.eol():
            t = self.peek()
            sys.stderr.write(f"compilation error: line {t.line}:{t.col}: junk at end\n")
            sys.exit(1)
        self.next_line()
        
    def exp(self, k, m):
        t = self.peek()
        if not t or (k == "identifier" and t.kind != "identifier") or (k != "identifier" and (t.kind != k and t.text != k)):
            l = t.line if t else self.ll
            c = t.col if t else self.lc + 1
            sys.stderr.write(f"compilation error: line {l}:{c}: expected {m}\n")
            sys.exit(1)
        return self.eat()

    def check_not_reserved(self, t):
        if t and t.text in ("read", "print"):
            sys.stderr.write(f"compilation error: line {t.line}:{t.col}: '{t.text}' is a reserved keyword\n")
            sys.exit(1)

    def is_lambda_start(self):
        cur_line = self.lines[self.lpos]
        p = self.tpos
        if p + 3 < len(cur_line):
            if cur_line[p].text == "fn" and cur_line[p + 1].kind == "identifier" and cur_line[p + 2].text == ":=" and cur_line[p + 3].text == "[":
                return True
        return False

    def parse_program(self):
        structs, funcs, stmts, ex = [], [], [], None
        phase = "struct"

        while self.lpos < len(self.lines):
            t = self.peek()
            if ex:
                sys.stderr.write(f"compilation error: line {t.line}:{t.col}: unreachable code\n")
                sys.exit(1)

            if t and t.text == "struct":
                if phase not in ("struct",):
                    sys.stderr.write(f"compilation error: line {t.line}:{t.col}: struct after a function or statement\n")
                    sys.exit(1)
                structs.append(self.parse_struct())
            elif t and t.text == "fn":
                if self.is_lambda_start():
                    phase = "stmt"
                    stmts.append(self.parse_lambda())
                else:
                    if phase not in ("struct", "fn"):
                        sys.stderr.write(f"compilation error: line {t.line}:{t.col}: function after a statement\n")
                        sys.exit(1)
                    phase = "fn"
                    funcs.append(self.parse_fn())
            elif t and t.kind == "keyword" and t.text == "exit":
                phase = "exit"
                ex = self.parse_exit()
                self.check_eol()
            else:
                phase = "stmt"
                stmts.append(self.parse_statement())

        if not ex:
            l = self.ll if self.ll else 0
            c = self.lc if self.lc else 0
            sys.stderr.write(f"compilation error: line {l}:{c}: no exit\n")
            sys.exit(1)
        return programnode(structs, funcs, stmts, ex)

    def parse_struct(self):
        st = self.eat()
        name_t = self.exp("identifier", "struct name")
        self.check_not_reserved(name_t)
        self.check_eol()

        t = self.peek()
        if not t or t.text != "{":
            l = t.line if t else self.ll
            c = t.col if t else self.lc + 1
            sys.stderr.write(f"compilation error: line {l}:{c}: expected '{{' on its own line\n")
            sys.exit(1)
        lb = self.eat()
        self.check_eol()

        fields = []
        member_funcs = []
        phase = "field"

        while self.lpos < len(self.lines):
            t = self.peek()
            if t and t.text == "}":
                break
            if t and t.text == "fn":
                if not fields:
                    sys.stderr.write(f"compilation error: line {t.line}:{t.col}: member function before the first field\n")
                    sys.exit(1)
                phase = "fn"
                member_funcs.append(self.parse_member_fn())
            else:
                if phase == "fn":
                    sys.stderr.write(f"compilation error: line {t.line}:{t.col}: field after a member function\n")
                    sys.exit(1)
                f_type = self.parse_type()
                mut = False
                if self.peek() and self.peek().text == "mut":
                    mut = True
                    self.eat()
                f_name = self.exp("identifier", "field name")
                self.check_not_reserved(f_name)
                self.check_eol()
                fields.append(fielddeclnode(f_name.line, f_name.col, f_type, mut, f_name.text))

        t = self.peek()
        if not t or t.text != "}":
            sys.stderr.write(f"compilation error: line {lb.line}:{lb.col}: '{{' is never closed\n")
            sys.exit(1)
        self.eat()
        self.check_eol()

        if not fields:
            sys.stderr.write(f"compilation error: line {st.line}:{st.col}: struct has no fields\n")
            sys.exit(1)

        return structnode(st.line, st.col, name_t.text, fields, member_funcs)

    def parse_member_fn(self):
        fn_kw = self.eat()
        name_t = self.exp("identifier", "function name")
        self.check_not_reserved(name_t)
        self.exp(":=", "':='")
        if self.peek() and self.peek().text == "[":
            t = self.peek()
            sys.stderr.write(f"compilation error: line {t.line}:{t.col}: member function cannot have captures\n")
            sys.exit(1)
        self.exp("(", "'('")

        params = []
        if self.peek() and self.peek().text != ")":
            p_type = self.parse_type()
            p_name = self.exp("identifier", "parameter name")
            self.check_not_reserved(p_name)
            params.append((p_type, p_name.text, p_name.line, p_name.col))
            while self.peek() and self.peek().text == ",":
                self.eat()
                p_type = self.parse_type()
                p_name = self.exp("identifier", "parameter name")
                self.check_not_reserved(p_name)
                params.append((p_type, p_name.text, p_name.line, p_name.col))

        self.exp(")", "')'")
        self.exp("->", "'->'")
        ret_type = self.parse_type()
        self.check_eol()

        t = self.peek()
        if not t or t.text != "{":
            l = t.line if t else self.ll
            c = t.col if t else self.lc + 1
            sys.stderr.write(f"compilation error: line {l}:{c}: expected '{{' on its own line after fn header\n")
            sys.exit(1)

        body = self.parse_block()
        return memberfnnode(fn_kw.line, fn_kw.col, name_t.text, params, ret_type, body)

    def parse_fn(self):
        fn_kw = self.eat()
        name_t = self.exp("identifier", "function name")
        self.check_not_reserved(name_t)
        self.exp(":=", "':='")
        self.exp("(", "'('")

        params = []
        if self.peek() and self.peek().text != ")":
            p_type = self.parse_type()
            p_name = self.exp("identifier", "parameter name")
            self.check_not_reserved(p_name)
            params.append((p_type, p_name.text, p_name.line, p_name.col))
            while self.peek() and self.peek().text == ",":
                self.eat()
                p_type = self.parse_type()
                p_name = self.exp("identifier", "parameter name")
                self.check_not_reserved(p_name)
                params.append((p_type, p_name.text, p_name.line, p_name.col))

        self.exp(")", "')'")
        self.exp("->", "'->'")
        ret_type = self.parse_type()
        self.check_eol()

        t = self.peek()
        if not t or t.text != "{":
            l = t.line if t else self.ll
            c = t.col if t else self.lc + 1
            sys.stderr.write(f"compilation error: line {l}:{c}: expected '{{' on its own line after fn header\n")
            sys.exit(1)

        body = self.parse_block()
        return funcnode(fn_kw.line, fn_kw.col, name_t.text, params, ret_type, body)

    def parse_type(self):
        t = self.peek()
        if not t or (t.kind not in ("typename", "identifier") and t.text not in ("i32", "i64", "bool")):
            l = t.line if t else self.ll
            c = t.col if t else self.lc + 1
            sys.stderr.write(f"compilation error: line {l}:{c}: expected type\n")
            sys.exit(1)
        return self.eat().text

    def parse_statement(self):
        t = self.peek()
        if t and t.text == "print":
            s = self.parse_print()
            self.check_eol()
            return s
        elif t and t.kind == "string":
            sys.stderr.write(f"compilation error: line {t.line}:{t.col}: string literal outside print\n")
            sys.exit(1)
        elif t and (t.text in ("i32", "i64", "bool") or (t.kind == "identifier" and self.is_decl_start())):
            s = self.parse_decl()
            self.check_eol()
            return s
        elif t and t.kind == "identifier":
            s = self.parse_assign()
            self.check_eol()
            return s
        elif t and t.text == "if":
            return self.parse_if()
        elif t and t.text == "while":
            return self.parse_while()
        elif t and t.text == "else":
            sys.stderr.write(f"compilation error: line {t.line}:{t.col}: 'else' without an 'if'\n")
            sys.exit(1)
        elif t and t.text == "fn":
            if self.is_lambda_start():
                return self.parse_lambda()
            else:
                sys.stderr.write(f"compilation error: line {t.line}:{t.col}: fn declared inside function or after statement\n")
                sys.exit(1)
        elif t and t.text == "struct":
            sys.stderr.write(f"compilation error: line {t.line}:{t.col}: struct declared inside function or after statement\n")
            sys.exit(1)
        else:
            l = t.line if t else self.ll
            c = t.col if t else self.lc + 1
            sys.stderr.write(f"compilation error: line {l}:{c}: bad statement\n")
            sys.exit(1)

    def parse_print(self):
        pr = self.eat()
        self.exp("(", "'('")
        t = self.peek()
        if not t or t.text == ")":
            sys.stderr.write(f"compilation error: line {pr.line}:{pr.col}: print() expects 1 argument, got 0\n")
            sys.exit(1)
        if t.kind == "string":
            arg = self.eat()
            arg_node = stringnode(arg.line, arg.col, arg.text)
        else:
            arg_node = self.parse_expr()
        if self.peek() and self.peek().text == ",":
            t_comma = self.peek()
            sys.stderr.write(f"compilation error: line {t_comma.line}:{t_comma.col}: print() takes only 1 argument\n")
            sys.exit(1)
        self.exp(")", "')'")
        return printnode(pr.line, pr.col, arg_node)

    def is_decl_start(self):
        cur_line = self.lines[self.lpos]
        p = self.tpos + 1
        if p < len(cur_line) and cur_line[p].text == "mut":
            p += 1
            if p < len(cur_line) and cur_line[p].kind == "identifier":
                p += 1
                if p < len(cur_line) and cur_line[p].text == "{":
                    return True
        elif p < len(cur_line) and cur_line[p].kind == "identifier":
            p += 1
            if p < len(cur_line) and cur_line[p].text == "{":
                return True
        return False

    def parse_decl(self):
        t = self.eat()
        mut = False
        if self.peek() and self.peek().text == "mut": mut = True; self.eat()
        n = self.exp("identifier", "name")
        self.check_not_reserved(n)
        
        b1 = self.peek()
        if not b1 or b1.text != "{":
            l = b1.line if b1 else self.ll
            c = b1.col if b1 else self.lc + 1
            sys.stderr.write(f"compilation error: line {l}:{c}: expected '{{'\n")
            sys.exit(1)
        self.eat()
        
        inits = [self.parse_expr()]
        while self.peek() and self.peek().text == ",":
            self.eat()
            inits.append(self.parse_expr())
        
        b2 = self.peek()
        if not b2 or b2.text != "}":
            l = b2.line if b2 else self.ll
            c = b2.col if b2 else self.lc + 1
            sys.stderr.write(f"compilation error: line {l}:{c}: expected '}}'\n")
            sys.exit(1)
        self.eat()
        
        return declnode(n.line, n.col, t.text, n.text, mut, inits)

    def parse_assign(self):
        n = self.exp("identifier", "target")
        self.check_not_reserved(n)
        chain = [n.text]
        while self.peek() and self.peek().text == ".":
            self.eat()
            fld = self.exp("identifier", "field")
            self.check_not_reserved(fld)
            chain.append(fld.text)

        o = self.exp("operator", ":=")
        if o.text != ":=":
            sys.stderr.write(f"compilation error: line {o.line}:{o.col}: need :=\n")
            sys.exit(1)
        return assignnode(n.line, n.col, chain, self.parse_expr())

    def parse_if(self):
        i = self.eat()
        cond = self.parse_expr()
        if not self.eol():
            t = self.peek()
            if t.text == "{":
                sys.stderr.write(f"compilation error: line {t.line}:{t.col}: unexpected '{{' after the statement\n")
                sys.exit(1)
        self.check_eol()
        
        t = self.peek()
        if not t or t.text != "{":
            l = t.line if t else self.ll
            c = t.col if t else self.lc + 1
            sys.stderr.write(f"compilation error: line {l}:{c}: expected '{{' on its own line after 'if'\n")
            sys.exit(1)
            
        then_b = self.parse_block()
        else_b = None
        
        t = self.peek()
        if t and t.text == "else":
            e = self.eat()
            if not self.eol():
                t2 = self.peek()
                sys.stderr.write(f"compilation error: line {t2.line}:{t2.col}: junk after 'else'\n")
                sys.exit(1)
            self.check_eol()
            t_brace = self.peek()
            if not t_brace or t_brace.text != "{":
                l = t_brace.line if t_brace else self.ll
                c = t_brace.col if t_brace else self.lc + 1
                sys.stderr.write(f"compilation error: line {l}:{c}: expected '{{' on its own line after 'else'\n")
                sys.exit(1)
            else_b = self.parse_block()
            
        return ifnode(i.line, i.col, cond, then_b, else_b)

    def parse_while(self):
        w = self.eat()
        cond = self.parse_expr()
        if not self.eol():
            t = self.peek()
            if t.text == "{":
                sys.stderr.write(f"compilation error: line {t.line}:{t.col}: unexpected '{{' after the statement\n")
                sys.exit(1)
        self.check_eol()
        
        t = self.peek()
        if not t or t.text != "{":
            l = t.line if t else self.ll
            c = t.col if t else self.lc + 1
            sys.stderr.write(f"compilation error: line {l}:{c}: expected '{{' on its own line after 'while'\n")
            sys.exit(1)
            
        body = self.parse_block()
        return whilenode(w.line, w.col, cond, body)

    def parse_lambda(self):
        fn_kw = self.eat()
        name_t = self.exp("identifier", "lambda name")
        self.check_not_reserved(name_t)
        self.exp(":=", "':='")
        self.exp("[", "'['")

        captures = []
        if self.peek() and self.peek().text != "]":
            c_name = self.exp("identifier", "capture name")
            self.check_not_reserved(c_name)
            captures.append((c_name.text, c_name.line, c_name.col))
            while self.peek() and self.peek().text == ",":
                self.eat()
                c_name = self.exp("identifier", "capture name")
                self.check_not_reserved(c_name)
                captures.append((c_name.text, c_name.line, c_name.col))

        self.exp("]", "']'")
        self.exp("(", "'('")

        params = []
        if self.peek() and self.peek().text != ")":
            p_type = self.parse_type()
            p_name = self.exp("identifier", "parameter name")
            self.check_not_reserved(p_name)
            params.append((p_type, p_name.text, p_name.line, p_name.col))
            while self.peek() and self.peek().text == ",":
                self.eat()
                p_type = self.parse_type()
                p_name = self.exp("identifier", "parameter name")
                self.check_not_reserved(p_name)
                params.append((p_type, p_name.text, p_name.line, p_name.col))

        self.exp(")", "')'")
        self.exp("->", "'->'")
        ret_type = self.parse_type()
        self.check_eol()

        t = self.peek()
        if not t or t.text != "{":
            l = t.line if t else self.ll
            c = t.col if t else self.lc + 1
            sys.stderr.write(f"compilation error: line {l}:{c}: expected '{{' on its own line after fn header\n")
            sys.exit(1)

        body = self.parse_block()
        return lambdanode(fn_kw.line, fn_kw.col, name_t.text, captures, params, ret_type, body)

    def parse_block(self):
        lb = self.eat()
        if not self.eol():
            t = self.peek()
            sys.stderr.write(f"compilation error: line {t.line}:{t.col}: unexpected '{t.text}' after '{{'\n")
            sys.exit(1)
        self.next_line()
        
        stmts, ex = [], None
        while self.lpos < len(self.lines):
            t = self.peek()
            if t and t.text == "}":
                break
            if ex:
                sys.stderr.write(f"compilation error: line {t.line}:{t.col}: statement after 'exit' in the same block\n")
                sys.exit(1)
            
            if t and t.text == "exit":
                ex = self.parse_exit()
                self.check_eol()
            else:
                stmts.append(self.parse_statement())
        
        t = self.peek()
        if not t or t.text != "}":
            sys.stderr.write(f"compilation error: line {lb.line}:{lb.col}: '{{' is never closed\n")
            sys.exit(1)
        self.eat()
        self.check_eol()
        
        if not stmts and not ex:
            sys.stderr.write(f"compilation error: line {lb.line}:{lb.col}: empty block\n")
            sys.exit(1)
            
        return blocknode(lb.line, lb.col, stmts, ex)

    def parse_exit(self):
        e = self.eat()
        return exitnode(e.line, e.col, self.parse_factor())

    def parse_expr(self):
        n = self.parse_arith()
        if self.peek() and self.peek().text in ("==", "!="):
            t = self.eat()
            n = binopnode(t.line, t.col, t.text, n, self.parse_arith())
        return n

    def parse_arith(self):
        n = self.parse_term()
        while self.peek() and self.peek().text in ("+", "-"):
            t = self.eat()
            n = binopnode(t.line, t.col, t.text, n, self.parse_term())
        return n

    def parse_term(self):
        n = self.parse_factor()
        while self.peek() and self.peek().text == "*":
            t = self.eat()
            n = binopnode(t.line, t.col, t.text, n, self.parse_factor())
        return n

    def parse_factor(self):
        t = self.peek()
        if not t:
            sys.stderr.write(f"compilation error: line {self.ll}:{self.lc + 1}: need val\n")
            sys.exit(1)
        if t.kind == "string":
            sys.stderr.write(f"compilation error: line {t.line}:{t.col}: string literal outside print\n")
            sys.exit(1)
        if t.text == "!":
            op = self.eat()
            return notnode(op.line, op.col, self.parse_factor())
        if t.kind == "constant": return constnode(self.eat().line, t.col, t.text)
        if t.kind == "boolean": return boolnode(self.eat().line, t.col, t.text)
        if t.text == "print":
            sys.stderr.write(f"compilation error: line {t.line}:{t.col}: 'print' has no value\n")
            sys.exit(1)
        if t.text == "read":
            id_t = self.eat()
            if self.peek() and self.peek().text == "(":
                self.eat()
                if self.peek() and self.peek().text != ")":
                    t_arg = self.peek()
                    sys.stderr.write(f"compilation error: line {t_arg.line}:{t_arg.col}: read() takes no arguments\n")
                    sys.exit(1)
                self.exp(")", "')'")
                return readnode(id_t.line, id_t.col)
            else:
                sys.stderr.write(f"compilation error: line {id_t.line}:{id_t.col}: 'read' is a built-in function, expected '()'\n")
                sys.exit(1)
        if t.kind == "identifier":
            id_t = self.eat()
            if self.peek() and self.peek().text == "(":
                self.eat()
                args = []
                if self.peek() and self.peek().text != ")":
                    args.append(self.parse_expr())
                    while self.peek() and self.peek().text == ",":
                        self.eat()
                        args.append(self.parse_expr())
                self.exp(")", "')'")
                return callnode(id_t.line, id_t.col, id_t.text, args)
            if self.peek() and self.peek().text == ".":
                chain = [id_t]
                while self.peek() and self.peek().text == ".":
                    self.eat()
                    nxt = self.exp("identifier", "name after '.'")
                    if nxt.text == "print":
                        sys.stderr.write(f"compilation error: line {nxt.line}:{nxt.col}: 'print' is a reserved keyword\n")
                        sys.exit(1)
                    if nxt.text == "read":
                        sys.stderr.write(f"compilation error: line {nxt.line}:{nxt.col}: 'read' is a reserved keyword\n")
                        sys.exit(1)
                    if self.peek() and self.peek().text == "(":
                        self.eat()
                        args = []
                        if self.peek() and self.peek().text != ")":
                            args.append(self.parse_expr())
                            while self.peek() and self.peek().text == ",":
                                self.eat()
                                args.append(self.parse_expr())
                        self.exp(")", "')'")
                        if len(chain) == 1:
                            target = varnode(chain[0].line, chain[0].col, chain[0].text)
                        else:
                            target = fieldaccessnode(chain[0].line, chain[0].col, [x.text for x in chain])
                        return membercallnode(nxt.line, nxt.col, target, nxt.text, args)
                    chain.append(nxt)
                return fieldaccessnode(chain[0].line, chain[0].col, [x.text for x in chain])
            return varnode(id_t.line, id_t.col, id_t.text)

        sys.stderr.write(f"compilation error: line {t.line}:{t.col}: bad val\n")
        sys.exit(1)


class semanticchecker:
    def __init__(self):
        self.structs = {}
        self.struct_nodes = {}
        self.struct_member_funcs = {}
        self.funcs = {}
        self.scopes = [{}]
        self.current_fn = None
        self.current_struct = None
        self.current_member_fn = None
        self.mutating_member_funcs = set()
        self.all_member_calls = []
        self.enclosing_lambda_scopes = set()
        self.current_lambda = None
        self.lambda_struct_counts = {}
        self.tree = None

    def is_type_known(self, t):
        return t in ("i32", "i64", "bool") or t in self.structs

    def is_all_mut(self, t):
        if t in ("i32", "i64", "bool"):
            return True
        st_fields = self.structs[t]
        for fname, (fidx, ftype, fmut) in st_fields.items():
            if not fmut:
                return False
            if not self.is_all_mut(ftype):
                return False
        return True

    def visit_program(self, node):
        self.tree = node
        for s in node.structs:
            if s.name in ("i32", "i64", "bool", "read", "print"):
                sys.stderr.write(f"compilation error: line {s.line}:{s.col}: cannot redeclare built-in type or keyword '{s.name}'\n")
                sys.exit(1)
            if s.name in self.structs:
                sys.stderr.write(f"compilation error: line {s.line}:{s.col}: struct '{s.name}' already declared\n")
                sys.exit(1)
            fields_map = {}
            for idx, f in enumerate(s.fields):
                if f.name in fields_map:
                    sys.stderr.write(f"compilation error: line {f.line}:{f.col}: field '{f.name}' already declared in struct '{s.name}'\n")
                    sys.exit(1)
                fields_map[f.name] = (idx, f.type_name, f.mut)
            self.structs[s.name] = fields_map
            self.struct_nodes[s.name] = s
            self.struct_member_funcs[s.name] = {}

        for s in node.structs:
            for idx, f in enumerate(s.fields):
                if not self.is_type_known(f.type_name):
                    sys.stderr.write(f"compilation error: line {f.line}:{f.col}: unknown type '{f.type_name}' in struct '{s.name}'\n")
                    sys.exit(1)
                if f.type_name == s.name:
                    sys.stderr.write(f"compilation error: line {f.line}:{f.col}: struct '{s.name}' cannot contain itself\n")
                    sys.exit(1)

        for s in node.structs:
            mf_map = self.struct_member_funcs[s.name]
            for mf in s.member_funcs:
                if mf.name in mf_map:
                    sys.stderr.write(f"compilation error: line {mf.line}:{mf.col}: member function '{mf.name}' already declared in struct '{s.name}'\n")
                    sys.exit(1)
                if not self.is_type_known(mf.ret_type):
                    sys.stderr.write(f"compilation error: line {mf.line}:{mf.col}: unknown return type '{mf.ret_type}'\n")
                    sys.exit(1)
                param_names = set()
                for p_type, p_name, p_line, p_col in mf.params:
                    if p_name in param_names:
                        sys.stderr.write(f"compilation error: line {p_line}:{p_col}: duplicate parameter name '{p_name}'\n")
                        sys.exit(1)
                    if not self.is_type_known(p_type):
                        sys.stderr.write(f"compilation error: line {p_line}:{p_col}: unknown parameter type '{p_type}'\n")
                        sys.exit(1)
                    param_names.add(p_name)
                mf_map[mf.name] = mf

        for f in node.funcs:
            if f.name in self.funcs:
                sys.stderr.write(f"compilation error: line {f.line}:{f.col}: function '{f.name}' already declared\n")
                sys.exit(1)
            if not self.is_type_known(f.ret_type):
                sys.stderr.write(f"compilation error: line {f.line}:{f.col}: unknown return type '{f.ret_type}'\n")
                sys.exit(1)
            param_names = set()
            for p_type, p_name, p_line, p_col in f.params:
                if p_name in param_names:
                    sys.stderr.write(f"compilation error: line {p_line}:{p_col}: duplicate parameter name '{p_name}'\n")
                    sys.exit(1)
                if not self.is_type_known(p_type):
                    sys.stderr.write(f"compilation error: line {p_line}:{p_col}: unknown parameter type '{p_type}'\n")
                    sys.exit(1)
                param_names.add(p_name)
            self.funcs[f.name] = {
                "params": [(p[0], p[1]) for p in f.params],
                "ret_type": f.ret_type,
                "node": f
            }

        for s in list(node.structs):
            self.current_struct = s
            for mf in s.member_funcs:
                self.current_member_fn = mf
                mf.direct_mutates = False
                mf.calls_on_this = []
                mf.calls_on_fields = []
                mf.struct_name = s.name
                param_scope = {}
                for p_type, p_name, p_line, p_col in mf.params:
                    p_decl = declnode(p_line, p_col, p_type, p_name, False, [])
                    p_decl.type = p_type
                    param_scope[p_name] = p_decl
                mf.saved_param_scope = param_scope
                self.scopes = [param_scope]
                self.visit_block(mf.body, is_fn_body=True)
                if mf.direct_mutates:
                    self.mutating_member_funcs.add((s.name, mf.name))
                self.current_member_fn = None
            self.current_struct = None

        for f in node.funcs:
            self.current_fn = f
            param_scope = {}
            for p_type, p_name, p_line, p_col in f.params:
                p_decl = declnode(p_line, p_col, p_type, p_name, False, [])
                p_decl.type = p_type
                param_scope[p_name] = p_decl
            f.saved_param_scope = param_scope
            self.scopes = [param_scope]
            self.visit_block(f.body, is_fn_body=True)
            self.current_fn = None

        changed = True
        while changed:
            changed = False
            for s in list(node.structs):
                for mf in s.member_funcs:
                    if (s.name, mf.name) in self.mutating_member_funcs:
                        continue
                    for called_mf_name in mf.calls_on_this:
                        if (s.name, called_mf_name) in self.mutating_member_funcs:
                            self.mutating_member_funcs.add((s.name, mf.name))
                            changed = True
                            break
                    if (s.name, mf.name) in self.mutating_member_funcs:
                        continue
                    for field_type, called_mf_name in mf.calls_on_fields:
                        if (field_type, called_mf_name) in self.mutating_member_funcs:
                            self.mutating_member_funcs.add((s.name, mf.name))
                            changed = True
                            break

        self.scopes = [{}]
        self.current_fn = None
        self.current_struct = None
        self.current_member_fn = None
        for s in node.stmts:
            if isinstance(s, declnode): self.visit_decl(s)
            elif isinstance(s, assignnode): self.visit_assign(s)
            elif isinstance(s, ifnode): self.visit_if(s)
            elif isinstance(s, whilenode): self.visit_while(s)
            elif isinstance(s, lambdanode): self.visit_lambda(s)
            elif isinstance(s, printnode): self.visit_print(s)
        self.visit_exit(node.exit_node)

        self.check_all_member_calls()

    def check_all_member_calls(self):
        for node, target_struct, method_name, target_node, caller_mf in self.all_member_calls:
            if (target_struct, method_name) in self.mutating_member_funcs:
                is_callable = getattr(node, "is_callable_call", False)
                callable_name = getattr(node, "callable_name", None)
                if callable_name is None and target_node:
                    callable_name = target_node.name if isinstance(target_node, varnode) else ('.'.join(target_node.chain) if isinstance(target_node, fieldaccessnode) else None)
                if target_node is None:
                    continue
                if isinstance(target_node, varnode):
                    if hasattr(target_node, "is_this_field") and target_node.is_this_field:
                        finfo = self.structs[caller_mf.struct_name][target_node.name]
                        if not finfo[2]:
                            if is_callable:
                                sys.stderr.write(f"compilation error: line {node.line}:{node.col}: cannot call '{callable_name}': its 'call' changes it, and it is not mut\n")
                            else:
                                sys.stderr.write(f"compilation error: line {node.line}:{node.col}: cannot call mutating member function '{method_name}' through const link '{target_node.name}'\n")
                            sys.exit(1)
                    else:
                        decl = target_node.decl
                        if not decl.mut:
                            if is_callable:
                                sys.stderr.write(f"compilation error: line {node.line}:{node.col}: cannot call '{callable_name}': its 'call' changes it, and it is not mut\n")
                            else:
                                sys.stderr.write(f"compilation error: line {node.line}:{node.col}: cannot call mutating member function '{method_name}' on const object '{target_node.name}'\n")
                            sys.exit(1)
                elif isinstance(target_node, fieldaccessnode):
                    if hasattr(target_node, "is_this_field") and target_node.is_this_field:
                        root_fname = target_node.chain[0]
                        finfo = self.structs[caller_mf.struct_name][root_fname]
                        if not finfo[2]:
                            if is_callable:
                                sys.stderr.write(f"compilation error: line {node.line}:{node.col}: cannot call '{callable_name}': its 'call' changes it, and it is not mut\n")
                            else:
                                sys.stderr.write(f"compilation error: line {node.line}:{node.col}: cannot call mutating member function '{method_name}' through const link '{root_fname}'\n")
                            sys.exit(1)
                        cur_t = finfo[1]
                        for fn in target_node.chain[1:]:
                            sub_info = self.structs[cur_t][fn]
                            if not sub_info[2]:
                                if is_callable:
                                    sys.stderr.write(f"compilation error: line {node.line}:{node.col}: cannot call '{callable_name}': its 'call' changes it, and it is not mut\n")
                                else:
                                    sys.stderr.write(f"compilation error: line {node.line}:{node.col}: cannot call mutating member function '{method_name}' through const link '{fn}'\n")
                                sys.exit(1)
                            cur_t = sub_info[1]
                    else:
                        root_decl = target_node.decl
                        if not root_decl.mut:
                            if is_callable:
                                sys.stderr.write(f"compilation error: line {node.line}:{node.col}: cannot call '{callable_name}': its 'call' changes it, and it is not mut\n")
                            else:
                                sys.stderr.write(f"compilation error: line {node.line}:{node.col}: cannot call mutating member function '{method_name}' on const object '{target_node.chain[0]}'\n")
                            sys.exit(1)
                        cur_t = root_decl.type_name
                        for fn in target_node.chain[1:]:
                            sub_info = self.structs[cur_t][fn]
                            if not sub_info[2]:
                                if is_callable:
                                    sys.stderr.write(f"compilation error: line {node.line}:{node.col}: cannot call '{callable_name}': its 'call' changes it, and it is not mut\n")
                                else:
                                    sys.stderr.write(f"compilation error: line {node.line}:{node.col}: cannot call mutating member function '{method_name}' through const link '{fn}'\n")
                                sys.exit(1)
                            cur_t = sub_info[1]

    def visit_block(self, node, is_fn_body=False):
        if not is_fn_body:
            self.scopes.append({})
        for s in node.stmts:
            if isinstance(s, declnode): self.visit_decl(s)
            elif isinstance(s, assignnode): self.visit_assign(s)
            elif isinstance(s, ifnode): self.visit_if(s)
            elif isinstance(s, whilenode): self.visit_while(s)
            elif isinstance(s, lambdanode): self.visit_lambda(s)
            elif isinstance(s, printnode): self.visit_print(s)
        if node.ex: self.visit_exit(node.ex)
        if not is_fn_body:
            self.scopes.pop()

    def visit_while(self, node):
        self.visit(node.cond)
        if node.cond.type != "bool":
            sys.stderr.write(f"compilation error: line {node.line}:{node.col}: the condition of 'while' must be bool, got {node.cond.type}\n")
            sys.exit(1)
        self.visit_block(node.body)

    def visit_lambda(self, node):
        seen = set()
        for c_name, c_line, c_col in node.captures:
            if c_name in seen:
                sys.stderr.write(f"compilation error: line {c_line}:{c_col}: '{c_name}' is captured twice\n")
                sys.exit(1)
            seen.add(c_name)

        captured_fields = []
        for c_name, c_line, c_col in node.captures:
            c_decl = None
            for sc in reversed(self.scopes):
                if c_name in sc:
                    c_decl = sc[c_name]
                    break
            is_field = False
            if not c_decl and self.current_struct is not None and c_name in self.structs.get(self.current_struct.name, {}):
                is_field = True
                fidx, ftype, fmut = self.structs[self.current_struct.name][c_name]
                c_type = ftype
            elif c_decl:
                c_type = c_decl.type_name
            else:
                sys.stderr.write(f"compilation error: line {c_line}:{c_col}: cannot capture '{c_name}': no variable '{c_name}' is visible here\n")
                sys.exit(1)
            captured_fields.append((c_name, c_line, c_col, c_type, is_field))

        cap_names = {c[0] for c in node.captures}
        for p_type, p_name, p_line, p_col in node.params:
            if p_name in cap_names:
                sys.stderr.write(f"compilation error: line {p_line}:{p_col}: parameter '{p_name}' has the same name as a capture\n")
                sys.exit(1)

        count = self.lambda_struct_counts.get(node.name, 0)
        self.lambda_struct_counts[node.name] = count + 1
        st_name = f"lambda.{node.name}" if count == 0 else f"lambda.{node.name}_{count}"

        st_fields = [fielddeclnode(c_line, c_col, c_type, False, c_name) for c_name, c_line, c_col, c_type, _ in captured_fields]
        mf = memberfnnode(node.line, node.col, "call", node.params, node.ret_type, node.body)
        st_node = structnode(node.line, node.col, st_name, st_fields, [mf])
        node.rewritten_struct = st_node

        self.tree.structs.append(st_node)
        self.struct_nodes[st_name] = st_node
        self.structs[st_name] = {f.name: (idx, f.type_name, f.mut) for idx, f in enumerate(st_fields)}
        self.struct_member_funcs[st_name] = {"call": mf}

        inits = []
        for c_name, c_line, c_col, c_type, is_field in captured_fields:
            v = varnode(c_line, c_col, c_name)
            if is_field:
                v.is_this_field = True
                v.type = c_type
            else:
                for sc in reversed(self.scopes):
                    if c_name in sc:
                        v.decl = sc[c_name]
                        break
                v.type = c_type
            inits.append(v)
        decl = declnode(node.line, node.col, st_name, node.name, False, inits)
        decl.type = st_name
        decl.type_name = st_name
        node.rewritten_decl = decl

        prev_scopes = self.scopes
        prev_struct = self.current_struct
        prev_member_fn = self.current_member_fn
        prev_lambda = self.current_lambda
        prev_enclosing = self.enclosing_lambda_scopes

        new_enclosing = set(self.enclosing_lambda_scopes) if self.enclosing_lambda_scopes else set()
        for sc in self.scopes:
            new_enclosing.update(sc.keys())
        if self.current_struct is not None:
            new_enclosing.update(self.structs.get(self.current_struct.name, {}).keys())
        self.enclosing_lambda_scopes = new_enclosing
        self.current_lambda = node
        self.current_struct = st_node
        self.current_member_fn = mf

        mf.direct_mutates = False
        mf.calls_on_this = []
        mf.calls_on_fields = []
        mf.struct_name = st_name

        param_scope = {}
        for p_type, p_name, p_line, p_col in node.params:
            p_decl = declnode(p_line, p_col, p_type, p_name, False, [])
            p_decl.type = p_type
            param_scope[p_name] = p_decl
        mf.saved_param_scope = param_scope
        self.scopes = [param_scope]

        self.visit_block(node.body, is_fn_body=True)

        self.scopes = prev_scopes
        self.current_struct = prev_struct
        self.current_member_fn = prev_member_fn
        self.current_lambda = prev_lambda
        self.enclosing_lambda_scopes = prev_enclosing

        if node.name in self.scopes[-1]:
            sys.stderr.write(f"compilation error: line {node.line}:{node.col}: variable '{node.name}' is already declared in this block\n")
            sys.exit(1)
        self.scopes[-1][node.name] = decl
        node.type = st_name

    def visit_print(self, node):
        if isinstance(node.arg, stringnode):
            return
        self.visit(node.arg)
        t = node.arg.type
        if t.startswith("lambda."):
            name = node.arg.name if isinstance(node.arg, varnode) else ('.'.join(node.arg.chain) if isinstance(node.arg, fieldaccessnode) else 'lambda')
            sys.stderr.write(f"compilation error: line {node.arg.line}:{node.arg.col}: '{name}' is a lambda and cannot be printed: its type has no name\n")
            sys.exit(1)
        if t not in ("i32", "i64", "bool") and t not in self.structs:
            sys.stderr.write(f"compilation error: line {node.line}:{node.col}: cannot print value of type '{t}'\n")
            sys.exit(1)

    def visit_decl(self, node):
        if not self.is_type_known(node.type_name):
            sys.stderr.write(f"compilation error: line {node.line}:{node.col}: unknown type '{node.type_name}'\n")
            sys.exit(1)
        if node.name in self.scopes[-1]:
            sys.stderr.write(f"compilation error: line {node.line}:{node.col}: variable '{node.name}' is already declared in this block\n")
            sys.exit(1)

        t_name = node.type_name
        if t_name in ("i32", "i64", "bool"):
            if len(node.inits) != 1:
                sys.stderr.write(f"compilation error: line {node.line}:{node.col}: built-in type '{t_name}' expects 1 initialiser, got {len(node.inits)}\n")
                sys.exit(1)
            self.visit(node.inits[0])
            if node.inits[0].type.startswith("lambda."):
                name = node.inits[0].name if isinstance(node.inits[0], varnode) else ('.'.join(node.inits[0].chain) if isinstance(node.inits[0], fieldaccessnode) else 'lambda')
                sys.stderr.write(f"compilation error: line {node.inits[0].line}:{node.inits[0].col}: '{name}' is a lambda and cannot initialise a variable: its type has no name\n")
                sys.exit(1)
            self.check_assignable(node.inits[0], t_name, node, f"initialise '{node.name}'")
        else:
            st_fields = list(self.structs[t_name].items())
            if len(node.inits) == 1 and (node.inits[0].type == t_name or self.visit(node.inits[0]) == t_name):
                pass
            else:
                if len(node.inits) != len(st_fields):
                    sys.stderr.write(f"compilation error: line {node.line}:{node.col}: wrong number of values in {{}}: expected {len(st_fields)}, got {len(node.inits)}\n")
                    sys.exit(1)
                for init_expr, (fname, (fidx, ftype, fmut)) in zip(node.inits, st_fields):
                    self.visit(init_expr)
                    if init_expr.type.startswith("lambda."):
                        name = init_expr.name if isinstance(init_expr, varnode) else ('.'.join(init_expr.chain) if isinstance(init_expr, fieldaccessnode) else 'lambda')
                        sys.stderr.write(f"compilation error: line {init_expr.line}:{init_expr.col}: '{name}' is a lambda and cannot initialise a variable: its type has no name\n")
                        sys.exit(1)
                    self.check_assignable(init_expr, ftype, init_expr, f"initialise field '{fname}' of '{node.name}'")

        node.type = node.type_name
        self.scopes[-1][node.name] = node

    def visit_assign(self, node):
        root_name = node.target[0]
        decl = None
        for scope in reversed(self.scopes):
            if root_name in scope:
                decl = scope[root_name]
                break

        if not decl:
            if self.current_struct is not None and root_name in self.structs[self.current_struct.name]:
                node.is_this_field = True
                st_name = self.current_struct.name
                fidx, ftype, fmut = self.structs[st_name][root_name]
                if self.current_lambda is not None and root_name in {c[0] for c in self.current_lambda.captures}:
                    sys.stderr.write(f"compilation error: line {node.line}:{node.col}: cannot assign to '{root_name}': the capture '{root_name}' is const, write [mut {root_name}]\n")
                    sys.exit(1)
                if len(node.target) == 1:
                    if not fmut:
                        sys.stderr.write(f"compilation error: line {node.line}:{node.col}: cannot assign to const field '{root_name}'\n")
                        sys.exit(1)
                    if ftype in self.structs and not self.is_all_mut(ftype):
                        sys.stderr.write(f"compilation error: line {node.line}:{node.col}: cannot assign whole struct '{root_name}' containing const fields\n")
                        sys.exit(1)
                    self.visit(node.value)
                    if node.value.type.startswith("lambda."):
                        name = node.value.name if isinstance(node.value, varnode) else ('.'.join(node.value.chain) if isinstance(node.value, fieldaccessnode) else 'lambda')
                        sys.stderr.write(f"compilation error: line {node.value.line}:{node.value.col}: '{name}' is a lambda and cannot be assigned: its type has no name\n")
                        sys.exit(1)
                    self.check_assignable(node.value, ftype, node, f"assign to '{root_name}'")
                    node.field_indices = [fidx]
                    node.target_type = ftype
                    if self.current_member_fn:
                        self.current_member_fn.direct_mutates = True
                    return
                else:
                    if not fmut:
                        sys.stderr.write(f"compilation error: line {node.line}:{node.col}: cannot write through const link '{root_name}'\n")
                        sys.exit(1)
                    cur_type = ftype
                    field_indices = [fidx]
                    for field_name in node.target[1:]:
                        if cur_type not in self.structs:
                            sys.stderr.write(f"compilation error: line {node.line}:{node.col}: cannot access field '{field_name}' of non-struct type '{cur_type}'\n")
                            sys.exit(1)
                        st_fields = self.structs[cur_type]
                        if field_name not in st_fields:
                            sys.stderr.write(f"compilation error: line {node.line}:{node.col}: unknown field '{field_name}' in struct '{cur_type}'\n")
                            sys.exit(1)
                        sub_idx, sub_type, sub_mut = st_fields[field_name]
                        if not sub_mut:
                            sys.stderr.write(f"compilation error: line {node.line}:{node.col}: cannot write through const link '{field_name}'\n")
                            sys.exit(1)
                        field_indices.append(sub_idx)
                        cur_type = sub_type
                    if cur_type in self.structs and not self.is_all_mut(cur_type):
                        sys.stderr.write(f"compilation error: line {node.line}:{node.col}: cannot assign struct field containing const fields\n")
                        sys.exit(1)
                    self.visit(node.value)
                    if node.value.type.startswith("lambda."):
                        name = node.value.name if isinstance(node.value, varnode) else ('.'.join(node.value.chain) if isinstance(node.value, fieldaccessnode) else 'lambda')
                        sys.stderr.write(f"compilation error: line {node.value.line}:{node.value.col}: '{name}' is a lambda and cannot be assigned: its type has no name\n")
                        sys.exit(1)
                    self.check_assignable(node.value, cur_type, node, f"assign to field '{'.'.join(node.target)}'")
                    node.field_indices = field_indices
                    node.target_type = cur_type
                    if self.current_member_fn:
                        self.current_member_fn.direct_mutates = True
                    return

            if self.current_lambda is not None and root_name in self.enclosing_lambda_scopes:
                sys.stderr.write(f"compilation error: line {node.line}:{node.col}: '{root_name}' is not captured by lambda '{self.current_lambda.name}': add it to the capture list, [{root_name}]\n")
                sys.exit(1)

            sys.stderr.write(f"compilation error: line {node.line}:{node.col}: variable '{root_name}' is used before its declaration\n")
            sys.exit(1)

        if len(node.target) == 1:
            if not decl.mut:
                sys.stderr.write(f"compilation error: line {node.line}:{node.col}: cannot assign to const variable '{root_name}'\n")
                sys.exit(1)
            if decl.type_name in self.structs:
                if not self.is_all_mut(decl.type_name):
                    sys.stderr.write(f"compilation error: line {node.line}:{node.col}: cannot assign whole struct '{root_name}' containing const fields\n")
                    sys.exit(1)
            self.visit(node.value)
            if node.value.type.startswith("lambda."):
                name = node.value.name if isinstance(node.value, varnode) else ('.'.join(node.value.chain) if isinstance(node.value, fieldaccessnode) else 'lambda')
                sys.stderr.write(f"compilation error: line {node.value.line}:{node.value.col}: '{name}' is a lambda and cannot be assigned: its type has no name\n")
                sys.exit(1)
            self.check_assignable(node.value, decl.type_name, node, f"assign to '{root_name}'")
            node.decl = decl
            node.field_indices = []
            node.target_type = decl.type_name
        else:
            if not decl.mut:
                sys.stderr.write(f"compilation error: line {node.line}:{node.col}: cannot write through const object '{root_name}'\n")
                sys.exit(1)
            
            cur_type = decl.type_name
            field_indices = []
            for field_name in node.target[1:]:
                if cur_type not in self.structs:
                    sys.stderr.write(f"compilation error: line {node.line}:{node.col}: cannot access field '{field_name}' of non-struct type '{cur_type}'\n")
                    sys.exit(1)
                st_fields = self.structs[cur_type]
                if field_name not in st_fields:
                    sys.stderr.write(f"compilation error: line {node.line}:{node.col}: unknown field '{field_name}' in struct '{cur_type}'\n")
                    sys.exit(1)
                fidx, ftype, fmut = st_fields[field_name]
                if not fmut:
                    sys.stderr.write(f"compilation error: line {node.line}:{node.col}: cannot write through const link '{field_name}'\n")
                    sys.exit(1)
                field_indices.append(fidx)
                cur_type = ftype

            if cur_type in self.structs and not self.is_all_mut(cur_type):
                sys.stderr.write(f"compilation error: line {node.line}:{node.col}: cannot assign struct field containing const fields\n")
                sys.exit(1)

            self.visit(node.value)
            if node.value.type.startswith("lambda."):
                name = node.value.name if isinstance(node.value, varnode) else ('.'.join(node.value.chain) if isinstance(node.value, fieldaccessnode) else 'lambda')
                sys.stderr.write(f"compilation error: line {node.value.line}:{node.value.col}: '{name}' is a lambda and cannot be assigned: its type has no name\n")
                sys.exit(1)
            self.check_assignable(node.value, cur_type, node, f"assign to field '{'.'.join(node.target)}'")
            node.decl = decl
            node.field_indices = field_indices
            node.target_type = cur_type

    def visit_if(self, node):
        self.visit(node.cond)
        if node.cond.type != "bool":
            sys.stderr.write(f"compilation error: line {node.line}:{node.col}: the condition of 'if' must be bool, got {node.cond.type}\n")
            sys.exit(1)
        self.visit_block(node.then_block)
        if node.else_block: self.visit_block(node.else_block)

    def visit_not(self, node):
        self.visit(node.val)
        if node.val.type != "bool":
            sys.stderr.write(f"compilation error: line {node.line}:{node.col}: cannot apply '!' to {node.val.type}\n")
            sys.exit(1)
        node.type = "bool"
        return node.type

    def visit_exit(self, node):
        self.visit(node.value)
        t = node.value.type
        if t.startswith("lambda."):
            name = node.value.name if isinstance(node.value, varnode) else ('.'.join(node.value.chain) if isinstance(node.value, fieldaccessnode) else 'lambda')
            sys.stderr.write(f"compilation error: line {node.value.line}:{node.value.col}: '{name}' is a lambda and cannot be the value of exit: its type has no name\n")
            sys.exit(1)
        if self.current_member_fn is not None:
            expected_ret = self.current_member_fn.ret_type
            if t != expected_ret:
                sys.stderr.write(f"compilation error: line {node.line}:{node.col}: exit type {t} does not match function return type {expected_ret}\n")
                sys.exit(1)
        elif self.current_fn is not None:
            expected_ret = self.current_fn.ret_type
            if t != expected_ret:
                sys.stderr.write(f"compilation error: line {node.line}:{node.col}: exit type {t} does not match function return type {expected_ret}\n")
                sys.exit(1)
        else:
            if t not in ("i32", "i64", "bool"):
                sys.stderr.write(f"compilation error: line {node.line}:{node.col}: invalid exit type {t} at top level\n")
                sys.exit(1)

    def visit_binop(self, node):
        lt = self.visit(node.left)
        rt = self.visit(node.right)
        if node.op in ("+", "-", "*"):
            if lt not in ("i32", "i64") or rt not in ("i32", "i64"):
                sys.stderr.write(f"compilation error: line {node.line}:{node.col}: cannot apply '{node.op}' to {lt} and {rt}\n")
                sys.exit(1)
            node.type = "i64" if "i64" in (lt, rt) else "i32"
        else:
            if (lt == "bool" and rt != "bool") or (lt != "bool" and rt == "bool"):
                sys.stderr.write(f"compilation error: line {node.line}:{node.col}: cannot compare bool with {rt if lt == 'bool' else lt}\n")
                sys.exit(1)
            if lt in self.structs or rt in self.structs:
                sys.stderr.write(f"compilation error: line {node.line}:{node.col}: cannot compare struct type\n")
                sys.exit(1)
            node.type = "bool"
        return node.type

    def visit_const(self, node):
        val = int(node.value)
        if val <= 2147483647: node.type = "i32"
        elif val <= 9223372036854775807: node.type = "i64"
        else:
            sys.stderr.write(f"compilation error: line {node.line}:{node.col}: constant {node.value} does not fit in i64\n")
            sys.exit(1)
        return node.type

    def visit_bool(self, node):
        node.type = "bool"
        return node.type

    def visit_var(self, node):
        if self.current_lambda is not None and node.name == self.current_lambda.name:
            sys.stderr.write(f"compilation error: line {node.line}:{node.col}: lambda '{node.name}' cannot call itself\n")
            sys.exit(1)
        decl = None
        for scope in reversed(self.scopes):
            if node.name in scope:
                decl = scope[node.name]
                break
        if not decl:
            if self.current_struct is not None and node.name in self.structs[self.current_struct.name]:
                node.is_this_field = True
                fidx, ftype, fmut = self.structs[self.current_struct.name][node.name]
                node.field_index = fidx
                node.field_mut = fmut
                node.type = ftype
                return node.type
            if self.current_lambda is not None and node.name in self.enclosing_lambda_scopes:
                sys.stderr.write(f"compilation error: line {node.line}:{node.col}: '{node.name}' is not captured by lambda '{self.current_lambda.name}': add it to the capture list, [{node.name}]\n")
                sys.exit(1)
            sys.stderr.write(f"compilation error: line {node.line}:{node.col}: variable '{node.name}' is used before its declaration\n")
            sys.exit(1)
        node.decl = decl
        node.type = decl.type_name
        return node.type

    def visit_field_access(self, node):
        root_name = node.chain[0]
        decl = None
        for scope in reversed(self.scopes):
            if root_name in scope:
                decl = scope[root_name]
                break
        if not decl:
            if self.current_struct is not None and root_name in self.structs[self.current_struct.name]:
                node.is_this_field = True
                fidx, ftype, fmut = self.structs[self.current_struct.name][root_name]
                node.field_indices = [fidx]
                cur_type = ftype
                if cur_type.startswith("lambda."):
                    sys.stderr.write(f"compilation error: line {node.line}:{node.col}: '{root_name}' is a lambda: its captures are not visible outside its body\n")
                    sys.exit(1)
                for field_name in node.chain[1:]:
                    if cur_type not in self.structs:
                        sys.stderr.write(f"compilation error: line {node.line}:{node.col}: cannot access field '{field_name}' of non-struct type '{cur_type}'\n")
                        sys.exit(1)
                    st_fields = self.structs[cur_type]
                    if field_name not in st_fields:
                        sys.stderr.write(f"compilation error: line {node.line}:{node.col}: unknown field '{field_name}' in struct '{cur_type}'\n")
                        sys.exit(1)
                    sub_idx, sub_type, sub_mut = st_fields[field_name]
                    node.field_indices.append(sub_idx)
                    cur_type = sub_type
                    if cur_type.startswith("lambda."):
                        sys.stderr.write(f"compilation error: line {node.line}:{node.col}: '{field_name}' is a lambda: its captures are not visible outside its body\n")
                        sys.exit(1)
                node.type = cur_type
                return node.type
            if self.current_lambda is not None and root_name in self.enclosing_lambda_scopes:
                sys.stderr.write(f"compilation error: line {node.line}:{node.col}: '{root_name}' is not captured by lambda '{self.current_lambda.name}': add it to the capture list, [{root_name}]\n")
                sys.exit(1)
            sys.stderr.write(f"compilation error: line {node.line}:{node.col}: variable '{root_name}' is used before its declaration\n")
            sys.exit(1)

        cur_type = decl.type_name
        if cur_type.startswith("lambda."):
            sys.stderr.write(f"compilation error: line {node.line}:{node.col}: '{root_name}' is a lambda: its captures are not visible outside its body\n")
            sys.exit(1)
        node.decl = decl
        node.field_indices = []
        for field_name in node.chain[1:]:
            if cur_type not in self.structs:
                sys.stderr.write(f"compilation error: line {node.line}:{node.col}: cannot access field '{field_name}' of non-struct type '{cur_type}'\n")
                sys.exit(1)
            st_fields = self.structs[cur_type]
            if field_name not in st_fields:
                sys.stderr.write(f"compilation error: line {node.line}:{node.col}: unknown field '{field_name}' in struct '{cur_type}'\n")
                sys.exit(1)
            fidx, ftype, fmut = st_fields[field_name]
            node.field_indices.append(fidx)
            cur_type = ftype
            if cur_type.startswith("lambda."):
                sys.stderr.write(f"compilation error: line {node.line}:{node.col}: '{field_name}' is a lambda: its captures are not visible outside its body\n")
                sys.exit(1)

        node.type = cur_type
        return node.type

    def visit_call(self, node):
        if self.current_lambda is not None and node.name == self.current_lambda.name:
            sys.stderr.write(f"compilation error: line {node.line}:{node.col}: lambda '{node.name}' cannot call itself\n")
            sys.exit(1)

        v_decl = None
        for scope in reversed(self.scopes):
            if node.name in scope:
                v_decl = scope[node.name]
                break
        is_this_field = False
        if not v_decl and self.current_struct is not None and node.name in self.structs.get(self.current_struct.name, {}):
            is_this_field = True

        is_var = (v_decl is not None) or is_this_field
        is_member_fn = (self.current_struct is not None and node.name in self.struct_member_funcs.get(self.current_struct.name, {}))
        is_global_fn = (node.name in self.funcs)
        is_fn = is_member_fn or is_global_fn

        if is_var and is_fn:
            sys.stderr.write(f"compilation error: line {node.line}:{node.col}: '{node.name}' is both a variable and a function: rename one of them\n")
            sys.exit(1)

        if is_var:
            if is_this_field:
                fidx, ftype, fmut = self.structs[self.current_struct.name][node.name]
                v_type = ftype
                target = varnode(node.line, node.col, node.name)
                target.is_this_field = True
                target.field_index = fidx
                target.field_mut = fmut
                target.type = v_type
            else:
                v_type = v_decl.type_name
                target = varnode(node.line, node.col, node.name)
                target.decl = v_decl
                target.type = v_type

            if v_type in ("i32", "i64", "bool"):
                sys.stderr.write(f"compilation error: line {node.line}:{node.col}: '{node.name}' is not callable: it is {v_type}\n")
                sys.exit(1)
            if v_type not in self.structs or "call" not in self.struct_member_funcs.get(v_type, {}):
                sys.stderr.write(f"compilation error: line {node.line}:{node.col}: '{node.name}' is not callable: {v_type} has no member function 'call'\n")
                sys.exit(1)

            mf = self.struct_member_funcs[v_type]["call"]
            if len(node.args) != len(mf.params):
                sys.stderr.write(f"compilation error: line {node.line}:{node.col}: function '{node.name}' expects {len(mf.params)} arguments, got {len(node.args)}\n")
                sys.exit(1)

            for arg, (p_type, p_name, _, _) in zip(node.args, mf.params):
                self.visit(arg)
                if arg.type.startswith("lambda."):
                    arg_name = arg.name if isinstance(arg, varnode) else ('.'.join(arg.chain) if isinstance(arg, fieldaccessnode) else 'lambda')
                    sys.stderr.write(f"compilation error: line {arg.line}:{arg.col}: '{arg_name}' is a lambda and cannot be passed to '{node.name}': its type has no name, so no parameter can have it\n")
                    sys.exit(1)
                self.check_assignable(arg, p_type, arg, f"pass argument for '{p_name}'")

            node.__class__ = callablecallnode
            node.target = target
            node.method_name = "call"
            node.target_struct = v_type
            node.is_callable_call = True
            node.callable_name = node.name
            node.name = "call"
            node.type = mf.ret_type

            if self.current_member_fn:
                if is_this_field:
                    self.current_member_fn.calls_on_fields.append((v_type, "call"))

            self.all_member_calls.append((node, v_type, "call", target, self.current_member_fn))
            return node.type

        if is_member_fn:
            mf = self.struct_member_funcs[self.current_struct.name][node.name]
            node.is_this_member_call = True
            node.target_struct = self.current_struct.name
            if len(node.args) != len(mf.params):
                sys.stderr.write(f"compilation error: line {node.line}:{node.col}: function '{node.name}' expects {len(mf.params)} arguments, got {len(node.args)}\n")
                sys.exit(1)
            for arg, (p_type, p_name, _, _) in zip(node.args, mf.params):
                self.visit(arg)
                if arg.type.startswith("lambda."):
                    arg_name = arg.name if isinstance(arg, varnode) else ('.'.join(arg.chain) if isinstance(arg, fieldaccessnode) else 'lambda')
                    sys.stderr.write(f"compilation error: line {arg.line}:{arg.col}: '{arg_name}' is a lambda and cannot be passed to '{node.name}': its type has no name, so no parameter can have it\n")
                    sys.exit(1)
                self.check_assignable(arg, p_type, arg, f"pass argument for '{p_name}'")
            node.type = mf.ret_type
            if self.current_member_fn:
                self.current_member_fn.calls_on_this.append(node.name)
            self.all_member_calls.append((node, self.current_struct.name, node.name, None, self.current_member_fn))
            return node.type

        if is_global_fn:
            fn_sig = self.funcs[node.name]
            params = fn_sig["params"]
            if len(node.args) != len(params):
                sys.stderr.write(f"compilation error: line {node.line}:{node.col}: function '{node.name}' expects {len(params)} arguments, got {len(node.args)}\n")
                sys.exit(1)

            for arg, (p_type, p_name) in zip(node.args, params):
                self.visit(arg)
                if arg.type.startswith("lambda."):
                    arg_name = arg.name if isinstance(arg, varnode) else ('.'.join(arg.chain) if isinstance(arg, fieldaccessnode) else 'lambda')
                    sys.stderr.write(f"compilation error: line {arg.line}:{arg.col}: '{arg_name}' is a lambda and cannot be passed to '{node.name}': its type has no name, so no parameter can have it\n")
                    sys.exit(1)
                self.check_assignable(arg, p_type, arg, f"pass argument for '{p_name}'")

            node.type = fn_sig["ret_type"]
            node.fn_info = fn_sig
            return node.type

        if self.current_lambda is not None and node.name in self.enclosing_lambda_scopes:
            sys.stderr.write(f"compilation error: line {node.line}:{node.col}: '{node.name}' is not captured by lambda '{self.current_lambda.name}': add it to the capture list, [{node.name}]\n")
            sys.exit(1)

        sys.stderr.write(f"compilation error: line {node.line}:{node.col}: unknown function '{node.name}'\n")
        sys.exit(1)

    def visit_member_call(self, node):
        if isinstance(node.target, varnode):
            found = False
            for scope in reversed(self.scopes):
                if node.target.name in scope:
                    found = True
                    break
            if not found and self.current_struct is not None and node.target.name in self.structs[self.current_struct.name]:
                found = True
            if not found and node.target.name in self.structs:
                sys.stderr.write(f"compilation error: line {node.line}:{node.col}: cannot call member function '{node.name}' on type '{node.target.name}'\n")
                sys.exit(1)

        target_type = self.visit(node.target)
        if target_type.startswith("lambda."):
            root_name = node.target.name if isinstance(node.target, varnode) else node.target.chain[0]
            sys.stderr.write(f"compilation error: line {node.line}:{node.col}: '{root_name}' is a lambda: its captures are not visible outside its body\n")
            sys.exit(1)

        if target_type not in self.structs:
            sys.stderr.write(f"compilation error: line {node.line}:{node.col}: cannot call member function '{node.name}' on non-struct type '{target_type}'\n")
            sys.exit(1)

        is_field = node.name in self.structs[target_type]
        is_mf = node.name in self.struct_member_funcs[target_type]

        if is_field and is_mf:
            sys.stderr.write(f"compilation error: line {node.line}:{node.col}: '{node.name}' is both a field and a member function: rename one of them\n")
            sys.exit(1)

        if is_field:
            fidx, ftype, fmut = self.structs[target_type][node.name]
            if ftype in ("i32", "i64", "bool"):
                sys.stderr.write(f"compilation error: line {node.line}:{node.col}: '{node.name}' is not callable: it is {ftype}\n")
                sys.exit(1)
            if ftype not in self.structs or "call" not in self.struct_member_funcs.get(ftype, {}):
                sys.stderr.write(f"compilation error: line {node.line}:{node.col}: '{node.name}' is not callable: {ftype} has no member function 'call'\n")
                sys.exit(1)

            if isinstance(node.target, varnode):
                new_chain = [node.target.name, node.name]
                field_access = fieldaccessnode(node.line, node.col, new_chain)
                if hasattr(node.target, "is_this_field") and node.target.is_this_field:
                    field_access.is_this_field = True
                    field_access.field_indices = [node.target.field_index, fidx]
                else:
                    field_access.decl = node.target.decl
                    field_access.field_indices = [fidx]
            elif isinstance(node.target, fieldaccessnode):
                new_chain = node.target.chain + [node.name]
                field_access = fieldaccessnode(node.line, node.col, new_chain)
                if hasattr(node.target, "is_this_field") and node.target.is_this_field:
                    field_access.is_this_field = True
                    field_access.field_indices = node.target.field_indices + [fidx]
                else:
                    field_access.decl = node.target.decl
                    field_access.field_indices = node.target.field_indices + [fidx]
            else:
                field_access = fieldaccessnode(node.line, node.col, [node.name])
                field_access.field_indices = [fidx]
            field_access.type = ftype

            mf = self.struct_member_funcs[ftype]["call"]
            if len(node.args) != len(mf.params):
                sys.stderr.write(f"compilation error: line {node.line}:{node.col}: function '{node.name}' expects {len(mf.params)} arguments, got {len(node.args)}\n")
                sys.exit(1)

            for arg, (p_type, p_name, _, _) in zip(node.args, mf.params):
                self.visit(arg)
                if arg.type.startswith("lambda."):
                    arg_name = arg.name if isinstance(arg, varnode) else ('.'.join(arg.chain) if isinstance(arg, fieldaccessnode) else 'lambda')
                    sys.stderr.write(f"compilation error: line {arg.line}:{arg.col}: '{arg_name}' is a lambda and cannot be passed to '{node.name}': its type has no name, so no parameter can have it\n")
                    sys.exit(1)
                self.check_assignable(arg, p_type, arg, f"pass argument for '{p_name}'")

            orig_name = node.name
            node.__class__ = callablecallnode
            node.target = field_access
            node.method_name = "call"
            node.target_struct = ftype
            node.is_callable_call = True
            node.callable_name = orig_name
            node.name = "call"
            node.type = mf.ret_type

            if self.current_member_fn:
                self.current_member_fn.calls_on_fields.append((ftype, "call"))

            self.all_member_calls.append((node, ftype, "call", field_access, self.current_member_fn))
            return node.type

        if is_mf:
            mf = self.struct_member_funcs[target_type][node.name]
            if len(node.args) != len(mf.params):
                sys.stderr.write(f"compilation error: line {node.line}:{node.col}: member function '{node.name}' expects {len(mf.params)} arguments, got {len(node.args)}\n")
                sys.exit(1)

            for arg, (p_type, p_name, _, _) in zip(node.args, mf.params):
                self.visit(arg)
                if arg.type.startswith("lambda."):
                    arg_name = arg.name if isinstance(arg, varnode) else ('.'.join(arg.chain) if isinstance(arg, fieldaccessnode) else 'lambda')
                    sys.stderr.write(f"compilation error: line {arg.line}:{arg.col}: '{arg_name}' is a lambda and cannot be passed to '{node.name}': its type has no name, so no parameter can have it\n")
                    sys.exit(1)
                self.check_assignable(arg, p_type, arg, f"pass argument for '{p_name}'")

            node.type = mf.ret_type
            node.target_struct = target_type

            if self.current_member_fn:
                if isinstance(node.target, varnode) and hasattr(node.target, "is_this_field") and node.target.is_this_field:
                    self.current_member_fn.calls_on_fields.append((target_type, node.name))
                elif isinstance(node.target, fieldaccessnode) and hasattr(node.target, "is_this_field") and node.target.is_this_field:
                    self.current_member_fn.calls_on_fields.append((target_type, node.name))

            self.all_member_calls.append((node, target_type, node.name, node.target, self.current_member_fn))
            return node.type

        sys.stderr.write(f"compilation error: line {node.line}:{node.col}: struct '{target_type}' has no member function '{node.name}'\n")
        sys.exit(1)


    def visit(self, node):
        if isinstance(node, binopnode): return self.visit_binop(node)
        elif isinstance(node, constnode): return self.visit_const(node)
        elif isinstance(node, boolnode): return self.visit_bool(node)
        elif isinstance(node, varnode): return self.visit_var(node)
        elif isinstance(node, fieldaccessnode): return self.visit_field_access(node)
        elif isinstance(node, callnode): return self.visit_call(node)
        elif isinstance(node, membercallnode): return self.visit_member_call(node)
        elif isinstance(node, readnode): return node.type
        elif isinstance(node, notnode): return self.visit_not(node)

    def check_assignable(self, expr, want, at, what):
        have = expr.type
        if have == want or (have == "i32" and want == "i64"): return
        if want == "i32" and isinstance(expr, constnode) and int(expr.value) > 2147483647:
            sys.stderr.write(f"compilation error: line {expr.line}:{expr.col}: constant {expr.value} does not fit in i32\n")
            sys.exit(1)
        sys.stderr.write(f"compilation error: line {at.line}:{at.col}: cannot {what} of type {want} with a value of type {have}\n")
        sys.exit(1)


class codegenerator:
    def __init__(self, module):
        self.module = module
        self.struct_ir_types = {}
        self.struct_nodes = {}
        self.func_ir = {}
        self.member_func_ir = {}
        self.syms = {}
        self.current_func = None
        self.current_struct = None
        self.current_this_ptr = None
        self.entry_bb = None
        self.builder = None
        self.str_constants = {}
        
        self.printf = ir.Function(self.module, ir.FunctionType(i32, [ir.PointerType(i8)], var_arg=True), name="printf")
        self.scanf = ir.Function(self.module, ir.FunctionType(i32, [ir.PointerType(i8)], var_arg=True), name="scanf")
        
        txt_read = b"%d\0"
        self.fmt_read = ir.GlobalVariable(self.module, ir.ArrayType(i8, len(txt_read)), name="fmt_read")
        self.fmt_read.linkage, self.fmt_read.global_constant = "private", True
        self.fmt_read.initializer = ir.Constant(ir.ArrayType(i8, len(txt_read)), bytearray(txt_read))

        txt_int = b"Program exit with result %lld\n\0"
        self.fmt_int = ir.GlobalVariable(self.module, ir.ArrayType(i8, len(txt_int)), name="fmt_int")
        self.fmt_int.linkage, self.fmt_int.global_constant = "private", True
        self.fmt_int.initializer = ir.Constant(ir.ArrayType(i8, len(txt_int)), bytearray(txt_int))
        
        txt_str = b"Program exit with result %s\n\0"
        self.fmt_str = ir.GlobalVariable(self.module, ir.ArrayType(i8, len(txt_str)), name="fmt_str")
        self.fmt_str.linkage, self.fmt_str.global_constant = "private", True
        self.fmt_str.initializer = ir.Constant(ir.ArrayType(i8, len(txt_str)), bytearray(txt_str))
        
        str_t = b"true\0"
        self.str_true = ir.GlobalVariable(self.module, ir.ArrayType(i8, len(str_t)), name="str_true")
        self.str_true.linkage, self.str_true.global_constant = "private", True
        self.str_true.initializer = ir.Constant(ir.ArrayType(i8, len(str_t)), bytearray(str_t))
        
        str_f = b"false\0"
        self.str_false = ir.GlobalVariable(self.module, ir.ArrayType(i8, len(str_f)), name="str_false")
        self.str_false.linkage, self.str_false.global_constant = "private", True
        self.str_false.initializer = ir.Constant(ir.ArrayType(i8, len(str_f)), bytearray(str_f))

    def get_str_constant(self, text):
        if text not in self.str_constants:
            b = text.encode("utf-8") + b"\0"
            name = f"str_const_{len(self.str_constants)}"
            gv = ir.GlobalVariable(self.module, ir.ArrayType(i8, len(b)), name=name)
            gv.linkage, gv.global_constant = "private", True
            gv.initializer = ir.Constant(ir.ArrayType(i8, len(b)), bytearray(b))
            self.str_constants[text] = gv
        return self.str_constants[text]

    def call_printf_str(self, text):
        gv = self.get_str_constant(text)
        fmt = self.get_str_constant("%s")
        self.builder.call(self.printf, [
            self.builder.bitcast(fmt, ir.PointerType(i8)),
            self.builder.bitcast(gv, ir.PointerType(i8))
        ])

    def type_to_ir(self, t):
        if t == "i64": return i64
        if t == "i32": return i32
        if t == "bool": return i1
        if t in self.struct_ir_types:
            return self.struct_ir_types[t]
        raise ValueError(f"unknown type {t}")

    def alloca_entry(self, name, type):
        old = self.builder.block
        self.builder.position_at_start(self.entry_bb)
        ptr = self.builder.alloca(type, name=name)
        self.builder.position_at_end(old)
        return ptr

    def coerce(self, value, have, want):
        if have == "i32" and (want == "i64" or want == i64):
            return self.builder.sext(value, i64, name="wide")
        return value

    def gen_program(self, node):
        for s in node.structs:
            st = self.module.context.get_identified_type(s.name)
            self.struct_ir_types[s.name] = st
            self.struct_nodes[s.name] = s
            
        for s in node.structs:
            element_types = [self.type_to_ir(f.type_name) for f in s.fields]
            self.struct_ir_types[s.name].set_body(*element_types)

        for s in node.structs:
            st_ptr_ty = ir.PointerType(self.struct_ir_types[s.name])
            for mf in s.member_funcs:
                param_types = [st_ptr_ty] + [self.type_to_ir(p[0]) for p in mf.params]
                ret_type = self.type_to_ir(mf.ret_type)
                fn_ty = ir.FunctionType(ret_type, param_types)
                fn = ir.Function(self.module, fn_ty, name=f"{s.name}_{mf.name}")
                self.member_func_ir[(s.name, mf.name)] = fn

        for f in node.funcs:
            param_types = [self.type_to_ir(p[0]) for p in f.params]
            ret_type = self.type_to_ir(f.ret_type)
            fn_ty = ir.FunctionType(ret_type, param_types)
            fn = ir.Function(self.module, fn_ty, name=f"user_{f.name}")
            self.func_ir[f.name] = fn

        for s in node.structs:
            for mf in s.member_funcs:
                self.gen_member_function(s, mf)

        for f in node.funcs:
            self.gen_user_function(f)

        main_fn = ir.Function(self.module, ir.FunctionType(i32, []), name="main")
        self.current_func = main_fn
        self.current_struct = None
        self.current_this_ptr = None
        self.entry_bb = main_fn.append_basic_block("entry")
        self.builder = ir.IRBuilder(self.entry_bb)

        for s in node.stmts:
            if isinstance(s, declnode): self.gen_decl(s)
            elif isinstance(s, assignnode): self.gen_assign(s)
            elif isinstance(s, ifnode): self.gen_if(s)
            elif isinstance(s, whilenode): self.gen_while(s)
            elif isinstance(s, lambdanode): self.gen_decl(s.rewritten_decl)
            elif isinstance(s, printnode): self.gen_print(s)
        self.gen_exit(node.exit_node)

    def gen_member_function(self, s, mf):
        fn = self.member_func_ir[(s.name, mf.name)]
        self.current_func = fn
        self.current_struct = s
        self.entry_bb = fn.append_basic_block("entry")
        self.builder = ir.IRBuilder(self.entry_bb)

        this_arg = fn.args[0]
        this_arg.name = "this"
        self.current_this_ptr = this_arg

        for idx, (p_type, p_name, _, _) in enumerate(mf.params):
            arg_val = fn.args[idx + 1]
            arg_val.name = p_name
            t_ir = self.type_to_ir(p_type)
            slot = self.alloca_entry(f"{p_name}.slot", t_ir)
            self.builder.store(arg_val, slot)
            p_decl = mf.saved_param_scope[p_name] if hasattr(mf, 'saved_param_scope') else None
            self.syms[p_decl] = slot

        self.gen_block(mf.body)

    def gen_user_function(self, f):
        fn = self.func_ir[f.name]
        self.current_func = fn
        self.entry_bb = fn.append_basic_block("entry")
        self.builder = ir.IRBuilder(self.entry_bb)

        for idx, (p_type, p_name, _, _) in enumerate(f.params):
            arg_val = fn.args[idx]
            arg_val.name = p_name
            t_ir = self.type_to_ir(p_type)
            slot = self.alloca_entry(f"{p_name}.slot", t_ir)
            self.builder.store(arg_val, slot)
            p_decl = f.body_scope[p_name] if hasattr(f, 'body_scope') else None
            self.syms[p_decl] = slot

        self.gen_block(f.body)

    def gen_while(self, node):
        cond_bb = self.current_func.append_basic_block("while.cond")
        body_bb = self.current_func.append_basic_block("while.body")
        merge_bb = self.current_func.append_basic_block("while.merge")

        self.builder.branch(cond_bb)
        self.builder.position_at_end(cond_bb)
        cond = self.gen_expr(node.cond)
        self.builder.cbranch(cond, body_bb, merge_bb)

        self.builder.position_at_end(body_bb)
        self.gen_block(node.body)
        if not self.builder.block.is_terminated:
            self.builder.branch(cond_bb)

        self.builder.position_at_end(merge_bb)

    def gen_block(self, node):
        for s in node.stmts:
            if isinstance(s, declnode): self.gen_decl(s)
            elif isinstance(s, assignnode): self.gen_assign(s)
            elif isinstance(s, ifnode): self.gen_if(s)
            elif isinstance(s, whilenode): self.gen_while(s)
            elif isinstance(s, lambdanode): self.gen_decl(s.rewritten_decl)
            elif isinstance(s, printnode): self.gen_print(s)
        if node.ex: self.gen_exit(node.ex)

    def gen_print(self, node):
        arg = node.arg
        if isinstance(arg, stringnode):
            str_gv = self.get_str_constant(arg.value)
            fmt = self.get_str_constant("%s\n")
            self.builder.call(self.printf, [
                self.builder.bitcast(fmt, ir.PointerType(i8)),
                self.builder.bitcast(str_gv, ir.PointerType(i8))
            ])
        elif arg.type == "i32":
            v = self.gen_expr(arg)
            fmt = self.get_str_constant("%d\n")
            self.builder.call(self.printf, [
                self.builder.bitcast(fmt, ir.PointerType(i8)),
                v
            ])
        elif arg.type == "i64":
            v = self.gen_expr(arg)
            fmt = self.get_str_constant("%lld\n")
            self.builder.call(self.printf, [
                self.builder.bitcast(fmt, ir.PointerType(i8)),
                v
            ])
        elif arg.type == "bool":
            v = self.gen_expr(arg)
            sel = self.builder.select(
                v,
                self.builder.bitcast(self.str_true, ir.PointerType(i8)),
                self.builder.bitcast(self.str_false, ir.PointerType(i8))
            )
            fmt = self.get_str_constant("%s\n")
            self.builder.call(self.printf, [
                self.builder.bitcast(fmt, ir.PointerType(i8)),
                sel
            ])
        else:
            st_name = arg.type
            if isinstance(arg, varnode):
                if hasattr(arg, "is_this_field") and arg.is_this_field:
                    ptr = self.builder.gep(self.current_this_ptr, [ir.Constant(i32, 0), ir.Constant(i32, arg.field_index)])
                else:
                    ptr = self.syms[arg.decl]
            elif isinstance(arg, fieldaccessnode):
                if hasattr(arg, "is_this_field") and arg.is_this_field:
                    base_ptr = self.current_this_ptr
                else:
                    base_ptr = self.syms[arg.decl]
                gep_indices = [ir.Constant(i32, 0)] + [ir.Constant(i32, idx) for idx in arg.field_indices]
                ptr = self.builder.gep(base_ptr, gep_indices)
            else:
                val = self.gen_expr(arg)
                ptr = self.alloca_entry("print_struct_tmp", self.struct_ir_types[st_name])
                self.builder.store(val, ptr)
            self.gen_print_struct(st_name, ptr, is_root=True)

    def gen_print_struct(self, st_name, struct_ptr, is_root=False):
        st_node = self.struct_nodes[st_name]
        self.call_printf_str(f"{st_name}{{")
        for idx, f in enumerate(st_node.fields):
            if idx > 0:
                self.call_printf_str(f", {f.name}: ")
            else:
                self.call_printf_str(f"{f.name}: ")
            
            f_gep = self.builder.gep(struct_ptr, [ir.Constant(i32, 0), ir.Constant(i32, idx)])
            if f.type_name == "i32":
                val = self.builder.load(f_gep)
                fmt = self.get_str_constant("%d")
                self.builder.call(self.printf, [self.builder.bitcast(fmt, ir.PointerType(i8)), val])
            elif f.type_name == "i64":
                val = self.builder.load(f_gep)
                fmt = self.get_str_constant("%lld")
                self.builder.call(self.printf, [self.builder.bitcast(fmt, ir.PointerType(i8)), val])
            elif f.type_name == "bool":
                val = self.builder.load(f_gep)
                sel = self.builder.select(
                    val,
                    self.builder.bitcast(self.str_true, ir.PointerType(i8)),
                    self.builder.bitcast(self.str_false, ir.PointerType(i8))
                )
                fmt = self.get_str_constant("%s")
                self.builder.call(self.printf, [self.builder.bitcast(fmt, ir.PointerType(i8)), sel])
            else:
                self.gen_print_struct(f.type_name, f_gep, is_root=False)
                
        if is_root:
            self.call_printf_str("}\n")
        else:
            self.call_printf_str("}")

    def gen_if(self, node):
        cond = self.gen_expr(node.cond)
        then_bb = self.current_func.append_basic_block("then")
        merge_bb = self.current_func.append_basic_block("merge")
        else_bb = self.current_func.append_basic_block("else") if node.else_block else None
        
        self.builder.cbranch(cond, then_bb, else_bb or merge_bb)
        
        self.builder.position_at_end(then_bb)
        self.gen_block(node.then_block)
        if not self.builder.block.is_terminated:
            self.builder.branch(merge_bb)
            
        if node.else_block:
            self.builder.position_at_end(else_bb)
            self.gen_block(node.else_block)
            if not self.builder.block.is_terminated:
                self.builder.branch(merge_bb)
                
        self.builder.position_at_end(merge_bb)

    def gen_decl(self, node):
        t_ir = self.type_to_ir(node.type_name)
        ptr = self.alloca_entry(node.name, t_ir)
        self.syms[node] = ptr

        if node.type_name in ("i32", "i64", "bool"):
            val = self.gen_expr(node.inits[0])
            val = self.coerce(val, node.inits[0].type, node.type_name)
            self.builder.store(val, ptr)
        else:
            if len(node.inits) == 1 and node.inits[0].type == node.type_name:
                val = self.gen_expr(node.inits[0])
                self.builder.store(val, ptr)
            else:
                for idx, init_expr in enumerate(node.inits):
                    val = self.gen_expr(init_expr)
                    val = self.coerce(val, init_expr.type, self.get_field_type(node.type_name, idx))
                    field_ptr = self.builder.gep(ptr, [ir.Constant(i32, 0), ir.Constant(i32, idx)])
                    self.builder.store(val, field_ptr)

    def get_field_type(self, struct_name, idx):
        st_ir = self.struct_ir_types[struct_name]
        return st_ir.elements[idx]

    def gen_assign(self, node):
        if hasattr(node, "is_this_field") and node.is_this_field:
            base_ptr = self.current_this_ptr
            gep_indices = [ir.Constant(i32, 0)] + [ir.Constant(i32, idx) for idx in node.field_indices]
            field_ptr = self.builder.gep(base_ptr, gep_indices)
            val = self.gen_expr(node.value)
            val = self.coerce(val, node.value.type, node.target_type)
            self.builder.store(val, field_ptr)
            return

        base_ptr = self.syms[node.decl]
        if not node.field_indices:
            val = self.gen_expr(node.value)
            val = self.coerce(val, node.value.type, node.decl.type_name)
            self.builder.store(val, base_ptr)
        else:
            gep_indices = [ir.Constant(i32, 0)] + [ir.Constant(i32, idx) for idx in node.field_indices]
            field_ptr = self.builder.gep(base_ptr, gep_indices)
            val = self.gen_expr(node.value)
            val = self.coerce(val, node.value.type, node.target_type)
            self.builder.store(val, field_ptr)

    def gen_exit(self, node):
        val = self.gen_expr(node.value)
        if self.current_func.name != "main":
            self.builder.ret(val)
        else:
            if node.value.type in ("i32", "i64"):
                val = self.coerce(val, node.value.type, "i64")
                ptr = self.builder.bitcast(self.fmt_int, ir.PointerType(i8))
                self.builder.call(self.printf, [ptr, val])
            else:
                sel = self.builder.select(val, self.builder.bitcast(self.str_true, ir.PointerType(i8)), self.builder.bitcast(self.str_false, ir.PointerType(i8)))
                ptr = self.builder.bitcast(self.fmt_str, ir.PointerType(i8))
                self.builder.call(self.printf, [ptr, sel])
            self.builder.ret(ir.Constant(i32, 0))

    def gen_expr(self, node):
        if isinstance(node, binopnode):
            l = self.gen_expr(node.left)
            r = self.gen_expr(node.right)
            
            if node.op in ("==", "!="):
                if node.left.type != "bool" or node.right.type != "bool":
                    w = "i64" if "i64" in (node.left.type, node.right.type) else "i32"
                    l = self.coerce(l, node.left.type, w)
                    r = self.coerce(r, node.right.type, w)
                return self.builder.icmp_signed(node.op, l, r)
            
            w = node.type
            l = self.coerce(l, node.left.type, w)
            r = self.coerce(r, node.right.type, w)
            if node.op == "+": return self.builder.add(l, r)
            elif node.op == "-": return self.builder.sub(l, r)
            elif node.op == "*": return self.builder.mul(l, r)
            
        elif isinstance(node, constnode):
            return ir.Constant(self.type_to_ir(node.type), int(node.value))
        elif isinstance(node, boolnode):
            return ir.Constant(i1, 1 if node.value == "true" else 0)
        elif isinstance(node, notnode):
            val = self.gen_expr(node.val)
            return self.builder.not_(val)
        elif isinstance(node, varnode):
            if hasattr(node, "is_this_field") and node.is_this_field:
                f_ptr = self.builder.gep(self.current_this_ptr, [ir.Constant(i32, 0), ir.Constant(i32, node.field_index)])
                return self.builder.load(f_ptr)
            ptr = self.syms[node.decl]
            return self.builder.load(ptr)
        elif isinstance(node, fieldaccessnode):
            if hasattr(node, "is_this_field") and node.is_this_field:
                base_ptr = self.current_this_ptr
            else:
                base_ptr = self.syms[node.decl]
            gep_indices = [ir.Constant(i32, 0)] + [ir.Constant(i32, idx) for idx in node.field_indices]
            f_ptr = self.builder.gep(base_ptr, gep_indices)
            return self.builder.load(f_ptr)
        elif isinstance(node, callnode):
            if hasattr(node, "is_this_member_call") and node.is_this_member_call:
                fn = self.member_func_ir[(node.target_struct, node.name)]
                mf_sig = self.struct_nodes[node.target_struct].member_funcs
                target_mf = next(m for m in mf_sig if m.name == node.name)
                arg_vals = [self.current_this_ptr]
                for arg_node, (p_type, p_name, _, _) in zip(node.args, target_mf.params):
                    v = self.gen_expr(arg_node)
                    v = self.coerce(v, arg_node.type, p_type)
                    arg_vals.append(v)
                return self.builder.call(fn, arg_vals)

            fn = self.func_ir[node.name]
            callee_params = node.fn_info["params"]
            arg_vals = []
            for arg_node, (p_type, p_name) in zip(node.args, callee_params):
                v = self.gen_expr(arg_node)
                v = self.coerce(v, arg_node.type, p_type)
                arg_vals.append(v)
            return self.builder.call(fn, arg_vals)
        elif isinstance(node, membercallnode):
            fn = self.member_func_ir[(node.target_struct, node.name)]
            if isinstance(node.target, varnode):
                if hasattr(node.target, "is_this_field") and node.target.is_this_field:
                    this_target_ptr = self.builder.gep(self.current_this_ptr, [ir.Constant(i32, 0), ir.Constant(i32, node.target.field_index)])
                else:
                    this_target_ptr = self.syms[node.target.decl]
            elif isinstance(node.target, fieldaccessnode):
                if hasattr(node.target, "is_this_field") and node.target.is_this_field:
                    base_ptr = self.current_this_ptr
                else:
                    base_ptr = self.syms[node.target.decl]
                gep_indices = [ir.Constant(i32, 0)] + [ir.Constant(i32, idx) for idx in node.target.field_indices]
                this_target_ptr = self.builder.gep(base_ptr, gep_indices)
            else:
                this_target_ptr = self.current_this_ptr

            target_mf = next(m for m in self.struct_nodes[node.target_struct].member_funcs if m.name == node.name)
            arg_vals = [this_target_ptr]
            for arg_node, (p_type, p_name, _, _) in zip(node.args, target_mf.params):
                v = self.gen_expr(arg_node)
                v = self.coerce(v, arg_node.type, p_type)
                arg_vals.append(v)
            return self.builder.call(fn, arg_vals)
        elif isinstance(node, readnode):
            slot = self.alloca_entry("read.slot", i32)
            fmt = self.builder.bitcast(self.fmt_read, ir.PointerType(i8))
            self.builder.call(self.scanf, [fmt, slot])
            return self.builder.load(slot)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.stderr.write("compilation error: missing input file\n")
        sys.exit(1)
    ast_mode = False
    ast_checked_mode = False
    inp = None
    out_file = "output.ll"
    
    idx = 1
    while idx < len(sys.argv):
        arg = sys.argv[idx]
        if arg == "--ast":
            ast_mode = True
        elif arg == "--ast-checked":
            ast_checked_mode = True
        elif inp is None:
            inp = arg
        else:
            out_file = arg
        idx += 1

    if inp is None:
        sys.stderr.write("compilation error: missing input file\n")
        sys.exit(1)
    
    try:
        with open(inp, "rb") as f: data = f.read()
    except Exception as e:
        sys.stderr.write(f"compilation error: cannot open '{inp}'\n")
        sys.exit(1)
    
    tree = parser(lex(data)).parse_program()
    if ast_mode:
        tree.dump()
        sys.exit(0)

    sc = semanticchecker()
    sc.visit_program(tree)

    if ast_checked_mode:
        tree.dump()
        sys.exit(0)

    for s in tree.structs:
        for mf in s.member_funcs:
            mf.body_scope = mf.saved_param_scope if hasattr(mf, 'saved_param_scope') else {}

    for f in tree.funcs:
        f.body_scope = f.saved_param_scope if hasattr(f, 'saved_param_scope') else {}

    m = ir.Module(name="practice8")
    m.triple = llvm.get_default_triple()
    
    cg = codegenerator(m)
    cg.gen_program(tree)
    
    with open(out_file, 'w') as f:
        f.write(str(m))
