#include <stdio.h>

void test(int arr[]){
    printf(sizeof(arr) / sizeof(arr[0]));
}

int main(){
    int arr[32];
    test(arr);
}