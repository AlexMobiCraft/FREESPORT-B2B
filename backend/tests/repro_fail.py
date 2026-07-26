from decimal import Decimal

import pytest

from tests.conftest import ProductFactory


@pytest.mark.django_db
def test_repro():
    print("Running repro test...")
    try:
        ProductFactory.create(retail_price=Decimal("123.00"))
        print("Success!")
    except Exception as e:
        print(f"Caught exception: {e}")
        raise e
