; ModuleID = '<string>'
source_filename = "<string>"
target datalayout = "e-m:e-i64:64-f80:128-n8:16:32:64-S128"
target triple = "x86_64-unknown-linux-gnu"

%"testing:print:Test" = type { i32 }

@".const.string.b'JWkgXG4='" = private unnamed_addr constant [5 x i8] c"%i \0A\00"
@".const.string.b'V2hpbGUgbG9vcDogJWlcbg=='" = private unnamed_addr constant [16 x i8] c"While loop: %i\0A\00"
@str = private unnamed_addr constant [13 x i8] c"Hello world!\00", align 1
@str.1 = private unnamed_addr constant [10 x i8] c"Loop loop\00", align 1
@".const.string.b'JWlcbg=='" = private unnamed_addr constant [4 x i8] c"%i\0A\00"
@str.6 = private unnamed_addr constant [5 x i8] c"Test\00", align 1
@".const.string.b'dHJ1ZQ=='" = private unnamed_addr constant [5 x i8] c"true\00"
@".const.string.b'ZmFsc2U='" = private unnamed_addr constant [6 x i8] c"false\00"

; Function Attrs: alwaysinline
define i32 @"testing:main:main."() local_unnamed_addr #0 !function_definition !1 {
entry:
  %puts = tail call i32 @puts(i8* getelementptr inbounds ([13 x i8], [13 x i8]* @str, i64 0, i64 0))
  tail call void (i8*, ...) @printf(i8* getelementptr inbounds ([5 x i8], [5 x i8]* @".const.string.b'JWkgXG4='", i64 0, i64 0), i1 true)
  tail call void (i8*, ...) @printf(i8* null)
  tail call void @"testing:print:printInteger.i32"(i32 0)
  tail call void @"testing:print:printInteger.i32"(i32 1)
  tail call void @"testing:print:printInteger.i32"(i32 2)
  tail call void @"testing:print:printInteger.i32"(i32 3)
  tail call void @"testing:print:printInteger.i32"(i32 4)
  tail call void (i8*, ...) @printf(i8* getelementptr inbounds ([16 x i8], [16 x i8]* @".const.string.b'V2hpbGUgbG9vcDogJWlcbg=='", i64 0, i64 0), i32 0)
  tail call void (i8*, ...) @printf(i8* getelementptr inbounds ([16 x i8], [16 x i8]* @".const.string.b'V2hpbGUgbG9vcDogJWlcbg=='", i64 0, i64 0), i32 1)
  tail call void (i8*, ...) @printf(i8* getelementptr inbounds ([16 x i8], [16 x i8]* @".const.string.b'V2hpbGUgbG9vcDogJWlcbg=='", i64 0, i64 0), i32 2)
  tail call void (i8*, ...) @printf(i8* getelementptr inbounds ([16 x i8], [16 x i8]* @".const.string.b'V2hpbGUgbG9vcDogJWlcbg=='", i64 0, i64 0), i32 3)
  tail call void (i8*, ...) @printf(i8* getelementptr inbounds ([16 x i8], [16 x i8]* @".const.string.b'V2hpbGUgbG9vcDogJWlcbg=='", i64 0, i64 0), i32 4)
  tail call void (i8*, ...) @printf(i8* getelementptr inbounds ([16 x i8], [16 x i8]* @".const.string.b'V2hpbGUgbG9vcDogJWlcbg=='", i64 0, i64 0), i32 5)
  %puts1 = tail call i32 @puts(i8* getelementptr inbounds ([10 x i8], [10 x i8]* @str.1, i64 0, i64 0))
  tail call void @"testing:print:printTestWrapper."()
  tail call void @"testing:boolean:printBoolean.i1"(i1 true)
  ret i32 0
}

; Function Attrs: nounwind
declare void @printf(i8* nocapture readonly, ...) local_unnamed_addr #1

; Function Attrs: nounwind
declare i32 @puts(i8* nocapture readonly) #1

; Function Attrs: nounwind
define void @"testing:print:printInteger.i32"(i32 %arg) local_unnamed_addr #1 !function_definition !2 {
entry:
  tail call void (i8*, ...) @printf(i8* getelementptr inbounds ([4 x i8], [4 x i8]* @".const.string.b'JWlcbg=='", i64 0, i64 0), i32 %arg)
  ret void
}

; Function Attrs: nounwind
define void @"testing:print:printTestWrapper."() local_unnamed_addr #1 !function_definition !2 {
entry:
  %.2 = tail call fastcc %"testing:print:Test"* @"testing:print:Test.constructor"()
  %0 = bitcast %"testing:print:Test"* %.2 to i32*
  %.4.unpack = load i32, i32* %0, align 4
  %.41 = insertvalue %"testing:print:Test" undef, i32 %.4.unpack, 0
  tail call fastcc void @"testing:print:printTestWrapperWrapper.testing:print:Test"(%"testing:print:Test" %.41)
  ret void
}

; Function Attrs: norecurse nounwind readnone
define private fastcc noalias nonnull %"testing:print:Test"* @"testing:print:Test.constructor"() unnamed_addr #2 !function_definition !3 {
entry:
  %this = alloca %"testing:print:Test", align 8
  ret %"testing:print:Test"* %this
}

; Function Attrs: nounwind
define private fastcc void @"testing:print:printTestWrapperWrapper.testing:print:Test"(%"testing:print:Test" %test) unnamed_addr #1 !function_definition !4 {
entry:
  tail call fastcc void @"testing:print:printTest.testing:print:Test*"()
  ret void
}

; Function Attrs: nounwind
define private fastcc void @"testing:print:printTest.testing:print:Test*"() unnamed_addr #1 !function_definition !4 {
entry:
  %puts = tail call i32 @puts(i8* getelementptr inbounds ([5 x i8], [5 x i8]* @str.6, i64 0, i64 0))
  ret void
}

; Function Attrs: nounwind
define void @"testing:boolean:printBoolean.i1"(i1 %boolean) local_unnamed_addr #1 !function_definition !2 {
entry:
  %.10 = select i1 %boolean, i8* getelementptr inbounds ([5 x i8], [5 x i8]* @".const.string.b'dHJ1ZQ=='", i64 0, i64 0), i8* getelementptr inbounds ([6 x i8], [6 x i8]* @".const.string.b'ZmFsc2U='", i64 0, i64 0)
  %puts = tail call i32 @puts(i8* %.10)
  ret void
}

; Function Attrs: nounwind
declare void @llvm.stackprotector(i8*, i8**) #1

attributes #0 = { alwaysinline }
attributes #1 = { nounwind }
attributes #2 = { norecurse nounwind readnone }

!compiler = !{!0, !0, !0}

!0 = !{!"RIALC"}
!1 = !{!"int", !"public"}
!2 = !{!"void", !"internal"}
!3 = !{!"testing:print:Test", !"private"}
!4 = !{!"void", !"private"}
