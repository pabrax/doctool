import pytest

from doctool.http import content_disposition
from doctool.library import safe_filename


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("report.pdf", "report.pdf"),
        ("../../etc/passwd", "passwd"),
        ("C:\\dir\\a.pdf", "a.pdf"),
        ('we"ird?.pdf', "we_ird_.pdf"),
        ("a\r\nb.pdf", "a__b.pdf"),
        ("", "document.pdf"),
        ("...", "document.pdf"),
        ("señal.pdf", "señal.pdf"),
    ],
)
def test_safe_filename(raw, expected):
    assert safe_filename(raw) == expected


def test_safe_filename_is_length_bounded():
    assert len(safe_filename("a" * 1000 + ".pdf")) <= 200


def test_content_disposition_has_ascii_fallback_and_utf8_name():
    cd = content_disposition("señal 日本.pdf")
    assert cd.startswith('attachment; filename="')
    assert cd.isascii()
    assert "filename*=UTF-8''se%C3%B1al%20%E6%97%A5%E6%9C%AC.pdf" in cd


def test_content_disposition_never_contains_quotes_or_newlines_from_input():
    cd = content_disposition('x"\r\ny.pdf')
    assert "\r" not in cd and "\n" not in cd
    assert cd.count('"') == 2  # only the delimiters of the fallback name
