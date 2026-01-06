import logging
import os
from typing import Dict, List, Optional, Any
from utils.ai_client import AIClient

logger = logging.getLogger(__name__)


def _load_enhanced_review_prompt() -> str:
    """读取增强代码审查提示词文件"""
    prompt_path = os.path.join(os.path.dirname(__file__), '..', 'utils', 'prompts', 'enhanced_review.txt')
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        logger.warning(f"无法读取enhanced_review.txt提示词文件: {e}，使用默认提示词")
        return ""


class EnhancedCodeReview:
    """增强的代码审查服务，参考优秀实践提供结构化反馈"""
    
    def __init__(self, ai_provider: str = "deepseek"):
        self.ai_client = AIClient(ai_provider)
    
    async def analyze_code_with_categories(self, code: str, file_path: str = "") -> Dict[str, Any]:
        """
        对代码进行分类分析，返回结构化的审查结果
        
        Args:
            code: 要分析的代码内容
            file_path: 文件路径（可选）
            
        Returns:
            Dict: 包含各类别分析结果的结构化数据
        """
        try:
            # 构建提示词
            prompt = self._build_enhanced_review_prompt(code, file_path)
            
            # 调用AI分析
            response = await self.ai_client._chat_completion([
                {"role": "system", "content": "你是一位经验丰富的代码审查专家。"}
            ], prompt)
            
            # 解析响应
            parsed_result = self._parse_review_response(response)
            
            return {
                "success": True,
                "file_path": file_path,
                "analysis": parsed_result,
                "raw_response": response
            }
            
        except Exception as e:
            logger.error(f"增强代码分析失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "file_path": file_path
            }
    
    def _build_enhanced_review_prompt(self, code: str, file_path: str = "") -> str:
        """构建增强的代码审查提示词"""
        # 从文件读取提示词模板
        template = _load_enhanced_review_prompt()
        if not template:
            # 如果文件读取失败，使用默认提示词
            file_info = f"\n文件路径: {file_path}" if file_path else ""
            template = f"""请对以下代码进行全面审查，并按照指定格式提供反馈。

{file_info}

**审查维度：**
1. **语法和逻辑错误** - 代码语法问题、逻辑缺陷、潜在的运行时错误
2. **代码重构和质量** - 代码结构优化、可读性改进、重复代码消除
3. **性能优化机会** - 算法优化、资源使用效率、执行时间改进
4. **安全漏洞识别** - 安全风险、数据保护、输入验证、权限控制
5. **最佳实践符合性** - 编码规范、设计模式、错误处理、文档完整性

**要求输出格式：**
使用以下固定的标题结构，每个标题下的内容用项目符号列出具体建议：

**语法和逻辑错误**：
- 具体问题描述和位置

**代码重构和质量**：
- 具体改进建议

**性能优化**：
- 性能相关建议

**安全漏洞**：
- 安全相关问题和建议

**最佳实践**：
- 编码规范和最佳实践建议

**注意事项：**
- 每个类别最多提供3个具体建议
- 如果某个类别没有发现问题，请写"无相关问题"
- 建议要具体、可执行
- 包含具体的文件名和行号（如果可能）

**代码内容：**
```
{CODE}
```

**你的审查结果：**"""

        # 替换占位符
        file_info = f"\n文件路径: {file_path}" if file_path else ""
        prompt = template.replace("{FILE_INFO}", file_info)
        prompt = prompt.replace("{CODE}", code)
        
        return prompt
    
    def _parse_review_response(self, response: str) -> Dict[str, List[str]]:
        """
        解析AI返回的审查结果，提取各个类别的建议
        
        Args:
            response: AI返回的原始响应
            
        Returns:
            Dict: 按类别组织的建议列表
        """
        categories = {
            "语法和逻辑错误": [],
            "代码重构和质量": [],
            "性能优化": [],
            "安全漏洞": [],
            "最佳实践": []
        }
        
        try:
            import re
            
            # 使用正则表达式提取各个类别的内容
            pattern = r'\*\*(.+?)\*\*：(.*?)(?=\*\*|$)'
            matches = re.findall(pattern, response, re.DOTALL)
            
            for category, content in matches:
                category = category.strip()
                content = content.strip()
                
                if category in categories:
                    # 提取项目符号列表
                    lines = content.split('\n')
                    suggestions = []
                    
                    for line in lines:
                        line = line.strip()
                        if line.startswith('-'):
                            suggestion = line[1:].strip()
                            if suggestion and suggestion != "无相关问题":
                                suggestions.append(suggestion)
                    
                    categories[category] = suggestions
            
        except Exception as e:
            logger.error(f"解析审查响应失败: {e}")
            # 如果解析失败，返回原始响应作为通用建议
            categories["最佳实践"] = [response.strip()] if response.strip() else []
        
        return categories
    
    async def generate_structured_recommendations(self, analysis_result: Dict) -> List[Dict]:
        """
        基于分类分析结果生成结构化的建议
        
        Args:
            analysis_result: 分类分析结果
            
        Returns:
            List[Dict]: 标准化的建议列表
        """
        recommendations = []
        id_counter = 1
        
        # 定义优先级映射
        priority_map = {
            "语法和逻辑错误": "高",
            "安全漏洞": "高",
            "性能优化": "中",
            "代码重构和质量": "中",
            "最佳实践": "低"
        }
        
        for category, suggestions in analysis_result.items():
            priority = priority_map.get(category, "中")
            
            for suggestion in suggestions:
                recommendations.append({
                    "id": id_counter,
                    "category": category,
                    "priority": priority,
                    "title": suggestion[:60] + ("..." if len(suggestion) > 60 else ""),
                    "location": analysis_result.get("file_path", "未指定"),
                    "description": suggestion,
                    "issue": suggestion,
                    "fix": "根据建议进行相应修改",
                    "reason": f"基于{category}的分析",
                    "impact": "提升代码质量",
                    "recommendation": suggestion
                })
                id_counter += 1
        
        return recommendations
    
    def format_review_summary(self, analysis_result: Dict) -> str:
        """
        格式化审查结果为易读的摘要
        
        Args:
            analysis_result: 分析结果
            
        Returns:
            str: 格式化的摘要字符串
        """
        if not analysis_result.get("success"):
            return f"分析失败: {analysis_result.get('error', '未知错误')}"
        
        analysis = analysis_result.get("analysis", {})
        file_path = analysis_result.get("file_path", "未知文件")
        
        summary = f"## 代码审查报告\n\n"
        summary += f"**文件**: `{file_path}`\n\n"
        
        total_issues = sum(len(suggestions) for suggestions in analysis.values())
        summary += f"**总计发现问题**: {total_issues} 个\n\n"
        
        for category, suggestions in analysis.items():
            if suggestions:
                summary += f"### {category}\n\n"
                for i, suggestion in enumerate(suggestions, 1):
                    summary += f"{i}. {suggestion}\n"
                summary += "\n"
        
        return summary


# 使用示例函数
async def demo_enhanced_review(code: str, file_path: str = ""):
    """演示增强代码审查功能"""
    reviewer = EnhancedCodeReview()
    
    # 执行分析
    result = await reviewer.analyze_code_with_categories(code, file_path)
    
    if result["success"]:
        # 生成结构化建议
        recommendations = await reviewer.generate_structured_recommendations(result["analysis"])
        
        # 生成摘要
        summary = reviewer.format_review_summary(result)
        
        return {
            "summary": summary,
            "recommendations": recommendations,
            "detailed_analysis": result["analysis"]
        }
    else:
        return {"error": result["error"]}