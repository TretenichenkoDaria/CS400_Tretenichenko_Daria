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
    kws = {
        "i32": "typename", "i64": "typename", "bool": "typename",
        "mut": "specifier", "exit": "keyword",
        "true": "boolean", "false": "boolean",
        "if": "keyword", "else": "keyword",
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
            elif b == 10:
                if tokens: lines.append(tokens)
                tokens, line, col = [], line + 1, 0
            elif b in (123, 125):
                tokens.append(token("brace", chr(b), line, col))
            elif b in (40, 41):
                tokens.append(token("paren", chr(b), line, col))
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
    def __init__(self, l, c, name, fields):
        self.line, self.col, self.name, self.fields = l, c, name, fields
    def dump(self, ind=""):
        print(ind + f"struct {self.name}")
        for f in self.fields: f.dump(ind + "  ")

class fielddeclnode:
    def __init__(self, l, c, type_name, mut, name):
        self.line, self.col, self.type_name, self.mut, self.name = l, c, type_name, mut, name
    def dump(self, ind=""):
        print(ind + f"field {self.name} {self.type_name} {'mut' if self.mut else 'const'}")

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

class blocknode:
    def __init__(self, l, c, stmts, ex): 
        self.line, self.col, self.stmts, self.ex = l, c, stmts, ex
    def dump(self, ind=""):
        print(ind + "block")
        for s in self.stmts: s.dump(ind + "  ")
        if self.ex: self.ex.dump(ind + "  ")

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
        while self.lpos < len(self.lines):
            t = self.peek()
            if t and t.text == "}":
                break
            f_type = self.parse_type()
            mut = False
            if self.peek() and self.peek().text == "mut":
                mut = True
                self.eat()
            f_name = self.exp("identifier", "field name")
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

        return structnode(st.line, st.col, name_t.text, fields)

    def parse_fn(self):
        fn_kw = self.eat()
        name_t = self.exp("identifier", "function name")
        self.exp(":=", "':='")
        self.exp("(", "'('")

        params = []
        if self.peek() and self.peek().text != ")":
            p_type = self.parse_type()
            p_name = self.exp("identifier", "parameter name")
            params.append((p_type, p_name.text, p_name.line, p_name.col))
            while self.peek() and self.peek().text == ",":
                self.eat()
                p_type = self.parse_type()
                p_name = self.exp("identifier", "parameter name")
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
        if t and (t.text in ("i32", "i64", "bool") or (t.kind == "identifier" and self.is_decl_start())):
            s = self.parse_decl()
            self.check_eol()
            return s
        elif t and t.kind == "identifier":
            s = self.parse_assign()
            self.check_eol()
            return s
        elif t and t.text == "if":
            return self.parse_if()
        elif t and t.text == "else":
            sys.stderr.write(f"compilation error: line {t.line}:{t.col}: 'else' without an 'if'\n")
            sys.exit(1)
        elif t and t.text in ("struct", "fn"):
            sys.stderr.write(f"compilation error: line {t.line}:{t.col}: {t.text} declared inside function or after statement\n")
            sys.exit(1)
        else:
            l = t.line if t else self.ll
            c = t.col if t else self.lc + 1
            sys.stderr.write(f"compilation error: line {l}:{c}: bad statement\n")
            sys.exit(1)

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
        chain = [n.text]
        while self.peek() and self.peek().text == ".":
            self.eat()
            fld = self.exp("identifier", "field")
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
            else_b = self.parse_block()
            
        return ifnode(i.line, i.col, cond, then_b, else_b)

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
        if t.text == "!":
            op = self.eat()
            return notnode(op.line, op.col, self.parse_factor())
        if t.kind == "constant": return constnode(self.eat().line, t.col, t.text)
        if t.kind == "boolean": return boolnode(self.eat().line, t.col, t.text)
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
                chain = [id_t.text]
                while self.peek() and self.peek().text == ".":
                    self.eat()
                    f_name = self.exp("identifier", "field")
                    chain.append(f_name.text)
                return fieldaccessnode(id_t.line, id_t.col, chain)
            return varnode(id_t.line, id_t.col, id_t.text)

        sys.stderr.write(f"compilation error: line {t.line}:{t.col}: bad val\n")
        sys.exit(1)


class semanticchecker:
    def __init__(self):
        self.structs = {}
        self.struct_nodes = {}
        self.funcs = {}
        self.scopes = [{}]
        self.current_fn = None

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
        for s in node.structs:
            if s.name in ("i32", "i64", "bool"):
                sys.stderr.write(f"compilation error: line {s.line}:{s.col}: cannot redeclare built-in type '{s.name}'\n")
                sys.exit(1)
            if s.name in self.structs:
                sys.stderr.write(f"compilation error: line {s.line}:{s.col}: struct '{s.name}' already declared\n")
                sys.exit(1)
            fields_map = {}
            for idx, f in enumerate(s.fields):
                if f.name in fields_map:
                    sys.stderr.write(f"compilation error: line {f.line}:{f.col}: field '{f.name}' already declared in struct '{s.name}'\n")
                    sys.exit(1)
                if not self.is_type_known(f.type_name):
                    sys.stderr.write(f"compilation error: line {f.line}:{f.col}: unknown type '{f.type_name}' in struct '{s.name}'\n")
                    sys.exit(1)
                if f.type_name == s.name:
                    sys.stderr.write(f"compilation error: line {f.line}:{f.col}: struct '{s.name}' cannot contain itself\n")
                    sys.exit(1)
                fields_map[f.name] = (idx, f.type_name, f.mut)
            self.structs[s.name] = fields_map
            self.struct_nodes[s.name] = s

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

        self.scopes = [{}]
        self.current_fn = None
        for s in node.stmts:
            if isinstance(s, declnode): self.visit_decl(s)
            elif isinstance(s, assignnode): self.visit_assign(s)
            elif isinstance(s, ifnode): self.visit_if(s)
        self.visit_exit(node.exit_node)

    def visit_block(self, node, is_fn_body=False):
        if not is_fn_body:
            self.scopes.append({})
        for s in node.stmts:
            if isinstance(s, declnode): self.visit_decl(s)
            elif isinstance(s, assignnode): self.visit_assign(s)
            elif isinstance(s, ifnode): self.visit_if(s)
        if node.ex: self.visit_exit(node.ex)
        if not is_fn_body:
            self.scopes.pop()

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
            self.check_assignable(node.inits[0], t_name, node.inits[0], f"initialise '{node.name}'")
        else:
            st_fields = list(self.structs[t_name].items())
            if len(node.inits) == 1 and node.inits[0].type == t_name:
                pass
            elif len(node.inits) == 1 and self.visit(node.inits[0]) == t_name:
                pass
            else:
                if len(node.inits) != len(st_fields):
                    sys.stderr.write(f"compilation error: line {node.line}:{node.col}: wrong number of values in {{}}: expected {len(st_fields)}, got {len(node.inits)}\n")
                    sys.exit(1)
                for init_expr, (fname, (fidx, ftype, fmut)) in zip(node.inits, st_fields):
                    self.visit(init_expr)
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
            self.check_assignable(node.value, decl.type_name, node.value, f"assign to '{root_name}'")
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
            self.check_assignable(node.value, cur_type, node.value, f"assign to field '{'.'.join(node.target)}'")
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
        if self.current_fn is not None:
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
        decl = None
        for scope in reversed(self.scopes):
            if node.name in scope:
                decl = scope[node.name]
                break
        if not decl:
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
            sys.stderr.write(f"compilation error: line {node.line}:{node.col}: variable '{root_name}' is used before its declaration\n")
            sys.exit(1)

        cur_type = decl.type_name
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

        node.type = cur_type
        return node.type

    def visit_call(self, node):
        if node.name not in self.funcs:
            sys.stderr.write(f"compilation error: line {node.line}:{node.col}: unknown function '{node.name}'\n")
            sys.exit(1)
        fn_sig = self.funcs[node.name]
        params = fn_sig["params"]
        if len(node.args) != len(params):
            sys.stderr.write(f"compilation error: line {node.line}:{node.col}: function '{node.name}' expects {len(params)} arguments, got {len(node.args)}\n")
            sys.exit(1)

        for arg, (p_type, p_name) in zip(node.args, params):
            self.visit(arg)
            self.check_assignable(arg, p_type, arg, f"pass argument for '{p_name}'")

        node.type = fn_sig["ret_type"]
        node.fn_info = fn_sig
        return node.type

    def visit(self, node):
        if isinstance(node, binopnode): return self.visit_binop(node)
        elif isinstance(node, constnode): return self.visit_const(node)
        elif isinstance(node, boolnode): return self.visit_bool(node)
        elif isinstance(node, varnode): return self.visit_var(node)
        elif isinstance(node, fieldaccessnode): return self.visit_field_access(node)
        elif isinstance(node, callnode): return self.visit_call(node)
        elif isinstance(node, notnode): return self.visit_not(node)

    def check_assignable(self, expr, want, at, what):
        have = expr.type
        if have == want or (have == "i32" and want == "i64"): return
        sys.stderr.write(f"compilation error: line {at.line}:{at.col}: cannot {what} of type {want} with a value of type {have}\n")
        sys.exit(1)


class codegenerator:
    def __init__(self, module):
        self.module = module
        self.struct_ir_types = {}
        self.func_ir = {}
        self.syms = {}
        self.current_func = None
        self.entry_bb = None
        self.builder = None
        
        self.printf = ir.Function(self.module, ir.FunctionType(i32, [ir.PointerType(i8)], var_arg=True), name="printf")
        
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
        if have == "i32" and want == "i64":
            return self.builder.sext(value, i64, name="wide")
        return value

    def gen_program(self, node):
        for s in node.structs:
            st = self.module.context.get_identified_type(s.name)
            self.struct_ir_types[s.name] = st
            
        for s in node.structs:
            element_types = [self.type_to_ir(f.type_name) for f in s.fields]
            self.struct_ir_types[s.name].set_body(*element_types)

        for f in node.funcs:
            param_types = [self.type_to_ir(p[0]) for p in f.params]
            ret_type = self.type_to_ir(f.ret_type)
            fn_ty = ir.FunctionType(ret_type, param_types)
            fn = ir.Function(self.module, fn_ty, name=f"user_{f.name}")
            self.func_ir[f.name] = fn

        for f in node.funcs:
            self.gen_user_function(f)

        main_fn = ir.Function(self.module, ir.FunctionType(i32, []), name="main")
        self.current_func = main_fn
        self.entry_bb = main_fn.append_basic_block("entry")
        self.builder = ir.IRBuilder(self.entry_bb)

        for s in node.stmts:
            if isinstance(s, declnode): self.gen_decl(s)
            elif isinstance(s, assignnode): self.gen_assign(s)
            elif isinstance(s, ifnode): self.gen_if(s)
        self.gen_exit(node.exit_node)

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

    def gen_block(self, node):
        for s in node.stmts:
            if isinstance(s, declnode): self.gen_decl(s)
            elif isinstance(s, assignnode): self.gen_assign(s)
            elif isinstance(s, ifnode): self.gen_if(s)
        if node.ex: self.gen_exit(node.ex)

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
            ptr = self.syms[node.decl]
            return self.builder.load(ptr)
        elif isinstance(node, fieldaccessnode):
            base_ptr = self.syms[node.decl]
            gep_indices = [ir.Constant(i32, 0)] + [ir.Constant(i32, idx) for idx in node.field_indices]
            f_ptr = self.builder.gep(base_ptr, gep_indices)
            return self.builder.load(f_ptr)
        elif isinstance(node, callnode):
            fn = self.func_ir[node.name]
            callee_params = node.fn_info["params"]
            arg_vals = []
            for arg_node, (p_type, p_name) in zip(node.args, callee_params):
                v = self.gen_expr(arg_node)
                v = self.coerce(v, arg_node.type, p_type)
                arg_vals.append(v)
            return self.builder.call(fn, arg_vals)

if __name__ == "__main__":
    ast_mode = sys.argv[1] == "--ast"
    inp = sys.argv[2] if ast_mode else sys.argv[1]
    
    with open(inp, "rb") as f: data = f.read()
    
    tree = parser(lex(data)).parse_program()
    sc = semanticchecker()
    sc.visit_program(tree)

    for f in tree.funcs:
        f.body_scope = f.saved_param_scope if hasattr(f, 'saved_param_scope') else {}

    if ast_mode:
        tree.dump()
        sys.exit(0)
        
    m = ir.Module(name="practice6")
    m.triple = llvm.get_default_triple()
    
    cg = codegenerator(m)
    cg.gen_program(tree)
    
    out_file = sys.argv[2] if not ast_mode else "out.ll"
    with open(out_file, 'w') as f:
        f.write(str(m))
