; ModuleID = "practice5"
target triple = "x86_64-apple-darwin24.6.0"
target datalayout = ""

define i32 @"main"()
{
entry:
  %"c" = alloca i64
  %"b" = alloca i64
  %"a" = alloca i32
  store i32 10, i32* %"a"
  %".3" = load i32, i32* %"a"
  %"wide" = sext i32 %".3" to i64
  store i64 %"wide", i64* %"b"
  %".5" = load i32, i32* %"a"
  %".6" = load i64, i64* %"b"
  %"wide.1" = sext i32 %".5" to i64
  %".7" = add i64 %"wide.1", %".6"
  store i64 %".7", i64* %"c"
  %".9" = load i64, i64* %"c"
  %".10" = bitcast [31 x i8]* @"fmt_int" to i8*
  %".11" = call i32 (i8*, ...) @"printf"(i8* %".10", i64 %".9")
  ret i32 0
}

declare i32 @"printf"(i8* %".1", ...)

@"fmt_int" = private constant [31 x i8] c"Program exit with result %lld\0a\00"
@"fmt_str" = private constant [29 x i8] c"Program exit with result %s\0a\00"
@"str_true" = private constant [5 x i8] c"true\00"
@"str_false" = private constant [6 x i8] c"false\00"