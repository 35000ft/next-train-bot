import os

from lxml import html
from html2image import Html2Image


def dom_to_image(dom: str, save_path: str, size: tuple = (1200, 800), ):
    html_str = html.tostring(dom, encoding='unicode', method='html')
    filename = os.path.basename(save_path)
    dirname = os.path.dirname(save_path)
    full_html = f"""
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{
                    background-color: white;
                }}
                table {{ border-collapse: collapse; font-family: sans-serif; }}
                td, th {{ border: 1px solid #888; padding: 6px; }}
                a {{
                    color: inherit;
                    text-decoration: none;
                    cursor: default;
                }}
            </style>
        </head>
        <body>{html_str}</body>
        </html>
        """

    hti = Html2Image(output_path=dirname, size=size, custom_flags=['--no-sandbox'])
    hti.screenshot(html_str=full_html, save_as=filename)
