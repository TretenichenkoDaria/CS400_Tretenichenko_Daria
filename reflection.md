1. Describe the features or idioms covered by the course that you think to be the most useful.

The most useful concept turned out to be simplifying complex code into basic constructs prior to code generation (desugaring). For instance, in compiler.py, anonymous functions are simply transformed into standard structures. Their fields store captured variables, and a call method is added to them. Thanks to this, we didn't have to construct complex closures or function pointers in LLVM IR; we simply leveraged the existing logic for handling structures and methods from the codegenerator.

2. Which features were not covered properly?

Currently, in compiler.py (for example, in parser.exp or semanticchecker.visit_assign), any syntax error or type mismatch simply crashes the program via sys.exit(1). The compiler cannot continue past the first error to collect all of them at once. 

3. Provide at least 3 examples related to languages and compilers that surprised you most.

1. It turns out you cannot simply remove all unused variables and functions in a single pass. Removing one element might render something else unused as well. Therefore, it is necessary to iterate through the usecounter repeatedly until there is nothing left to remove .
2. To verify whether a method modifies a constant object, looking at the method itself is not enough. In semanticchecker.visit_program, one must traverse the entire chain of method calls to ensure that no mutations occur anywhere along the path
3. To output a structure to the screen, the compiler does not need to know the structure's name at all. It simply iterates over the fields using builder.gep and formats them into LLVM IR on the fly, without being tightly coupled to any specific structure types.
4. I was surprised how easily lexer.py and the ebnf grammar could be modified to accept emoji tokens, mapping them to standard ast nodes without breaking the semantic pass.

4. Which concepts (idioms) or approaches are still not clear enough?

It is still difficult to grasp the distinction between data types within the language itself and the C ABI specifications for various platforms. When passing structures to external functions, one must adhere to the rules of the specific architecture (e.g., x86-64 or ARM64). In these cases, small structures might be packed into registers or memory in complex ways—a process that differs significantly from how we pass parameters field-by-field within our own LLVM IR.

5. Other ideas and suggestions related to the course content.

It would be great to add more examples and code demonstrating on pairs. If we talk about the course in general, the presence check on pairs is unuseful to me. Also, would like to hear more real-life examples of compilers and how they work, their architecture, etc.