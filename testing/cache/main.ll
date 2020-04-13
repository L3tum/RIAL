; ModuleID = '<string>'
source_filename = "<string>"
target datalayout = "e-m:e-i64:64-f80:128-n8:16:32:64-S128"
target triple = "x86_64-unknown-linux-gnu"

@".const.string.b'SGVsbG8gd29ybGQhXG4='" = private unnamed_addr constant [14 x i8] c"Hello world!\0A\00"
@".const.string.b'JWkgXG4='" = private unnamed_addr constant [5 x i8] c"%i \0A\00"
@".const.string.b'SGk='" = private unnamed_addr constant [3 x i8] c"Hi\00"
@".const.string.b'V2hpbGUgbG9vcDogJWlcbg=='" = private unnamed_addr constant [16 x i8] c"While loop: %i\0A\00"
@".const.string.b'TG9vcCBsb29wXG4='" = private unnamed_addr constant [11 x i8] c"Loop loop\0A\00"

; Function Attrs: alwaysinline
define i32 @"testing:main:main."() #0 !function_definition !1 {
entry:
  call void (i8*, ...) @printf(i8* getelementptr inbounds ([14 x i8], [14 x i8]* @".const.string.b'SGVsbG8gd29ybGQhXG4='", i32 0, i32 0))
  %.3 = add i32 5, 5
  %.4 = icmp slt i32 5, %.3
  call void (i8*, ...) @printf(i8* getelementptr inbounds ([5 x i8], [5 x i8]* @".const.string.b'JWkgXG4='", i32 0, i32 0), i1 %.4)
  br label %entry.condition

entry.condition:                                  ; preds = %entry
  %.7 = icmp slt i32 5, 10
  br i1 %.7, label %entry.body, label %entry.if_else.end

entry.body:                                       ; preds = %entry.condition
  call void (i8*, ...) @printf(i8* null)
  br label %entry.if_else.end

entry.if_else.end:                                ; preds = %entry.body, %entry.condition
  br label %entry.if_else.end.wrapper

entry.if_else.end.wrapper:                        ; preds = %entry.if_else.end
  %i = alloca i32, !type !2
  store i32 0, i32* %i
  br label %entry.if_else.end.wrapper.condition

entry.if_else.end.wrapper.condition:              ; preds = %entry.if_else.end.wrapper.body, %entry.if_else.end.wrapper
  %.17 = load i32, i32* %i
  %.18 = icmp slt i32 %.17, 5
  br i1 %.18, label %entry.if_else.end.wrapper.body, label %entry.if_else.end.wrapper.end

entry.if_else.end.wrapper.body:                   ; preds = %entry.if_else.end.wrapper.condition
  %j = alloca i32, !type !2
  store i32 0, i32* %j
  %.22 = load i32, i32* %i
  %.23 = load i32, i32* %j
  %.24 = add i32 %.23, %.22
  store i32 %.24, i32* %j
  %.26 = load i32, i32* %j
  call void @"testing:print:printInteger.i32"(i32 %.26)
  %.28 = load i32, i32* %i
  %.29 = add i32 %.28, 1
  store i32 %.29, i32* %i
  br label %entry.if_else.end.wrapper.condition

entry.if_else.end.wrapper.end:                    ; preds = %entry.if_else.end.wrapper.condition
  %i.1 = alloca i32, !type !2
  store i32 0, i32* %i.1
  br label %entry.if_else.end.wrapper.end.condition

entry.if_else.end.wrapper.end.condition:          ; preds = %entry.if_else.end.wrapper.end.body.end, %entry.if_else.end.wrapper.end
  br i1 true, label %entry.if_else.end.wrapper.end.body, label %entry.if_else.end.wrapper.end.end

entry.if_else.end.wrapper.end.body:               ; preds = %entry.if_else.end.wrapper.end.condition
  %.36 = load i32, i32* %i.1
  call void (i8*, ...) @printf(i8* getelementptr inbounds ([16 x i8], [16 x i8]* @".const.string.b'V2hpbGUgbG9vcDogJWlcbg=='", i32 0, i32 0), i32 %.36)
  %.38 = load i32, i32* %i.1
  %.39 = add i32 %.38, 1
  store i32 %.39, i32* %i.1
  br label %entry.if_else.end.wrapper.end.body.condition

entry.if_else.end.wrapper.end.end:                ; preds = %entry.if_else.end.wrapper.end.body.body, %entry.if_else.end.wrapper.end.condition
  br label %entry.if_else.end.wrapper.end.end.body

entry.if_else.end.wrapper.end.body.condition:     ; preds = %entry.if_else.end.wrapper.end.body
  %.42 = load i32, i32* %i.1
  %.43 = icmp sgt i32 %.42, 5
  br i1 %.43, label %entry.if_else.end.wrapper.end.body.body, label %entry.if_else.end.wrapper.end.body.end

entry.if_else.end.wrapper.end.body.body:          ; preds = %entry.if_else.end.wrapper.end.body.condition
  br label %entry.if_else.end.wrapper.end.end

entry.if_else.end.wrapper.end.body.end:           ; preds = %entry.if_else.end.wrapper.end.body.condition
  br label %entry.if_else.end.wrapper.end.condition

entry.if_else.end.wrapper.end.end.body:           ; preds = %entry.if_else.end.wrapper.end.end
  call void (i8*, ...) @printf(i8* getelementptr inbounds ([11 x i8], [11 x i8]* @".const.string.b'TG9vcCBsb29wXG4='", i32 0, i32 0))
  br label %entry.if_else.end.wrapper.end.end.end

entry.if_else.end.wrapper.end.end.end:            ; preds = %entry.if_else.end.wrapper.end.end.body
  call void @"testing:print:printTestWrapper."()
  call void @"testing:boolean:printBoolean.i1"(i1 true)
  ret i32 0
}

declare void @printf(i8*, ...)

declare void @"testing:print:printInteger.i32"(i32)

declare void @"testing:print:printTestWrapper."()

declare void @"testing:boolean:printBoolean.i1"(i1)

; Function Attrs: nounwind
declare void @llvm.stackprotector(i8*, i8**) #1

attributes #0 = { alwaysinline }
attributes #1 = { nounwind }

!compiler = !{!0}

!0 = !{!"RIALC"}
!1 = !{!"Int32", !"public"}
!2 = !{!""}
