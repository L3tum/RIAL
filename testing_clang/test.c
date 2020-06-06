#include <stdio.h>

struct Foo
{
    char *b;
    int a;
};

int test5(){
    int a = 5;
    return a;
}

void test4(struct Foo *foo){
    printf(foo->b);
}

void test3(int a){
    printf("%i\n", a);
}

void test2(char *p){
    printf(p);
}

int test(int arr[]){
    int s = sizeof(arr);
//    printf(sizeof(arr) / sizeof(arr[0]));

    return s;
}

int main(){
    int a = 50;
    int arr[a];
    test(arr);
    struct Foo foo;
    printf(foo.b);
}