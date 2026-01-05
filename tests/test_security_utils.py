import pytest
from utils.security_utils import SecurityUtils


class TestSecurityUtils:
    """测试安全工具类"""
    
    def test_is_security_issue(self):
        """测试安全问题检测"""
        # 测试包含安全关键词的问题
        issue_with_security = {
            "title": "Potential SQL injection vulnerability",
            "description": "Found SQL injection in user input processing"
        }
        assert SecurityUtils.is_security_issue(issue_with_security) == True
        
        # 测试不包含安全关键词的问题
        issue_without_security = {
            "title": "Code style improvement",
            "description": "Improve code formatting"
        }
        assert SecurityUtils.is_security_issue(issue_without_security) == False
        
        # 测试包含安全关键词的描述
        issue_with_security_desc = {
            "title": "Performance issue",
            "description": "This function has a potential XSS vulnerability"
        }
        assert SecurityUtils.is_security_issue(issue_with_security_desc) == True
    
    def test_detect_security_patterns(self):
        """测试安全模式检测"""
        code_with_exec = "user_input = input(); exec(user_input)"
        patterns = SecurityUtils.detect_security_patterns(code_with_exec)
        assert "exec" in str(patterns).lower()
        
        code_safe = "user_input = input(); print(user_input)"
        patterns_safe = SecurityUtils.detect_security_patterns(code_safe)
        # 安全代码可能仍会返回一些信息，但不会有高风险模式
        assert isinstance(patterns_safe, list) or isinstance(patterns_safe, str)
    
    def test_check_license_compliance(self):
        """测试许可证合规性检查"""
        # 测试MIT许可证
        license_info = {"name": "MIT", "spdx_id": "MIT"}
        compliance = SecurityUtils.check_license_compliance(license_info)
        assert compliance["is_compliant"] == True
        
        # 测试GPL许可证
        gpl_license = {"name": "GNU General Public License v3.0", "spdx_id": "GPL-3.0"}
        gpl_compliance = SecurityUtils.check_license_compliance(gpl_license)
        assert gpl_compliance["is_compliant"] == False  # GPL通常被认为不合规
    
    def test_validate_repo_url(self):
        """测试仓库URL验证"""
        # 测试有效的GitHub URL
        valid_github = "https://github.com/user/repo"
        assert SecurityUtils.validate_repo_url(valid_github) == True
        
        # 测试有效的Gitee URL
        valid_gitee = "https://gitee.com/user/repo"
        assert SecurityUtils.validate_repo_url(valid_gitee) == True
        
        # 测试无效URL
        invalid_url = "not-a-url"
        assert SecurityUtils.validate_repo_url(invalid_url) == False
    
    def test_sanitize_input(self):
        """测试输入清理"""
        # 测试包含恶意代码的输入
        malicious_input = "'; DROP TABLE users; --"
        sanitized = SecurityUtils.sanitize_input(malicious_input)
        # 确保清理后的输入不为空，并且是字符串
        assert isinstance(sanitized, str)
        assert len(sanitized) > 0
    
    def test_check_repo_security(self):
        """测试仓库安全检查"""
        repo_info = {
            "has_issues": True,
            "has_projects": False,
            "has_wiki": True,
            "default_branch": "main"
        }
        
        security_report = SecurityUtils.check_repo_security(repo_info)
        assert "security_score" in security_report
        assert "issues" in security_report
        assert isinstance(security_report["security_score"], (int, float))