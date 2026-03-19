from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('add-recipe/', views.add_recipe, name='add_recipe'),
    path('recipes/', views.view_recipes, name='view_recipes'),
    path('recipe/<int:id>/', views.recipe_detail, name='recipe_detail'),
    
    path('recipe/<int:id>/download/', views.download_recipe_pdf, name='download_pdf'),
    
    path('recipe/<int:recipe_id>/like/', views.toggle_like, name='toggle_like'),
]
