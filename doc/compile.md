# 编译流程

## 本机库添加调用检查

### C 语言文件

假设有如下源代码

```c
struct A {
    int a;
};

struct B {
    double b;
};

typedef int (*Add) (struct A, struct B);

void some_func(Add add) {
    struct A a;
    a.a = 1;
    struct B b;
    b.b = 2.0;
    int c = add(a, b);
}
```

#### 源代码修改

编译过程中会发生如下修改，文件头部将加入函数涉及的结构体的前置声明，以及一个检查函数的声明。

```c
struct A;
struct B;
int __QEMU_NC_CHECK_i_AB(void *func, struct A a, struct B b);
```

且调用点将会被替换为
```c
int c = __QEMU_NC_CHECK_i_AB(add, a, b);
```

以上过程尽可能简化了修改流程，利用了前置声明，避免了在源文件中间插入函数。

#### 辅助文件生成



使用clang编写一个工具，能够对一个 cpp 文件进行以下处理。
1. 遇到函数实现，如果这个函数是一个全局函数，那么把实现部分删了，留下声明
2. 如果是一个类的函数，那么如果是写在外部的函数实现则整个删除，如果是在类声明内部的内联实现，那么删除实现部分（包括初始化列表），如果声明为 =default，则把=default删除
3. 注意一些编译器扩展，比如在函数旁边的attribute，在整个函数删除的时候也要删