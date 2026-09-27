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
    kws = {"i32": "typename", "i64": "typename", "bool": "typename", "mut": "specifier", "exit": "keyword", "true": "boolean", "false": "boolean"}
    br = False

    while i <= len(data):
        b = data[i] if i < len(data) else None
        if state == "start":
            if b is None:
                if br:
                    sys.stderr.write(f"compilation error: line {line}:{col}: no closing '}}'\n")
                    sys.exit(1)
                break
            if b in (32, 9): pass
            elif 65 <= b <= 90 or 97 <= b <= 122 or b == 95: state, start = "ident", i
            elif 48 <= b <= 57: state, start = "number", i
            elif b == 10:
                if br:
                    sys.stderr.write(f"compilation error: line {line}:{col}: no closing '}}'\n")
                    sys.exit(1)
                if tokens: lines.append(tokens)
                tokens, line, col = [], line + 1, 0
            elif b == 123:
                tokens.append(token("block_start", "{", line, col)); br = True
            elif b == 125:
                tokens.append(token("block_end", "}", line, col)); br = False
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
                sys.stderr.write(f"compilation error: line {line}:{col}: expected '=='\n")
                sys.exit(1)
        elif state == "neq1":
            if b == 61:
                tokens.append(token("operator", "!=", line, col - 1)); state = "start"
            else:
                sys.stderr.write(f"compilation error: line {line}:{col}: expected '='\n")
                sys.exit(1)
        elif state == "assign":
            if b == 61:
                tokens.append(token("operator", ":=", line, col - 1)); state = "start"
            else:
                sys.stderr.write(f"compilation error: line {line}:{col}: expected '='\n")
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
    def __init__(self, lines): self.lines, self.toks, self.pos = lines, [], 0
    def peek(self): return self.toks[self.pos] if self.pos < len(self.toks) else None
    def eat(self):
        t = self.toks[self.pos]; self.pos += 1
        return t
    def exp(self, k, m):
        t = self.peek()
        if not t or t.kind != k:
            sys.stderr.write(f"compilation error: line {t.line if t else 0}:{t.col if t else 0}: expected {m}\n")
            sys.exit(1)
        return self.eat()
    
    def parse_program(self):
        stmts, ex = [], None
        for toks in self.lines:
            if not toks: continue
            self.toks, self.pos = toks, 0
            t = self.peek()
            if t and t.kind == "keyword" and t.text == "exit": ex = self.parse_exit()
            else: stmts.append(self.parse_statement())
            if self.peek():
                sys.stderr.write(f"compilation error: line {self.peek().line}:{self.peek().col}: junk at end\n")
                sys.exit(1)
        if not ex:
            sys.stderr.write("compilation error: line 0:0: no exit\n")
            sys.exit(1)
        return programnode(stmts, ex)

    def parse_statement(self):
        t = self.peek()
        if t and t.text in ("i32", "i64", "bool"): return self.parse_decl()
        elif t and t.kind == "identifier": return self.parse_assign()
        else:
            sys.stderr.write(f"compilation error: line {t.line if t else 0}:{t.col if t else 0}: bad statement\n")
            sys.exit(1)

    def parse_decl(self):
        t = self.eat()
        mut = False
        if self.peek() and self.peek().text == "mut": mut = True; self.eat()
        n = self.exp("identifier", "name")
        self.exp("block_start", "{")
        i = self.parse_expr()
        self.exp("block_end", "}")
        return declnode(n.line, n.col, t.text, n.text, mut, i)

    def parse_assign(self):
        n = self.exp("identifier", "name")
        o = self.exp("operator", ":=")
        if o.text != ":=":
            sys.stderr.write(f"compilation error: line {o.line}:{o.col}: need :=\n")
            sys.exit(1)
        return assignnode(n.line, n.col, n.text, self.parse_expr())

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
            sys.stderr.write("compilation error: line 0:0: need val\n")
            sys.exit(1)
        if t.kind == "constant": return constnode(self.eat().line, t.col, t.text)
        if t.kind == "boolean": return boolnode(self.eat().line, t.col, t.text)
        if t.kind == "identifier": return varnode(self.eat().line, t.col, t.text)
        sys.stderr.write(f"compilation error: line {t.line}:{t.col}: bad val\n")
        sys.exit(1)

class semanticchecker:
    def __init__(self):
        self.symbols = {}

    def visit(self, node):
        if isinstance(node, binopnode): return self.visit_binop(node)
        elif isinstance(node, constnode): return self.visit_const(node)
        elif isinstance(node, boolnode): return self.visit_bool(node)
        elif isinstance(node, varnode): return self.visit_var(node)

    def visit_program(self, node):
        for s in node.stmts:
            if isinstance(s, declnode): self.visit_decl(s)
            elif isinstance(s, assignnode): self.visit_assign(s)
        self.visit_exit(node.exit_node)

    def visit_decl(self, node):
        if node.name in self.symbols:
            sys.stderr.write(f"compilation error: line {node.line}:{node.col}: already declared\n")
            sys.exit(1)
        self.visit(node.init)
        self.check_assignable(node.init, node.type_name, node, f"initialise '{node.name}'")
        node.type = node.type_name
        self.symbols[node.name] = node

    def visit_assign(self, node):
        if node.name not in self.symbols:
            sys.stderr.write(f"compilation error: line {node.line}:{node.col}: used before declaration\n")
            sys.exit(1)
        decl = self.symbols[node.name]
        if not decl.mut:
            sys.stderr.write(f"compilation error: line {node.line}:{node.col}: not mut\n")
            sys.exit(1)
        self.visit(node.value)
        self.check_assignable(node.value, decl.type_name, node, f"assign to '{node.name}'")
        node.decl = decl

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
        if node.name not in self.symbols:
            sys.stderr.write(f"compilation error: line {node.line}:{node.col}: used before declaration\n")
            sys.exit(1)
        node.decl = self.symbols[node.name]
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
        self.builder = ir.IRBuilder(self.main.append_basic_block("entry"))
        self.syms = {}
        self.printf = ir.Function(self.module, ir.FunctionType(i32, [ir.PointerType(i8)], var_arg=True), name="printf")
        
        txt_int = b"program exit with result %lld\n\0"
        self.fmt_int = ir.GlobalVariable(self.module, ir.ArrayType(i8, len(txt_int)), name="fmt_int")
        self.fmt_int.linkage, self.fmt_int.global_constant = "private", True
        self.fmt_int.initializer = ir.Constant(ir.ArrayType(i8, len(txt_int)), bytearray(txt_int))
        
        txt_str = b"%s\n\0"
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
        self.gen_exit(node.exit_node)

    def gen_decl(self, node):
        t = self.type_to_ir(node.type_name)
        ptr = self.builder.alloca(t, name=node.name)
        self.syms[node.name] = ptr
        val = self.gen_expr(node.init)
        val = self.coerce(val, node.init.type, node.type_name)
        self.builder.store(val, ptr)

    def gen_assign(self, node):
        ptr = self.syms[node.name]
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
        elif isinstance(node, varnode):
            return self.builder.load(self.syms[node.name])

if __name__ == "__main__":
    ast_mode = sys.argv[1] == "--ast"
    inp = sys.argv[2] if ast_mode else sys.argv[1]
    
    with open(inp, "rb") as f: data = f.read()
    
    tree = parser(lex(data)).parse_program()
    semanticchecker().visit_program(tree)
    
    if ast_mode:
        tree.dump()
        sys.exit(0)
        
    m = ir.Module(name="practice4")
    m.triple = llvm.get_default_triple()
    
    cg = codegenerator(m)
    cg.gen_program(tree)
    
    open(sys.argv[2] if not ast_mode else "out.ll", 'w').write(str(m))