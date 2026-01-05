from typing import Dict, Any, Optional


class SecurityUtils:
    """安全相关工具类"""

    SECURITY_KEYWORDS = {
        "vulnerability", "漏洞", "security", "安全",
        "sql injection", "xss", "csrf", "rce",
        "hardcoded", "credential", "password", "secret", "key",
        "auth", "permission", "access control", "unauthorized",
        "denial of service", "dos", "buffer overflow",
        "crypto", "weak encryption", "hashing"
    }

    CRITICAL_KEYWORDS = {
        "rce", "remote code execution", "command injection",
        "sql injection", "hardcoded password", "hardcoded secret",
        "private key"
    }

    @classmethod
    def is_security_issue(cls, issue: Dict[str, Any]) -> bool:
        """
        判断给定的问题是否为安全问题
        """
        issue_type = str(issue.get("type", "")).lower()
        issue_category = str(issue.get("category", "")).lower()
        issue_title = str(issue.get("title", issue.get("issue", ""))).lower()
        issue_severity = str(issue.get("severity", "")).lower()
        issue_desc = str(issue.get("description", issue.get("analysis", ""))).lower()
        issue_location = str(issue.get("location", issue.get("file", ""))).lower()

        if "安全风险" in issue_category or "安全" in issue_category or "security" in issue_category:
            return True

        if "security" in issue_type or "vulnerability" in issue_type or "安全" in issue_type:
            return True

        text_to_check = f"{issue_title} {issue_desc}"
        if any(keyword in text_to_check for keyword in cls.SECURITY_KEYWORDS):
            return True

        if issue_severity in ["critical", "high", "严重", "高"]:
            if any(k in text_to_check for k in ["inject", "auth", "access", "sensitive", "private"]):
                return True

        return False


    @classmethod
    def calculate_severity_score(cls, severity: str) -> int:
        """根据严重程度返回扣分值"""
        severity = severity.lower()
        if severity in ["critical", "严重"]:
            return 12  # 严重问题扣12分
        if severity in ["high", "高"]:
            return 8   # 高危问题扣8分
        if severity in ["medium", "中"]:
            return 5   # 中等风险扣5分
        if severity in ["low", "低"]:
            return 2   # 低风险扣2分
        return 1       # 默认扣1分
