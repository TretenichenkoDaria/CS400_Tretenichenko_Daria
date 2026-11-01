# Optimizations

A variable that only feeds itself (such as `k := k + 1` with nobody else reading `k`) survives optimization: its right-hand side contains a read that counts towards its use. This is a limit of simple use/reference counting, not a bug.

When the optimization pass unlinks an unused subtree:
- **Compiler Implementation Language**: Python (CPython).
- **Memory Model**: CPython uses reference counting supplemented by a cyclic garbage collector. When all references to an object drop to zero, its memory is freed immediately.
- **Parent Pointers**: The AST nodes in this compiler do not keep pointers back to their parent nodes. Because there are no parent pointers, there are no reference cycles between AST nodes. If parent pointers were kept, each parent-child pair would form a cyclic reference (`parent -> child -> parent`), preventing immediate deallocation via reference counting and requiring a full cycle collection.
- **Measurement**: Creating a weak reference `ref = weakref.ref(node)` to an unlinked AST node before the pass completes shows that `ref()` evaluates to `None` immediately after the unlinking iteration finishes (even without calling `gc.collect()`), confirming the removed subtree is freed deterministically as soon as it is unlinked.

Note that this pertains strictly to the compiler's memory, not the compiled program's binary: the target language has no heap yet, so nothing is dynamically freed in the emitted binary.

