#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
文件更新查找工具

这个命令行工具帮助用户查找在指定时间之后被更新的文件。
"""

import os
import sys
import argparse
import datetime
import time
from pathlib import Path

def parse_time(time_str):
    """
    解析用户输入的时间字符串，转换为时间戳。
    支持多种格式，如：
    - 'YYYY-MM-DD'
    - 'YYYY-MM-DD HH:MM:SS'
    - 'YYYY-MM-DD HH:MM'
    - 相对时间，如 '1h'（1小时前）, '2d'（2天前）, '3w'（3周前）
    """
    now = datetime.datetime.now()
    
    # 处理相对时间格式
    if time_str.endswith(('m', 'h', 'd', 'w')):
        unit = time_str[-1]
        try:
            amount = int(time_str[:-1])
        except ValueError:
            print(f"错误：无法解析相对时间 '{time_str}'")
            sys.exit(1)
            
        if unit == 'm':  # 分钟
            delta = datetime.timedelta(minutes=amount)
        elif unit == 'h':  # 小时
            delta = datetime.timedelta(hours=amount)
        elif unit == 'd':  # 天
            delta = datetime.timedelta(days=amount)
        elif unit == 'w':  # 周
            delta = datetime.timedelta(weeks=amount)
            
        return (now - delta).timestamp()
    
    # 处理绝对时间格式
    formats = [
        '%Y-%m-%d',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H:%M',
        '%Y/%m/%d',
        '%Y/%m/%d %H:%M:%S',
        '%Y/%m/%d %H:%M'
    ]
    
    for fmt in formats:
        try:
            dt = datetime.datetime.strptime(time_str, fmt)
            return dt.timestamp()
        except ValueError:
            continue
    
    print(f"错误：无法解析时间格式 '{time_str}'")
    print("支持的格式: 'YYYY-MM-DD', 'YYYY-MM-DD HH:MM:SS', '1h'(1小时前), '2d'(2天前)")
    sys.exit(1)

def find_recent_files(base_dir, timestamp, include_dirs=False, exclude_patterns=None):
    """
    查找在指定时间戳之后修改的所有文件
    
    参数:
        base_dir: 要搜索的基础目录
        timestamp: 时间戳，查找在此之后修改的文件
        include_dirs: 是否包含目录
        exclude_patterns: 要排除的文件/目录模式列表
    """
    if exclude_patterns is None:
        exclude_patterns = []
        
    recent_files = []
    
    for root, dirs, files in os.walk(base_dir):
        # 过滤掉需要排除的目录
        dirs[:] = [d for d in dirs if not any(pat in os.path.join(root, d) for pat in exclude_patterns)]
        
        # 检查目录
        if include_dirs:
            dir_path = os.path.abspath(root)
            try:
                mtime = os.path.getmtime(dir_path)
                if mtime > timestamp:
                    recent_files.append((dir_path, mtime))
            except OSError:
                pass
                
        # 检查文件
        for file in files:
            file_path = os.path.join(root, file)
            
            # 检查是否应该排除此文件
            if any(pat in file_path for pat in exclude_patterns):
                continue
                
            try:
                mtime = os.path.getmtime(file_path)
                if mtime > timestamp:
                    recent_files.append((file_path, mtime))
            except OSError:
                pass
    
    return recent_files

def format_time(timestamp):
    """格式化时间戳为人类可读的格式"""
    return datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

def main():
    parser = argparse.ArgumentParser(description="查找在指定时间之后更新的文件")
    parser.add_argument('time', help="指定的时间点，格式可以是 'YYYY-MM-DD'、'YYYY-MM-DD HH:MM:SS' 或相对时间如 '1h'(1小时前)、'2d'(2天前)")
    parser.add_argument('-d', '--directory', default='.', help="要搜索的目录，默认为当前目录")
    parser.add_argument('--include-dirs', action='store_true', help="是否包含目录")
    parser.add_argument('-e', '--exclude', action='append', default=[], help="要排除的文件/目录模式")
    parser.add_argument('-s', '--sort', choices=['time', 'name'], default='time', help="排序方式：按时间（默认）或按名称")
    parser.add_argument('-r', '--reverse', action='store_true', help="反向排序")
    
    args = parser.parse_args()
    
    # 解析时间
    timestamp = parse_time(args.time)
    print(f"查找在 {format_time(timestamp)} 之后更新的内容...\n")
    
    # 查找文件
    directory = os.path.abspath(args.directory)
    recent_files = find_recent_files(directory, timestamp, args.include_dirs, args.exclude)
    
    # 排序
    if args.sort == 'time':
        recent_files.sort(key=lambda x: x[1], reverse=not args.reverse)
    else:  # 按名称排序
        recent_files.sort(key=lambda x: x[0], reverse=args.reverse)
    
    # 显示结果
    if not recent_files:
        print(f"没有找到在 {format_time(timestamp)} 之后更新的文件。")
        return
        
    print(f"找到 {len(recent_files)} 个更新的项目:")
    print("-" * 80)
    for file_path, mtime in recent_files:
        rel_path = os.path.relpath(file_path, directory)
        mtime_str = format_time(mtime)
        file_size = os.path.getsize(file_path)
        
        # 格式化文件大小
        if file_size < 1024:
            size_str = f"{file_size} B"
        elif file_size < 1024 * 1024:
            size_str = f"{file_size/1024:.1f} KB"
        elif file_size < 1024 * 1024 * 1024:
            size_str = f"{file_size/(1024*1024):.1f} MB"
        else:
            size_str = f"{file_size/(1024*1024*1024):.1f} GB"
            
        print(f"{rel_path} ({size_str}) - {mtime_str}")
    print("-" * 80)

if __name__ == "__main__":
    main() 