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

int test6(int n){
    int arr[n];

   return arr[0];
}

float test7(){
    int a = 5;
    float fa = (float)a;
    return fa / 10000000;
}

int main(){
    int a = 50;
    int arr[a];
    test(arr);
    struct Foo foo;
    printf(foo.b);
    printf("%f\n", test7);
}