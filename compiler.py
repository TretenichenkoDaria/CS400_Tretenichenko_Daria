import sys
from llvmlite import ir
import llvmlite.binding as llvm
I32, I8 = ir.IntType(32), ir.IntType(8)
module = ir.Module(name="practice1")
module.triple = llvm.get_default_triple() # otherwise llc: "unable to get targe>
main = ir.Function(module, ir.FunctionType(I32, []), name="main")
builder = ir.IRBuilder(main.append_basic_block("entry"))
printf = ir.Function(module, ir.FunctionType(I32, [ir.PointerType(I8)], var_arg>
 name="printf") # declaration only
text = b"Program exit with result %d\n\0"
fmt = ir.GlobalVariable(module, ir.ArrayType(I8, len(text)), name="fmt")
fmt.linkage, fmt.global_constant = "private", True
fmt.initializer = ir.Constant(ir.ArrayType(I8, len(text)), bytearray(text))

lines = open(sys.argv[1]).readlines()

symbols = {}

def input(val):
    if val.isdigit():
        return ir.Constant(I32, int(val))
    elif val not in symbols:
        sys.stderr.write("comp err")
        sys.exit(1)
    return builder.load(symbols[val])

for line in lines:
    l = (line.strip()).split()

    if len(l) == 0:
        continue
    
    if l[0] == "int":
        if len(l) < 2 or l[1] in symbols:
            sys.stderr.write("comp err")
            sys.exit(1)
        symbols[l[1]] = builder.alloca(I32, name=l[1])

    elif l[0] == "exit":
        if len(l) > 2 or l[1] not in symbols:
            sys.stderr.write("comp err")
            sys.exit(1)
        ptr = builder.bitcast(fmt, ir.PointerType(I8))
        val = builder.load(symbols[l[1]])
        builder.call(printf, [ptr, val])
        builder.ret(ir.Constant(I32, 0))
        break

    elif len(l) >= 3 and l[1] == ":=":
        name = l[0]
        if name not in symbols:
            sys.stderr.write("comp err")
            sys.exit(1)
        elif len(l) == 3:
            val = input(l[2])
            builder.store(val, symbols[name])
        elif len(l) == 5:
            val1 = input(l[2])
            val2 = input(l[4])
            sign = l[3]
            if sign == "+":
                res = builder.add(val1, val2)
            elif sign == "-":
                res = builder.sub(val1, val2)
            elif sign == "*":
                res = builder.mul(val1, val2)
            else:
                sys.stderr.write("comp err")
                sys.exit(1)

            builder.store(res, symbols[name])
        
        else:
            sys.stderr.write("comp err")
            sys.exit(1)

    else: 
        sys.stderr.write("comp err")
        sys.exit(1)

open(sys.argv[2], 'w').write(str(module))