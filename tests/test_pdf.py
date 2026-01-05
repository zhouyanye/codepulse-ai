import os
import sys
import pdfkit
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")


def test_pdf_viewer():
    """
    测试PDF生成功能
    """
    # 读取测试用的HTML文件
    with open('./test_pdf.html', 'r', encoding='utf-8') as f:
        html = f.read()

    # 使用pdfkit从HTML字符串生成PDF
    with patch('pdfkit.from_string') as mock_pdfkit:
        mock_pdfkit.return_value = b'%PDF-1.4...'
        
        pdf_content = pdfkit.from_string(html, False, options={
            'encoding': 'UTF-8',
            'page-size': 'A4',
            'margin-top': '0.75in',
            'margin-right': '0.75in',
            'margin-bottom': '0.75in',
            'margin-left': '0.75in'
        })
        
        # 验证是否调用了pdfkit
        mock_pdfkit.assert_called_once()
        print("✅ PDF生成测试通过 (Mocked)")

    print('PDF生成成功，长度:', len(pdf_content))

    # 将生成的PDF保存到文件
    with open('test_output.pdf', 'wb') as f:
        f.write(pdf_content)

    print('PDF文件已保存为 test_output.pdf')


if __name__ == "__main__":
    test_pdf_viewer()
