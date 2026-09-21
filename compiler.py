import sys
from llvmlite import ir
import llvmlite.binding as llvm

i32, i8 = ir.IntType(32), ir.IntType(8)

class token:
    def __init__(self, k, t, l, c): self.kind, self.text, self.line, self.col = k, t, l, c

def lex(data: bytes):
    lines, tokens = [], []
    state, start, line, col, i = "start", 0, 1, 1, 0
    kws = {"i32": "typename", "mut": "specifier", "exit": "keyword"}
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
            elif b == 58: state = "assign"
            else:
                sys.stderr.write(f"compilation error: line {line}:{col}: bad byte '{chr(b)}'\n")
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
    def codegen(self, b, syms, p, f):
        for s in self.stmts: s.codegen(b, syms)
        self.exit_node.codegen(b, syms, p, f)

class declnode:
    def __init__(self, l, c, n, m, i): self.line, self.col, self.name, self.mut, self.init = l, c, n, m, i
    def dump(self, ind=""):
        print(ind + f"decl {self.name} {'mut' if self.mut else 'const'}")
        self.init.dump(ind + "  ")
    def codegen(self, b, syms):
        if self.name in syms:
            sys.stderr.write(f"compilation error: line {self.line}:{self.col}: already declared\n")
            sys.exit(1)
        ptr = b.alloca(i32, name=self.name)
        syms[self.name] = {"ptr": ptr, "mut": self.mut}
        b.store(self.init.codegen(b, syms), ptr)

class assignnode:
    def __init__(self, l, c, n, v): self.line, self.col, self.name, self.value = l, c, n, v
    def dump(self, ind=""):
        print(ind + f"assign {self.name}"); self.value.dump(ind + "  ")
    def codegen(self, b, syms):
        if self.name not in syms:
            sys.stderr.write(f"compilation error: line {self.line}:{self.col}: not declared\n")
            sys.exit(1)
        if not syms[self.name]["mut"]:
            sys.stderr.write(f"compilation error: line {self.line}:{self.col}: not mut\n")
            sys.exit(1)
        b.store(self.value.codegen(b, syms), syms[self.name]["ptr"])

class exitnode:
    def __init__(self, l, c, v): self.line, self.col, self.value = l, c, v
    def dump(self, ind=""):
        print(ind + "exit"); self.value.dump(ind + "  ")
    def codegen(self, b, syms, p, f):
        v = self.value.codegen(b, syms)
        ptr = b.bitcast(f, ir.PointerType(i8))
        b.call(p, [ptr, v])
        b.ret(ir.Constant(i32, 0))

class binopnode:
    def __init__(self, l, c, o, left, right): self.line, self.col, self.op, self.left, self.right = l, c, o, left, right
    def dump(self, ind=""):
        print(ind + f"binop {self.op}"); self.left.dump(ind + "  "); self.right.dump(ind + "  ")
    def codegen(self, b, syms):
        l, r = self.left.codegen(b, syms), self.right.codegen(b, syms)
        if self.op == "+": return b.add(l, r)
        elif self.op == "-": return b.sub(l, r)
        elif self.op == "*": return b.mul(l, r)

class varnode:
    def __init__(self, l, c, n): self.line, self.col, self.name = l, c, n
    def dump(self, ind=""): print(ind + f"var {self.name}")
    def codegen(self, b, syms):
        if self.name not in syms:
            sys.stderr.write(f"compilation error: line {self.line}:{self.col}: not declared\n")
            sys.exit(1)
        return b.load(syms[self.name]["ptr"])

class constnode:
    def __init__(self, l, c, v): self.line, self.col, self.value = l, c, v
    def dump(self, ind=""): print(ind + f"const {self.value}")
    def codegen(self, b, syms): return ir.Constant(i32, int(self.value))

class parser:
    def __init__(self, lines): self.lines, self.toks, self.pos = lines, [], 0
    def peek(self): return self.toks[self.pos] if self.pos < len(self.toks) else None
    def eat(self):
        t = self.toks[self.pos]; self.pos += 1
        return t
    def err(self, l, c, m):
        sys.stderr.write(f"compilation error: line {l}:{c}: {m}\n")
        sys.exit(1)
    def exp(self, k, m):
        t = self.peek()
        if not t or t.kind != k: self.err(t.line if t else 0, t.col if t else 0, f"expected {m}")
        return self.eat()
    
    def parse_program(self):
        stmts, ex = [], None
        for toks in self.lines:
            if not toks: continue
            self.toks, self.pos = toks, 0
            t = self.peek()
            if t and t.kind == "keyword" and t.text == "exit": ex = self.parse_exit()
            else: stmts.append(self.parse_statement())
            if self.peek(): self.err(self.peek().line, self.peek().col, "junk at end")
        if not ex: self.err(0, 0, "no exit")
        return programnode(stmts, ex)

    def parse_statement(self):
        t = self.peek()
        if t and t.text == "i32": return self.parse_decl()
        elif t and t.kind == "identifier": return self.parse_assign()
        else: self.err(t.line if t else 0, t.col if t else 0, "bad statement")

    def parse_decl(self):
        self.eat(); mut = False
        if self.peek() and self.peek().text == "mut": mut = True; self.eat()
        n = self.exp("identifier", "name")
        self.exp("block_start", "{")
        i = self.parse_expr()
        self.exp("block_end", "}")
        return declnode(n.line, n.col, n.text, mut, i)

    def parse_assign(self):
        n = self.exp("identifier", "name")
        o = self.exp("operator", ":=")
        if o.text != ":=": self.err(o.line, o.col, "need :=")
        return assignnode(n.line, n.col, n.text, self.parse_expr())

    def parse_exit(self):
        e = self.eat()
        return exitnode(e.line, e.col, self.parse_factor())

    def parse_expr(self):
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
        if not t: self.err(0, 0, "need val")
        if t.kind == "constant": return constnode(self.eat().line, t.col, t.text)
        if t.kind == "identifier": return varnode(self.eat().line, t.col, t.text)
        self.err(t.line, t.col, "bad val")

if __name__ == "__main__":
    ast_mode = sys.argv[1] == "--ast"
    inp = sys.argv[2] if ast_mode else sys.argv[1]
    
    with open(inp, "rb") as f: data = f.read()
    
    tree = parser(lex(data)).parse_program()
    
    if ast_mode:
        tree.dump()
        sys.exit(0)
        
    m = ir.Module(name="practice3")
    m.triple = llvm.get_default_triple()
    main = ir.Function(m, ir.FunctionType(i32, []), name="main")
    b = ir.IRBuilder(main.append_basic_block("entry"))
    pf = ir.Function(m, ir.FunctionType(i32, [ir.PointerType(i8)], var_arg=True), name="printf")
    txt = b"program exit with result %d\n\0"
    fmt = ir.GlobalVariable(m, ir.ArrayType(i8, len(txt)), name="fmt")
    fmt.linkage, fmt.global_constant = "private", True
    fmt.initializer = ir.Constant(ir.ArrayType(i8, len(txt)), bytearray(txt))
    
    tree.codegen(b, {}, pf, fmt)
    open(sys.argv[2], 'w').write(str(m))