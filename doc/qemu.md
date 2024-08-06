# QEMU

## 编译 QEMU

```sh
sudo apt install ninja-build autoconf python3-pip

git clone https://github.com/rover2024/qemu

cd qemu
git checkout nc

mkdir build
../configure --target-list=x86_64-linux-user --enable-debug
make -j$(nproc)
```

## 如何修改 QEMU