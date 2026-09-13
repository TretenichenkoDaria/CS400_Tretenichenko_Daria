import sys

class token:
    def __init__(self, kind, text, line, col):
        self.kind = kind
        self.text = text
        self.line = line
        self.col = col

def lex(data: bytes):
    lines = []
    tokens = []
    state = "start"
    start = 0
    line = 1
    col = 1
    i = 0
    keywords = {"i32": "typename", "mut": "specifier", "exit": "keyword"}

    while i <= len(data):
        b = data[i] if i < len(data) else None
        
        if state == "start":
            if b is None:
                break
            elif b in (32, 9):
                pass
            elif 65 <= b <= 90 or 97 <= b <= 122 or b == 95:
                state = "ident"
                start = i
            elif 48 <= b <= 57:
                state = "number"
                start = i
            elif b == 10:
                if tokens:
                    lines.append(tokens)
                tokens = []
                line += 1
                col = 0
            elif b == 123:
                tokens.append(token("block_start", "{", line, col))
            elif b == 125:
                tokens.append(token("block_end", "}", line, col))
            elif b in (43, 45, 42):
                tokens.append(token("operator", chr(b), line, col))
            elif b == 58:
                state = "assign"
            elif b == 61:
                print(f"comp err")
                sys.exit(1)
            else:
                print(f"comp err")
                sys.exit(1)
                
        elif state == "assign":
            if b == 61:
                tokens.append(token("operator", ":=", line, col - 1))
                state = "start"
            else:
                print(f"comp err")
                sys.exit(1)

        elif state == "ident":
            if b is not None and (65 <= b <= 90 or 97 <= b <= 122 or b == 95 or 48 <= b <= 57):
                pass
            else:
                word = data[start:i].decode("ascii")
                kind = keywords.get(word, "identifier")
                tokens.append(token(kind, word, line, col - (i - start)))
                state = "start"
                continue
                
        elif state == "number":
            if b is not None and (48 <= b <= 57):
                pass
            elif b is not None and (65 <= b <= 90 or 97 <= b <= 122 or b == 95):
                print(f"comp err")
                sys.exit(1)
            else:
                word = data[start:i].decode("ascii")
                tokens.append(token("constant", word, line, col - (i - start)))
                state = "start"
                continue
                
        i += 1
        col += 1
        
    if tokens:
        lines.append(tokens)
        
    return lines

if __name__ == "__main__":
    with open(sys.argv[1], "rb") as f:
        data = f.read()
    
    token_lines = lex(data)
    
    for t_line in token_lines:
        for t in t_line:
            print(f"({t.text}, {t.kind})", end=" ")
        print()