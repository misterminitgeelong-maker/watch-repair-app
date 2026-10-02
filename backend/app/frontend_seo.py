"""Keep homepage search metadata out of application and customer-link pages."""
import re


def frontend_html(html: str, full_path: str) -> str:
    if full_path == "":
        return html
    for section in ("home", "content"):
        html = re.sub(
            rf"<!-- seo-{section}-start -->.*?<!-- seo-{section}-end -->",
            "",
            html,
            flags=re.DOTALL,
        )
    return html
