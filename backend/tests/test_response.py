from app.core.context import set_trace_id
from app.core.response import envelope
from app.core.exceptions import BizError, unauthorized, forbidden
from app.schemas.common import PageParams, paginate


def test_envelope_shape():
    set_trace_id("t-123")
    e = envelope(data={"x": 1})
    assert e["code"] == 0
    assert e["message"] == "ok"
    assert e["data"] == {"x": 1}
    assert e["trace_id"] == "t-123"


def test_biz_error_factories():
    assert isinstance(unauthorized(), BizError)
    assert unauthorized().code == 1001
    assert unauthorized().http_status == 401
    assert forbidden().code == 1003
    assert forbidden().http_status == 403


def test_paginate():
    params = PageParams(page=2, page_size=10)
    out = paginate(items=[1, 2, 3], total=23, params=params)
    assert out == {"items": [1, 2, 3], "total": 23, "page": 2, "page_size": 10}


def test_page_params_caps_page_size():
    params = PageParams(page_size=999)
    assert params.page_size == 100
