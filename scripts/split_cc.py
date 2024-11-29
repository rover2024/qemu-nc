import json
import os
import argparse

def split_compile_commands(input_file, num_parts, output_dir):
    # 读取原始 compile_commands.json 文件
    with open(input_file, 'r', encoding='utf-8') as f:
        compile_commands = json.load(f)

    # 计算每一份文件包含的命令数
    total_commands = len(compile_commands)
    commands_per_part = total_commands // num_parts
    remainder = total_commands % num_parts

    # 拆分 compile_commands 并保存为多个文件
    start_idx = 0
    for i in range(1, num_parts + 1):
        # 计算每一部分的结束索引
        end_idx = start_idx + commands_per_part + (1 if i <= remainder else 0)
        part_commands = compile_commands[start_idx:end_idx]

        # 生成输出文件名
        output_file = os.path.join(output_dir, f"compile_commands_{i}.json")
        
        # 保存拆分后的部分
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(part_commands, f, indent=4)

        # 更新起始索引
        start_idx = end_idx
        print(f"创建文件：{output_file}")

def main():
    # 设置命令行参数解析
    parser = argparse.ArgumentParser(description="拆分 compile_commands.json 文件")
    parser.add_argument('num_parts', type=int, help="将 compile_commands.json 拆分成的份数")
    parser.add_argument('input_file', type=str, help="输入的 compile_commands.json 文件路径")
    parser.add_argument('output_dir', type=str, help="拆分后的文件保存目录")

    # 解析命令行参数
    args = parser.parse_args()

    # 检查输入文件是否存在
    if not os.path.exists(args.input_file):
        print(f"输入文件 {args.input_file} 不存在！")
        exit(1)

    # 检查输出目录是否存在
    if not os.path.isdir(args.output_dir):
        print(f"输出目录 {args.output_dir} 不存在，正在创建...")
        os.makedirs(args.output_dir)

    # 调用拆分函数
    split_compile_commands(args.input_file, args.num_parts, args.output_dir)

if __name__ == "__main__":
    main()
