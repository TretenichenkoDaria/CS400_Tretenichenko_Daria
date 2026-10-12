; ModuleID = "practice6"
target triple = "x86_64-apple-darwin24.6.0"
target datalayout = ""

%"Point" = type {i32, i32}
%"Circle" = type {%"Point", i32}
declare i32 @"printf"(i8* %".1", ...)

@"fmt_int" = private constant [31 x i8] c"Program exit with result %lld\0a\00"
@"fmt_str" = private constant [29 x i8] c"Program exit with result %s\0a\00"
@"str_true" = private constant [5 x i8] c"true\00"
@"str_false" = private constant [6 x i8] c"false\00"
define i32 @"user_add"(i32 %"a", i32 %"b")
{
entry:
  %"sum" = alloca i32
  %"b.slot" = alloca i32
  %"a.slot" = alloca i32
  store i32 %"a", i32* %"a.slot"
  store i32 %"b", i32* %"b.slot"
  %".6" = load i32, i32* %"a.slot"
  %".7" = load i32, i32* %"b.slot"
  %".8" = add i32 %".6", %".7"
  store i32 %".8", i32* %"sum"
  %".10" = load i32, i32* %"sum"
  ret i32 %".10"
}

define i1 @"user_isXZero"(%"Point" %"p")
{
entry:
  %"zero" = alloca i1
  %"p.slot" = alloca %"Point"
  store %"Point" %"p", %"Point"* %"p.slot"
  %".4" = getelementptr %"Point", %"Point"* %"p.slot", i32 0, i32 0
  %".5" = load i32, i32* %".4"
  %".6" = icmp eq i32 %".5", 0
  store i1 %".6", i1* %"zero"
  %".8" = load i1, i1* %"zero"
  ret i1 %".8"
}

define %"Point" @"user_moved"(%"Point" %"p", i32 %"dx")
{
entry:
  %"q" = alloca %"Point"
  %"dx.slot" = alloca i32
  %"p.slot" = alloca %"Point"
  store %"Point" %"p", %"Point"* %"p.slot"
  store i32 %"dx", i32* %"dx.slot"
  %".6" = getelementptr %"Point", %"Point"* %"p.slot", i32 0, i32 0
  %".7" = load i32, i32* %".6"
  %".8" = load i32, i32* %"dx.slot"
  %".9" = add i32 %".7", %".8"
  %".10" = getelementptr %"Point", %"Point"* %"q", i32 0, i32 0
  store i32 %".9", i32* %".10"
  %".12" = getelementptr %"Point", %"Point"* %"p.slot", i32 0, i32 1
  %".13" = load i32, i32* %".12"
  %".14" = getelementptr %"Point", %"Point"* %"q", i32 0, i32 1
  store i32 %".13", i32* %".14"
  %".16" = load %"Point", %"Point"* %"q"
  ret %"Point" %".16"
}

define i32 @"main"()
{
entry:
  %"result" = alloca i32
  %"r" = alloca %"Point"
  %"z" = alloca i1
  %"xCoord" = alloca i32
  %"c" = alloca %"Circle"
  %"p" = alloca %"Point"
  %".2" = getelementptr %"Point", %"Point"* %"p", i32 0, i32 0
  store i32 10, i32* %".2"
  %".4" = getelementptr %"Point", %"Point"* %"p", i32 0, i32 1
  store i32 20, i32* %".4"
  %".6" = load %"Point", %"Point"* %"p"
  %".7" = getelementptr %"Circle", %"Circle"* %"c", i32 0, i32 0
  store %"Point" %".6", %"Point"* %".7"
  %".9" = getelementptr %"Circle", %"Circle"* %"c", i32 0, i32 1
  store i32 5, i32* %".9"
  %".11" = getelementptr %"Circle", %"Circle"* %"c", i32 0, i32 0, i32 0
  %".12" = load i32, i32* %".11"
  store i32 %".12", i32* %"xCoord"
  %".14" = load %"Point", %"Point"* %"p"
  %".15" = call i1 @"user_isXZero"(%"Point" %".14")
  store i1 %".15", i1* %"z"
  %".17" = load %"Point", %"Point"* %"p"
  %".18" = call %"Point" @"user_moved"(%"Point" %".17", i32 1)
  store %"Point" %".18", %"Point"* %"r"
  %".20" = load %"Point", %"Point"* %"r"
  %".21" = call %"Point" @"user_moved"(%"Point" %".20", i32 2)
  store %"Point" %".21", %"Point"* %"r"
  %".23" = load i32, i32* %"xCoord"
  %".24" = getelementptr %"Point", %"Point"* %"r", i32 0, i32 0
  %".25" = load i32, i32* %".24"
  %".26" = getelementptr %"Circle", %"Circle"* %"c", i32 0, i32 1
  %".27" = load i32, i32* %".26"
  %".28" = call i32 @"user_add"(i32 %".25", i32 %".27")
  %".29" = call i32 @"user_add"(i32 %".23", i32 %".28")
  store i32 %".29", i32* %"result"
  %".31" = load i32, i32* %"result"
  %"wide" = sext i32 %".31" to i64
  %".32" = bitcast [31 x i8]* @"fmt_int" to i8*
  %".33" = call i32 (i8*, ...) @"printf"(i8* %".32", i64 %"wide")
  ret i32 0
}
