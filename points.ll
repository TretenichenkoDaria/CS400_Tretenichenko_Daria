; ModuleID = "practice9"
target triple = "x86_64-apple-darwin24.6.0"
target datalayout = ""

%"Point" = type {i32, i32}
declare i32 @"printf"(i8* %".1", ...)

declare i32 @"scanf"(i8* %".1", ...)

@"fmt_read" = private constant [3 x i8] c"%d\00"
@"fmt_int" = private constant [31 x i8] c"Program exit with result %lld\0a\00"
@"fmt_str" = private constant [29 x i8] c"Program exit with result %s\0a\00"
@"str_true" = private constant [5 x i8] c"true\00"
@"str_false" = private constant [6 x i8] c"false\00"
define i32 @"Point_d2"(%"Point"* %"this")
{
entry:
  %"r" = alloca i32
  %".3" = getelementptr %"Point", %"Point"* %"this", i32 0, i32 0
  %".4" = load i32, i32* %".3"
  %".5" = getelementptr %"Point", %"Point"* %"this", i32 0, i32 0
  %".6" = load i32, i32* %".5"
  %".7" = mul i32 %".4", %".6"
  %".8" = getelementptr %"Point", %"Point"* %"this", i32 0, i32 1
  %".9" = load i32, i32* %".8"
  %".10" = getelementptr %"Point", %"Point"* %"this", i32 0, i32 1
  %".11" = load i32, i32* %".10"
  %".12" = mul i32 %".9", %".11"
  %".13" = add i32 %".7", %".12"
  store i32 %".13", i32* %"r"
  %".15" = load i32, i32* %"r"
  ret i32 %".15"
}

define i32 @"user_report"(%"Point" %"p", i32 %"d")
{
entry:
  %"hit" = alloca i32
  %"d.slot" = alloca i32
  %"p.slot" = alloca %"Point"
  store %"Point" %"p", %"Point"* %"p.slot"
  store i32 %"d", i32* %"d.slot"
  store i32 0, i32* %"hit"
  %".7" = call i32 @"Point_d2"(%"Point"* %"p.slot")
  %".8" = load i32, i32* %"d.slot"
  %".9" = icmp eq i32 %".7", %".8"
  br i1 %".9", label %"then", label %"merge"
then:
  %".11" = bitcast [3 x i8]* @"str_const_1" to i8*
  %".12" = bitcast [7 x i8]* @"str_const_0" to i8*
  %".13" = call i32 (i8*, ...) @"printf"(i8* %".11", i8* %".12")
  %".14" = bitcast [3 x i8]* @"str_const_1" to i8*
  %".15" = bitcast [4 x i8]* @"str_const_2" to i8*
  %".16" = call i32 (i8*, ...) @"printf"(i8* %".14", i8* %".15")
  %".17" = getelementptr %"Point", %"Point"* %"p.slot", i32 0, i32 0
  %".18" = load i32, i32* %".17"
  %".19" = bitcast [3 x i8]* @"str_const_3" to i8*
  %".20" = call i32 (i8*, ...) @"printf"(i8* %".19", i32 %".18")
  %".21" = bitcast [3 x i8]* @"str_const_1" to i8*
  %".22" = bitcast [6 x i8]* @"str_const_4" to i8*
  %".23" = call i32 (i8*, ...) @"printf"(i8* %".21", i8* %".22")
  %".24" = getelementptr %"Point", %"Point"* %"p.slot", i32 0, i32 1
  %".25" = load i32, i32* %".24"
  %".26" = bitcast [3 x i8]* @"str_const_3" to i8*
  %".27" = call i32 (i8*, ...) @"printf"(i8* %".26", i32 %".25")
  %".28" = bitcast [3 x i8]* @"str_const_1" to i8*
  %".29" = bitcast [3 x i8]* @"str_const_5" to i8*
  %".30" = call i32 (i8*, ...) @"printf"(i8* %".28", i8* %".29")
  store i32 1, i32* %"hit"
  br label %"merge"
merge:
  %".33" = load i32, i32* %"hit"
  ret i32 %".33"
}

@"str_const_0" = private constant [7 x i8] c"Point{\00"
@"str_const_1" = private constant [3 x i8] c"%s\00"
@"str_const_2" = private constant [4 x i8] c"x: \00"
@"str_const_3" = private constant [3 x i8] c"%d\00"
@"str_const_4" = private constant [6 x i8] c", y: \00"
@"str_const_5" = private constant [3 x i8] c"}\0a\00"
define i32 @"main"()
{
entry:
  %"n" = alloca i32
  %"read.slot.6" = alloca i32
  %"d" = alloca i32
  %"read.slot.5" = alloca i32
  %"read.slot.4" = alloca i32
  %"p3" = alloca %"Point"
  %"read.slot.3" = alloca i32
  %"read.slot.2" = alloca i32
  %"p2" = alloca %"Point"
  %"read.slot.1" = alloca i32
  %"read.slot" = alloca i32
  %"p1" = alloca %"Point"
  %".2" = bitcast [4 x i8]* @"str_const_7" to i8*
  %".3" = bitcast [21 x i8]* @"str_const_6" to i8*
  %".4" = call i32 (i8*, ...) @"printf"(i8* %".2", i8* %".3")
  %".5" = bitcast [3 x i8]* @"fmt_read" to i8*
  %".6" = call i32 (i8*, ...) @"scanf"(i8* %".5", i32* %"read.slot")
  %".7" = load i32, i32* %"read.slot"
  %".8" = getelementptr %"Point", %"Point"* %"p1", i32 0, i32 0
  store i32 %".7", i32* %".8"
  %".10" = bitcast [3 x i8]* @"fmt_read" to i8*
  %".11" = call i32 (i8*, ...) @"scanf"(i8* %".10", i32* %"read.slot.1")
  %".12" = load i32, i32* %"read.slot.1"
  %".13" = getelementptr %"Point", %"Point"* %"p1", i32 0, i32 1
  store i32 %".12", i32* %".13"
  %".15" = bitcast [4 x i8]* @"str_const_7" to i8*
  %".16" = bitcast [21 x i8]* @"str_const_8" to i8*
  %".17" = call i32 (i8*, ...) @"printf"(i8* %".15", i8* %".16")
  %".18" = bitcast [3 x i8]* @"fmt_read" to i8*
  %".19" = call i32 (i8*, ...) @"scanf"(i8* %".18", i32* %"read.slot.2")
  %".20" = load i32, i32* %"read.slot.2"
  %".21" = getelementptr %"Point", %"Point"* %"p2", i32 0, i32 0
  store i32 %".20", i32* %".21"
  %".23" = bitcast [3 x i8]* @"fmt_read" to i8*
  %".24" = call i32 (i8*, ...) @"scanf"(i8* %".23", i32* %"read.slot.3")
  %".25" = load i32, i32* %"read.slot.3"
  %".26" = getelementptr %"Point", %"Point"* %"p2", i32 0, i32 1
  store i32 %".25", i32* %".26"
  %".28" = bitcast [4 x i8]* @"str_const_7" to i8*
  %".29" = bitcast [21 x i8]* @"str_const_9" to i8*
  %".30" = call i32 (i8*, ...) @"printf"(i8* %".28", i8* %".29")
  %".31" = bitcast [3 x i8]* @"fmt_read" to i8*
  %".32" = call i32 (i8*, ...) @"scanf"(i8* %".31", i32* %"read.slot.4")
  %".33" = load i32, i32* %"read.slot.4"
  %".34" = getelementptr %"Point", %"Point"* %"p3", i32 0, i32 0
  store i32 %".33", i32* %".34"
  %".36" = bitcast [3 x i8]* @"fmt_read" to i8*
  %".37" = call i32 (i8*, ...) @"scanf"(i8* %".36", i32* %"read.slot.5")
  %".38" = load i32, i32* %"read.slot.5"
  %".39" = getelementptr %"Point", %"Point"* %"p3", i32 0, i32 1
  store i32 %".38", i32* %".39"
  %".41" = bitcast [4 x i8]* @"str_const_7" to i8*
  %".42" = bitcast [24 x i8]* @"str_const_10" to i8*
  %".43" = call i32 (i8*, ...) @"printf"(i8* %".41", i8* %".42")
  %".44" = bitcast [3 x i8]* @"fmt_read" to i8*
  %".45" = call i32 (i8*, ...) @"scanf"(i8* %".44", i32* %"read.slot.6")
  %".46" = load i32, i32* %"read.slot.6"
  store i32 %".46", i32* %"d"
  %".48" = load %"Point", %"Point"* %"p1"
  %".49" = load i32, i32* %"d"
  %".50" = call i32 @"user_report"(%"Point" %".48", i32 %".49")
  %".51" = load %"Point", %"Point"* %"p2"
  %".52" = load i32, i32* %"d"
  %".53" = call i32 @"user_report"(%"Point" %".51", i32 %".52")
  %".54" = add i32 %".50", %".53"
  %".55" = load %"Point", %"Point"* %"p3"
  %".56" = load i32, i32* %"d"
  %".57" = call i32 @"user_report"(%"Point" %".55", i32 %".56")
  %".58" = add i32 %".54", %".57"
  store i32 %".58", i32* %"n"
  %".60" = load i32, i32* %"n"
  %"wide" = sext i32 %".60" to i64
  %".61" = bitcast [31 x i8]* @"fmt_int" to i8*
  %".62" = call i32 (i8*, ...) @"printf"(i8* %".61", i64 %"wide")
  ret i32 0
}

@"str_const_6" = private constant [21 x i8] c"Enter point 1 (x y):\00"
@"str_const_7" = private constant [4 x i8] c"%s\0a\00"
@"str_const_8" = private constant [21 x i8] c"Enter point 2 (x y):\00"
@"str_const_9" = private constant [21 x i8] c"Enter point 3 (x y):\00"
@"str_const_10" = private constant [24 x i8] c"Enter distance squared:\00"