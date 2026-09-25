"""
URL конфигурация для корзины
"""

from django.urls import path

from .views import CartItemViewSet, CartViewSet

app_name = "cart"

urlpatterns = [
    # GET /cart/ - получить корзину
    path("", CartViewSet.as_view({"get": "list"}), name="cart-list"),
    # DELETE /cart/clear/ - очистить корзину
    path("clear/", CartViewSet.as_view({"delete": "clear"}), name="cart-clear"),
    # CRUD операции с элементами корзины
    path(
        "items/",
        CartItemViewSet.as_view({"post": "create", "get": "list"}),
        name="cart-items-list",
    ),
    path(
        "items/<int:pk>/",
        CartItemViewSet.as_view({"get": "retrieve", "patch": "partial_update", "delete": "destroy"}),
        name="cart-items-detail",
    ),
]
