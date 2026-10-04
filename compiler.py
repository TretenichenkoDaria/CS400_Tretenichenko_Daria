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
    kws = {"i32": "typename", "i64": "typename", "bool": "typename", "mut": "specifier", "exit": "keyword", "true": "boolean", "false": "boolean", "if": "keyword", "else": "keyword"}

    while i <= len(data):
        b = data[i] if i < len(data) else None
        if state == "start":
            if b is None:
                break
            if b in (32, 9): pass
            elif 65 <= b <= 90 or 97 <= b <= 122 or b == 95: state, start = "ident", i
            elif 48 <= b <= 57: state, start = "number", i
            elif b == 10:
                if tokens: lines.append(tokens)
                tokens, line, col = [], line + 1, 0
            elif b in (123, 125):
                tokens.append(token("brace", chr(b), line, col))
            elif b in (43, 45, 42): tokens.append(token("operator", chr(b), line, col))
            elif b == 61: state = "eq1"
            elif b == 33: state = "neq1"
            elif b == 58: state = "assign"
            else:
                sys.stderr.write(f"compilation error: line {line}:{col}: bad byte '{chr(b)}'\n")
                sys.exit(1)
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
    def __init__(self, s, e): self.stmts, self.exit_node = s, e
    def dump(self, ind=""):
        print(ind + "program")
        for s in self.stmts: s.dump(ind + "  ")
        self.exit_node.dump(ind + "  ")

class declnode:
    def __init__(self, l, c, t, n, m, i): 
        self.line, self.col, self.type_name, self.name, self.mut, self.init = l, c, t, n, m, i
        self.type = None
    def dump(self, ind=""):
        print(ind + f"decl {self.name} {self.type_name} {'mut' if self.mut else 'const'}")
        self.init.dump(ind + "  ")

class assignnode:
    def __init__(self, l, c, n, v): 
        self.line, self.col, self.name, self.value = l, c, n, v
        self.decl = None
    def dump(self, ind=""):
        print(ind + f"assign {self.name}"); self.value.dump(ind + "  ")

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
        if not t or t.kind != k:
            l = t.line if t else self.ll
            c = t.col if t else self.lc + 1
            sys.stderr.write(f"compilation error: line {l}:{c}: expected {m}\n")
            sys.exit(1)
        return self.eat()

    def parse_program(self):
        stmts, ex = [], None
        while self.lpos < len(self.lines):
            t = self.peek()
            if ex:
                sys.stderr.write(f"compilation error: line {t.line}:{t.col}: unreachable code\n")
                sys.exit(1)
            if t and t.kind == "keyword" and t.text == "exit": 
                ex = self.parse_exit()
                self.check_eol()
            else: 
                stmts.append(self.parse_statement())
                
        if not ex:
            l = self.ll if self.ll else 0
            c = self.lc if self.lc else 0
            sys.stderr.write(f"compilation error: line {l}:{c}: no exit\n")
            sys.exit(1)
        return programnode(stmts, ex)

    def parse_statement(self):
        t = self.peek()
        if t and t.text in ("i32", "i64", "bool"):
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
        else:
            l = t.line if t else self.ll
            c = t.col if t else self.lc + 1
            sys.stderr.write(f"compilation error: line {l}:{c}: bad statement\n")
            sys.exit(1)

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
        
        i = self.parse_expr()
        
        b2 = self.peek()
        if not b2 or b2.text != "}":
            l = b2.line if b2 else self.ll
            c = b2.col if b2 else self.lc + 1
            sys.stderr.write(f"compilation error: line {l}:{c}: expected '}}'\n")
            sys.exit(1)
        self.eat()
        
        return declnode(n.line, n.col, t.text, n.text, mut, i)

    def parse_assign(self):
        n = self.exp("identifier", "name")
        o = self.exp("operator", ":=")
        if o.text != ":=":
            sys.stderr.write(f"compilation error: line {o.line}:{o.col}: need :=\n")
            sys.exit(1)
        return assignnode(n.line, n.col, n.text, self.parse_expr())

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
        if t.kind == "identifier": return varnode(self.eat().line, t.col, t.text)
        sys.stderr.write(f"compilation error: line {t.line}:{t.col}: bad val\n")
        sys.exit(1)

class semanticchecker:
    def __init__(self):
        self.scopes = [{}]

    def visit(self, node):
        if isinstance(node, binopnode): return self.visit_binop(node)
        elif isinstance(node, constnode): return self.visit_const(node)
        elif isinstance(node, boolnode): return self.visit_bool(node)
        elif isinstance(node, varnode): return self.visit_var(node)
        elif isinstance(node, notnode): return self.visit_not(node)

    def visit_program(self, node):
        for s in node.stmts:
            if isinstance(s, declnode): self.visit_decl(s)
            elif isinstance(s, assignnode): self.visit_assign(s)
            elif isinstance(s, ifnode): self.visit_if(s)
        self.visit_exit(node.exit_node)

    def visit_block(self, node):
        self.scopes.append({})
        for s in node.stmts:
            if isinstance(s, declnode): self.visit_decl(s)
            elif isinstance(s, assignnode): self.visit_assign(s)
            elif isinstance(s, ifnode): self.visit_if(s)
        if node.ex: self.visit_exit(node.ex)
        self.scopes.pop()

    def visit_decl(self, node):
        if node.name in self.scopes[-1]:
            sys.stderr.write(f"compilation error: line {node.line}:{node.col}: variable '{node.name}' is already declared in this block\n")
            sys.exit(1)
        self.visit(node.init)
        self.check_assignable(node.init, node.type_name, node.init, f"initialise '{node.name}'")
        node.type = node.type_name
        self.scopes[-1][node.name] = node

    def visit_assign(self, node):
        decl = None
        for scope in reversed(self.scopes):
            if node.name in scope:
                decl = scope[node.name]
                break
        if not decl:
            sys.stderr.write(f"compilation error: line {node.line}:{node.col}: variable '{node.name}' is used before its declaration\n")
            sys.exit(1)
        if not decl.mut:
            sys.stderr.write(f"compilation error: line {node.line}:{node.col}: not mut\n")
            sys.exit(1)
        self.visit(node.value)
        self.check_assignable(node.value, decl.type_name, node.value, f"assign to '{node.name}'")
        node.decl = decl

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
        if t not in ("i32", "i64", "bool"):
            sys.stderr.write(f"compilation error: line {node.line}:{node.col}: invalid exit type\n")
            sys.exit(1)

    def visit_binop(self, node):
        lt = self.visit(node.left)
        rt = self.visit(node.right)
        if node.op in ("+", "-", "*"):
            if lt == "bool" or rt == "bool":
                sys.stderr.write(f"compilation error: line {node.line}:{node.col}: cannot apply '{node.op}' to bool\n")
                sys.exit(1)
            node.type = "i64" if "i64" in (lt, rt) else "i32"
        else:
            if (lt == "bool" and rt != "bool") or (lt != "bool" and rt == "bool"):
                sys.stderr.write(f"compilation error: line {node.line}:{node.col}: cannot compare bool with {rt if lt == 'bool' else lt}\n")
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
        node.type = node.decl.type_name
        return node.type

    def check_assignable(self, expr, want, at, what):
        have = expr.type
        if have == want or (have == "i32" and want == "i64"): return
        sys.stderr.write(f"compilation error: line {at.line}:{at.col}: cannot {what} of type {want} with a value of type {have}\n")
        sys.exit(1)

class codegenerator:
    def __init__(self, module):
        self.module = module
        self.main = ir.Function(self.module, ir.FunctionType(i32, []), name="main")
        self.entry_bb = self.main.append_basic_block("entry")
        self.builder = ir.IRBuilder(self.entry_bb)
        self.syms = {}
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

    def type_to_ir(self, t):
        if t == "i64": return i64
        if t == "i32": return i32
        if t == "bool": return i1
        return i32

    def gen_program(self, node):
        for s in node.stmts:
            if isinstance(s, declnode): self.gen_decl(s)
            elif isinstance(s, assignnode): self.gen_assign(s)
            elif isinstance(s, ifnode): self.gen_if(s)
        self.gen_exit(node.exit_node)

    def gen_block(self, node):
        for s in node.stmts:
            if isinstance(s, declnode): self.gen_decl(s)
            elif isinstance(s, assignnode): self.gen_assign(s)
            elif isinstance(s, ifnode): self.gen_if(s)
        if node.ex: self.gen_exit(node.ex)

    def gen_if(self, node):
        cond = self.gen_expr(node.cond)
        then_bb = self.main.append_basic_block("then")
        merge_bb = self.main.append_basic_block("merge")
        else_bb = self.main.append_basic_block("else") if node.else_block else None
        
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
        t = self.type_to_ir(node.type_name)
        ptr = self.alloca_entry(node.name, t)
        val = self.gen_expr(node.init)
        val = self.coerce(val, node.init.type, node.type_name)
        self.builder.store(val, ptr)
        self.syms[node] = ptr

    def gen_assign(self, node):
        ptr = self.syms[node.decl]
        val = self.gen_expr(node.value)
        val = self.coerce(val, node.value.type, node.decl.type_name)
        self.builder.store(val, ptr)

    def gen_exit(self, node):
        val = self.gen_expr(node.value)
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
            return self.builder.load(self.syms[node.decl])

if __name__ == "__main__":
    ast_mode = sys.argv[1] == "--ast"
    inp = sys.argv[2] if ast_mode else sys.argv[1]
    
    with open(inp, "rb") as f: data = f.read()
    
    tree = parser(lex(data)).parse_program()
    semanticchecker().visit_program(tree)
    
    if ast_mode:
        tree.dump()
        sys.exit(0)
        
    m = ir.Module(name="practice5")
    m.triple = llvm.get_default_triple()
    
    cg = codegenerator(m)
    cg.gen_program(tree)
    
    open(sys.argv[2] if not ast_mode else "out.ll", 'w').write(str(m))