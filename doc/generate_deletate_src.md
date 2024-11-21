# 生成代理库

## 步骤

1. 使用 nm 工具获取动态库导出的函数符号，生成到一个列表文件`symbols.txt`中
```bash
nm -D <so> | grep " T " | awk '{print $3}'  > symbols.txt
```

对于某些使用 VLA 的函数，需要做特殊标注。

使用不定参数以及使用`va_list`的函数，一般有两种处理方式，其代表函数分别是`scanf`与`printf`。

对于回调函数中的`va_list`，一律视为`printf`类型。
对于普通函数中的`va_list`，默认视为`printf`类型，如果函数名中存在`scanf`，那么视为`scanf`类型。


2. 编写一个头文件，引入库的所有头文件，命名为`headers.h`
```cpp
#include "a.h"
#include "b.h"
// ...
```

3. 使用代理库生成器，生成代理库的源代码
```bash
python3 delegen.py -I/path/to -DFOO=foo -o main.cpp symbols.txt headers.h <name>
```

命令行参数：
- `-I`：头文件搜索目录
- `-D`：预定义宏
- `-o`：输出文件名

# 函数调用时间

100000000 次：

- native
    - cycles: 6006362949
    - time: 2.6 s

- box64
    - cycles: 