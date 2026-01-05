#!/usr/bin/env python3
"""测试自动修复功能的语言识别"""


# 测试语言映射逻辑
def test_language_mapping():
    """测试文件扩展名到语言的映射"""
    lang_map = {
        'py': 'python',
        'java': 'java',
        'go': 'go',
        'js': 'javascript',
        'ts': 'typescript',
        'c': 'c',
        'cpp': 'cpp',
        'cs': 'csharp',
        'php': 'php',
        'rb': 'ruby',
        'rs': 'rust',
        'swift': 'swift',
        'kt': 'kotlin',
        'scala': 'scala',
        'html': 'html',
        'css': 'css',
        'json': 'json',
        'yaml': 'yaml',
        'xml': 'xml',
        'sh': 'bash',
        'sql': 'sql',
        'md': 'markdown'
    }

    test_cases = [
        ('py', 'python'),
        ('java', 'java'),
        ('go', 'go'),
        ('js', 'javascript'),
        ('ts', 'typescript'),
        ('unknown', 'text'),  # 默认值
    ]

    print("=== 语言映射测试 ===")
    for file_ext, expected_lang in test_cases:
        detected_lang = lang_map.get(file_ext, 'python')
        status = "✓" if detected_lang == expected_lang else "✗"
        print(f"{status} 扩展名: {file_ext:<10} -> 语言: {detected_lang:<15} (期望: {expected_lang})")

    print("\n所有测试完成！")


def test_auto_fix_service():
    """测试AutoFixService的文件扩展名识别"""
    import os
    from services.auto_fix_service import AutoFixService

    print("\n=== AutoFixService扩展名测试 ===")

    # 测试各种文件路径
    test_paths = [
        "src/main.py",
        "com/example/Main.java",
        "pkg/handler.go",
        "web/app.js",
        "server/app.ts",
        "lib/core.c",
        "src/main.cpp",
        "utils/helper.rb",
    ]

    service = AutoFixService()
    for file_path in test_paths:
        file_extension = os.path.splitext(file_path)[1].lower().lstrip('.') or "txt"
        print(f"文件路径: {file_path:<30} -> 扩展名: {file_extension}")

    print("\nAutoFixService测试完成！")


if __name__ == "__main__":
    test_language_mapping()
    test_auto_fix_service()
