import sys
from bs4 import BeautifulSoup
from markdownify import markdownify as md

html_file = r"c:\Users\Duy\Desktop\buhbot\docs\api\zendesk_api_specification.html"
md_file = r"c:\Users\Duy\Desktop\buhbot\docs\api\zendesk_api_specificcation.md"

try:
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()

    soup = BeautifulSoup(html_content, 'html.parser')

    # Try to find the main content
    main_content = soup.find('main')
    if not main_content:
        main_content = soup.find('body')

    # Remove script and style tags
    for tag in main_content(['script', 'style', 'nav', 'header', 'footer']):
        tag.decompose()

    # Pre-process pre blocks
    for pre in main_content.find_all('pre'):
        code_lines = []
        # Find token lines first
        lines = pre.find_all('code', class_=lambda c: c and 'token-line' in c)
        if lines:
            for line in lines:
                code_lines.append(line.get_text())
        else:
            divs = pre.find_all('div')
            if divs:
                for div in divs:
                    code_lines.append(div.get_text())
            else:
                code_lines = [pre.get_text()]
        
        # Now replace the pre content with the clean text
        new_pre = soup.new_tag('pre')
        new_code = soup.new_tag('code')
        new_code.string = '\n'.join(code_lines)
        new_pre.append(new_code)
        pre.replace_with(new_pre)

    # Convert to markdown
    markdown_content = md(str(main_content), heading_style="ATX", strip=['script', 'style'])

    # Clean up multiple newlines that might have been generated
    import re
    markdown_content = re.sub(r'\n{3,}', '\n\n', markdown_content)

    with open(md_file, 'w', encoding='utf-8') as f:
        f.write(markdown_content)

    print(f"Successfully converted using markdownify with cleaned pre blocks, saved to {md_file}")

except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
