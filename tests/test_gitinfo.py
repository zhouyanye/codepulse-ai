import requests


def count_master_files(owner="psf", repo="requests", branch="main"):
    url = f'https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1'
    response = requests.get(url)

    if response.status_code == 200:
        tree = response.json().get('tree', [])
        file_count = sum(1 for item in tree if item['type'] == 'blob')  # 仅统计文件（blob类型）
        dir_count = sum(1 for item in tree if item['type'] == 'tree')  # 统计目录（可选）
        return f"main分支文件总数：{file_count}，目录总数：{dir_count}"
    elif response.status_code == 404:
        return "main分支不存在，请检查分支名（可能已改为main）"
    else:
        return f"请求失败：{response.status_code}"


# 执行查询
print(count_master_files())