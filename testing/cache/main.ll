; ModuleID = "main"
target triple = "x86_64-unknown-linux-gnu"
target datalayout = ""

declare void @"printf"(i8* %"format", ...) 

define void @"main"() 
{
entry:
  %".2" = bitcast [14 x i8]* @".const.string.Hello world!\5cn" to i8*
  call void (i8*, ...) @"printf"(i8* %".2")
  ret void
}

@".const.string.Hello world!\5cn" = internal constant [14 x i8] c"Hello world!\0a\00"