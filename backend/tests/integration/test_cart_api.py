import pytest
from django.urls import reverse
from rest_framework import status

from apps.cart.models import Cart, CartItem
from apps.products.models import Product
from tests.conftest import ProductFactory, UserFactory, sample_image

pytestmark = pytest.mark.django_db


@pytest.fixture
def product(sample_image):
    """Fixture to create a product for cart tests."""
    return ProductFactory.create(stock_quantity=10, main_image=sample_image)


@pytest.fixture
def authenticated_client(db, api_client):
    user = UserFactory.create()
    from rest_framework_simplejwt.tokens import RefreshToken

    refresh = RefreshToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    api_client.user = user
    return api_client


# AC 1: Get Cart
def test_get_cart_for_authenticated_user(authenticated_client):
    """Test getting the cart for an authenticated user."""
    url = reverse("cart:cart-list")
    response = authenticated_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert response.data["total_items"] == 0


def test_get_cart_for_guest(api_client):
    """Test getting the cart for a guest user."""
    url = reverse("cart:cart-list")
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert response.data["total_items"] == 0


# AC 2: Add Item
def test_add_item_to_cart(authenticated_client, product):
    """Test adding an item to the cart."""
    url = reverse("cart:cart-items-list")
    variant = product.variants.first()
    data = {"variant_id": variant.id, "quantity": 2}
    response = authenticated_client.post(url, data, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    assert CartItem.objects.count() == 1
    cart = Cart.objects.get(user=authenticated_client.user)
    assert cart.total_items == 2


def test_add_same_item_merges_quantity(authenticated_client, product):
    """Test that adding the same item merges the quantity."""
    url = reverse("cart:cart-items-list")
    variant = product.variants.first()
    # Add first time
    authenticated_client.post(url, {"variant_id": variant.id, "quantity": 1}, format="json")
    # Add second time
    response = authenticated_client.post(url, {"variant_id": variant.id, "quantity": 2}, format="json")
    assert response.status_code == status.HTTP_201_CREATED  # Merging returns 201
    assert CartItem.objects.count() == 1
    cart = Cart.objects.get(user=authenticated_client.user)
    assert cart.items.first().quantity == 3


# AC 3: Update Item
def test_update_item_quantity(authenticated_client, product):
    """Test updating the quantity of a cart item."""
    # Add item first
    add_url = reverse("cart:cart-items-list")
    variant = product.variants.first()
    authenticated_client.post(add_url, {"variant_id": variant.id, "quantity": 1}, format="json")
    cart_item = CartItem.objects.first()

    update_url = reverse("cart:cart-items-detail", kwargs={"pk": cart_item.pk})
    response = authenticated_client.patch(update_url, {"quantity": 5}, format="json")
    assert response.status_code == status.HTTP_200_OK
    cart_item.refresh_from_db()
    assert cart_item.quantity == 5


# AC 4: Delete Item
def test_delete_item_from_cart(authenticated_client, product):
    """Test deleting an item from the cart."""
    add_url = reverse("cart:cart-items-list")
    variant = product.variants.first()
    authenticated_client.post(add_url, {"variant_id": variant.id, "quantity": 1}, format="json")
    cart_item = CartItem.objects.first()

    delete_url = reverse("cart:cart-items-detail", kwargs={"pk": cart_item.pk})
    response = authenticated_client.delete(delete_url)
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert CartItem.objects.count() == 0


# AC 5: Guest Cart
def test_guest_cart_persistence(api_client, product):
    """Test that a guest cart persists across requests."""
    url = reverse("cart:cart-items-list")
    variant = product.variants.first()
    response = api_client.post(url, {"variant_id": variant.id, "quantity": 1}, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    session_key = api_client.session.session_key
    assert Cart.objects.filter(session_key=session_key).exists()

    # Make another request to ensure the cart is retrieved
    cart_url = reverse("cart:cart-list")
    response = api_client.get(cart_url)
    assert response.status_code == status.HTTP_200_OK
    assert response.data["total_items"] == 1
