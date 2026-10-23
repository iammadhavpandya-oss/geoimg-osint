import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT)


@pytest.fixture(scope="session")
def samples(tmp_path_factory):
    from tests.make_samples import main
    d = tmp_path_factory.mktemp("samples")
    main(str(d))
    return d


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    from geoimg.modules import geocode
    monkeypatch.setattr(geocode, "CACHE", tmp_path / "nominatim.json")
    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "MAPILLARY_TOKEN", "GEOIMG_GEOCLIP_PYTHON"):
        monkeypatch.delenv(k, raising=False)
